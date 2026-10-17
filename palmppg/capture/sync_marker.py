"""Hardware sync marker on the recording Pi: LED + buzzer patterns P1/P2 logged on the reference clock.

Protocol section 4.2: one LED and one active piezo buzzer on two GPIO pins, driven from the same call.
At ``t_start + 2 s`` the marker emits P1 (three pulses, 100 ms on / 200 ms off); at ``t_end - 5 s``
(or ``t_start + 28 s`` when the Kardia app only records 30 s, section 4.3) it emits P2 (two pulses,
300 ms on / 300 ms off). Every LED edge is logged to ``sync_events.csv`` (CONTRACTS section 3.4) with
``mono_ns`` = ``CLOCK_BOOTTIME`` (the reference clock, DECISIONS D-001), ``wall_ns`` for audit only and a
``gpio_ok`` self-check made by reading the pin state back after setting it.

All pattern quantities (pulse counts, on/off durations, placement) come from ``unit_config.yaml``
``marker.*``; nothing is hard-coded. ``gpiozero`` is imported lazily; without it (or with
``simulate=True``) the pins are ``MockPin`` objects that record every state change with its time, so the
whole schedule runs on any machine and the log it writes has the real format and the real timing.

CLI (used by the tests): ``python -m palmppg.capture.sync_marker --simulate --seconds 8`` writes a log
with P1 at 2 s and P2 at ``8 - 5 = 3 s`` and exits once P2 has finished.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Self

import yaml

log = logging.getLogger(__name__)

SYNC_EVENT_COLUMNS: tuple[str, ...] = ("event_id", "kind", "pattern", "mono_ns", "wall_ns", "gpio_ok")
PATTERN_NAMES: tuple[str, ...] = ("P1", "P2")
P2_MODES: tuple[str, ...] = ("before_end", "after_start")
BUSY_WAIT_NS = 2_000_000           # busy-wait the last 2 ms of every timed wait (WP12 spec)
_SLEEP_CHUNK_S = 0.05               # longest single time.sleep so cancellation is responsive
DEFAULT_UNIT_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "unit_config.yaml"


# --------------------------------------------------------------------------- clocks and timed waits
def mono_ns() -> int:
    """Reference clock: ``CLOCK_BOOTTIME`` in nanoseconds (what picamera2 reports as SensorTimestamp)."""
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


def wall_ns() -> int:
    """Wall clock in nanoseconds since the epoch (audit only, never used for alignment)."""
    return time.time_ns()


def sleep_until(target_mono_ns: int, cancel: threading.Event | None = None, busy_ns: int = BUSY_WAIT_NS) -> bool:
    """Block until the reference clock reaches ``target_mono_ns``; coarse ``time.sleep`` then a busy-wait.

    The busy-wait covers the last ``busy_ns`` (2 ms) so edges land within a fraction of a millisecond of
    their target on a Pi. Returns False if ``cancel`` was set before the target was reached.
    Serves section 4.2 (edge timing precision).
    """
    target = int(target_mono_ns)
    while True:
        remaining = target - mono_ns()
        if remaining <= busy_ns:
            break
        if cancel is not None and cancel.is_set():
            return False
        time.sleep(min((remaining - busy_ns) / 1e9, _SLEEP_CHUNK_S))
    while mono_ns() < target:
        if cancel is not None and cancel.is_set():
            return False
    return True


# --------------------------------------------------------------------------- pins
class MockPin:
    """Stand-in for a gpiozero output device: records (mono_ns, state) for every change, reads back its state."""

    def __init__(self, pin: int, name: str = "pin"):
        self.pin = int(pin)
        self.name = name
        self._state = 0
        self.history: list[tuple[int, int]] = []
        self.closed = False

    def on(self) -> None:
        self._state = 1
        self.history.append((mono_ns(), 1))

    def off(self) -> None:
        self._state = 0
        self.history.append((mono_ns(), 0))

    @property
    def value(self) -> int:
        return self._state

    @property
    def is_active(self) -> bool:
        return bool(self._state)

    def close(self) -> None:
        self.closed = True

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"MockPin({self.name}, pin={self.pin}, state={self._state}, edges={len(self.history)})"


def _open_devices(led_pin: int, buzzer_pin: int, simulate: bool) -> tuple[object, object, bool]:
    """Return (led, buzzer, hardware) using gpiozero when available and not simulating, else MockPins."""
    if not simulate:
        try:
            from gpiozero import LED, Buzzer  # lazy: Pi-only dependency

            return LED(int(led_pin)), Buzzer(int(buzzer_pin)), True
        except Exception as exc:  # noqa: BLE001 - ImportError or any pin-factory failure off the Pi: fall back
            log.warning("gpiozero unavailable (%s); using MockPin objects, no hardware is driven", exc)
    return MockPin(led_pin, "led"), MockPin(buzzer_pin, "buzzer"), False


# --------------------------------------------------------------------------- pattern specs
def load_marker_patterns(source: str | os.PathLike | Mapping | None = None) -> dict[str, dict]:
    """``{"P1": spec, "P2": spec}`` from ``unit_config.yaml`` ``marker.*`` (or a mapping with that shape).

    Each spec carries ``pulses, on_ms, off_ms`` plus placement keys (``at_s_after_start`` for P1;
    ``mode, at_s_before_end, at_s_after_start`` for P2). Serves section 4.2.
    """
    if source is None:
        source = DEFAULT_UNIT_CONFIG
    if isinstance(source, Mapping):
        data = dict(source)
    else:
        with open(source, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    marker = data.get("marker", data) if isinstance(data, Mapping) else {}
    out: dict[str, dict] = {}
    for name in PATTERN_NAMES:
        key = name.lower()
        if key not in marker:
            raise KeyError(f"marker config lacks pattern '{key}' (have {sorted(marker)})")
        spec = dict(marker[key])
        for req in ("pulses", "on_ms", "off_ms"):
            if req not in spec:
                raise KeyError(f"marker.{key} lacks '{req}'")
        spec["pulses"] = int(spec["pulses"])
        spec["on_ms"] = float(spec["on_ms"])
        spec["off_ms"] = float(spec["off_ms"])
        out[name] = spec
    return out


def pattern_edge_offsets_s(spec: Mapping) -> list[tuple[float, str]]:
    """Edge times relative to the pattern onset: ``[(0.0,'start'), (on,'end'), (on+off,'start'), ...]``."""
    on, off = float(spec["on_ms"]), float(spec["off_ms"])
    edges: list[tuple[float, str]] = []
    for k in range(int(spec["pulses"])):
        t_ms = k * (on + off)                      # accumulate in ms so 100 + 200 + ... stays exact
        edges.append((t_ms / 1e3, "start"))
        edges.append(((t_ms + on) / 1e3, "end"))
    return edges


def pattern_duration_s(spec: Mapping) -> float:
    """Time from the first rising edge to the last falling edge of a pattern, in seconds."""
    return pattern_edge_offsets_s(spec)[-1][0]


def plan_schedule(patterns: Mapping[str, Mapping], t_start_mono_ns: int, video_seconds: float,
                  kardia_duration_s: float | None = None) -> dict:
    """Where P1 and P2 go on the reference clock for one clip (sections 4.2 and 4.3).

    P1 at ``t_start + p1.at_s_after_start``. P2 per ``p2.mode``: ``before_end`` puts it at
    ``t_start + video_seconds - p2.at_s_before_end``; ``after_start`` at ``t_start + p2.at_s_after_start``.
    When ``kardia_duration_s`` is given and the ECG (started no later than P1) would end before P2 finishes,
    P2 falls back to ``after_start`` placement so the fine anchor always lies inside the ECG recording;
    the effective mode is reported. Returns ``{"order": [(mono_ns, name), ...], "p1_mono_ns", "p2_mono_ns",
    "p2_mode", "p2_mode_requested", "overlap"}``.
    """
    p1, p2 = patterns["P1"], patterns["P2"]
    t0 = int(t_start_mono_ns)
    t_p1 = t0 + round(float(p1["at_s_after_start"]) * 1e9)
    mode_req = str(p2.get("mode", "before_end"))
    if mode_req not in P2_MODES:
        raise ValueError(f"p2.mode must be one of {P2_MODES}, got {mode_req!r}")
    mode = mode_req
    if mode == "before_end":
        t_p2 = t0 + round((float(video_seconds) - float(p2["at_s_before_end"])) * 1e9)
    else:
        t_p2 = t0 + round(float(p2["at_s_after_start"]) * 1e9)
    if kardia_duration_s is not None and mode == "before_end":
        ecg_end = t_p1 + round(float(kardia_duration_s) * 1e9)
        if t_p2 + round(pattern_duration_s(p2) * 1e9) > ecg_end:
            log.warning("P2 at t_end-%ss would fall outside a %ss Kardia recording; moving it to t_start+%ss",
                        p2["at_s_before_end"], kardia_duration_s, p2["at_s_after_start"])
            mode = "after_start"
            t_p2 = t0 + round(float(p2["at_s_after_start"]) * 1e9)
    order = sorted([(t_p1, "P1"), (t_p2, "P2")])
    first_end = order[0][0] + round(pattern_duration_s(patterns[order[0][1]]) * 1e9)
    overlap = order[1][0] < first_end
    if overlap:
        log.warning("patterns overlap on this schedule (%s ends after %s starts); the second is emitted late",
                    order[0][1], order[1][1])
    return {"order": order, "p1_mono_ns": t_p1, "p2_mono_ns": t_p2, "p2_mode": mode,
            "p2_mode_requested": mode_req, "overlap": bool(overlap), "t_start_mono_ns": t0,
            "video_seconds": float(video_seconds)}


# --------------------------------------------------------------------------- the marker
class SyncMarker:
    """LED + buzzer marker driven from one call per pattern, logged as edges on the reference clock.

    Parameters: ``led_pin``/``buzzer_pin`` (BCM numbers from ``unit_config.yaml`` ``led.gpio_pin`` /
    ``buzzer.gpio_pin``), ``patterns`` from ``load_marker_patterns``, ``events_csv_path`` for the log
    (header written when the file is new; rows are flushed per edge), ``simulate`` to force MockPins.
    Serves protocol section 4.2 and CONTRACTS section 3.4.
    """

    def __init__(self, led_pin: int, buzzer_pin: int, patterns: Mapping[str, Mapping],
                 events_csv_path: str | os.PathLike, simulate: bool = False):
        self.patterns = {k: dict(v) for k, v in patterns.items()}
        for name in PATTERN_NAMES:
            if name not in self.patterns:
                raise KeyError(f"patterns lack {name}")
        self.events_csv_path = Path(events_csv_path)
        self.simulate = bool(simulate)
        self.led, self.buzzer, self.hardware = _open_devices(led_pin, buzzer_pin, simulate)
        self._lock = threading.Lock()
        self._event_id = 0
        self._fh = None
        self._writer = None
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self.schedule_info: dict | None = None
        self.emitted: dict[str, int] = {}          # pattern -> onset mono_ns of the last emission
        self.rows: list[dict] = []                 # every row written in this process (test and audit aid)
        self._open_log()

    # ------------------------------------------------------------------ log
    def _open_log(self) -> None:
        self.events_csv_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.events_csv_path.exists() or self.events_csv_path.stat().st_size == 0
        if not new:
            with open(self.events_csv_path, "r", encoding="utf-8", newline="") as fh:
                ids = [int(r["event_id"]) for r in csv.DictReader(fh) if str(r.get("event_id", "")).strip()]
            self._event_id = max(ids) if ids else 0
        self._fh = open(self.events_csv_path, "a", encoding="utf-8", newline="")  # noqa: SIM115 - lives for the clip, closed in close()
        self._writer = csv.writer(self._fh)
        if new:
            self._writer.writerow(SYNC_EVENT_COLUMNS)
            self._fh.flush()

    def _log_edge(self, kind: str, pattern: str, t_mono_ns: int, t_wall_ns: int, gpio_ok: bool) -> dict:
        self._event_id += 1
        row = {"event_id": self._event_id, "kind": kind, "pattern": pattern, "mono_ns": int(t_mono_ns),
               "wall_ns": int(t_wall_ns), "gpio_ok": bool(gpio_ok)}
        self._writer.writerow([row[c] for c in SYNC_EVENT_COLUMNS])
        self._fh.flush()
        self.rows.append(row)
        return row

    # ------------------------------------------------------------------ pins
    @property
    def led_is_on(self) -> bool:
        """Current LED state read back from the device (the simulator paints the LED block from this)."""
        return bool(int(self.led.value))

    def _set(self, state: int) -> tuple[int, bool]:
        """Drive both pins to ``state``; return (edge mono_ns, gpio_ok) with gpio_ok from reading both back."""
        t_before = mono_ns()
        if state:
            self.led.on()
            self.buzzer.on()
        else:
            self.led.off()
            self.buzzer.off()
        t_after = mono_ns()
        ok = int(self.led.value) == int(state) and int(self.buzzer.value) == int(state)
        return (t_before + t_after) // 2, ok

    # ------------------------------------------------------------------ emission
    def emit(self, pattern_name: str, onset_mono_ns: int | None = None) -> list[dict]:
        """Emit one pattern on LED and buzzer together; log every edge; return the rows written.

        Edges are timed against the onset (``onset_mono_ns`` or now) rather than cumulatively, so sleep
        overshoot never accumulates across pulses. Serves section 4.2.
        """
        name = str(pattern_name).upper()
        spec = self.patterns[name]
        with self._lock:
            onset = int(onset_mono_ns) if onset_mono_ns is not None else mono_ns()
            rows = []
            for off_s, kind in pattern_edge_offsets_s(spec):
                target = onset + round(off_s * 1e9)
                sleep_until(target, None)
                t_edge, ok = self._set(1 if kind == "start" else 0)
                rows.append(self._log_edge(kind, name, t_edge, wall_ns(), ok))
            self.emitted[name] = onset
            return rows

    def schedule(self, t_start_mono_ns: int, video_seconds: float, kardia_duration_s: float | None = None) -> dict:
        """Plan P1/P2 for a clip starting at ``t_start_mono_ns`` and run them in a background thread.

        Returns the plan from ``plan_schedule`` (mono_ns of each onset, effective P2 mode). ``wait()`` joins
        the thread; ``cancel()`` aborts pending patterns. Serves sections 4.2 and 4.3.
        """
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("a schedule is already running")
        info = plan_schedule(self.patterns, t_start_mono_ns, video_seconds, kardia_duration_s)
        self.schedule_info = info
        self._cancel.clear()
        self._thread = threading.Thread(target=self._run, args=(info["order"],), name="sync_marker", daemon=True)
        self._thread.start()
        return info

    def _run(self, order: list[tuple[int, str]]) -> None:
        for t_on, name in order:
            if not sleep_until(t_on, self._cancel):
                log.info("schedule cancelled before %s", name)
                return
            now = mono_ns()
            if now - t_on > BUSY_WAIT_NS:
                log.warning("%s onset was %.1f ms in the past; emitting from now", name, (now - t_on) / 1e6)
            self.emit(name, onset_mono_ns=max(t_on, now))

    def wait(self, timeout_s: float | None = None) -> bool:
        """Join the schedule thread; True when it has finished."""
        if self._thread is None:
            return True
        self._thread.join(timeout_s)
        return not self._thread.is_alive()

    def cancel(self) -> None:
        self._cancel.set()

    def close(self) -> None:
        """Stop any pending schedule, switch both pins off and close the log and devices."""
        self.cancel()
        if self._thread is not None:
            self._thread.join(2.0)
        try:
            self.led.off()
            self.buzzer.off()
        finally:
            for dev in (self.led, self.buzzer):
                close = getattr(dev, "close", None)
                if close:
                    close()
            if self._fh is not None:
                self._fh.close()
                self._fh = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# --------------------------------------------------------------------------- CLI
def build_marker(unit_config: str | os.PathLike | Mapping | None, events_csv_path: str | os.PathLike,
                 simulate: bool, led_pin: int | None = None, buzzer_pin: int | None = None) -> SyncMarker:
    """Construct a SyncMarker from ``unit_config.yaml`` (pins from ``led.gpio_pin`` / ``buzzer.gpio_pin``)."""
    if unit_config is None:
        unit_config = DEFAULT_UNIT_CONFIG
    if isinstance(unit_config, Mapping):
        ucfg = dict(unit_config)
    else:
        with open(unit_config, "r", encoding="utf-8") as fh:
            ucfg = yaml.safe_load(fh) or {}
    patterns = load_marker_patterns(ucfg)
    lp = int(led_pin if led_pin is not None else ucfg["led"]["gpio_pin"])
    bp = int(buzzer_pin if buzzer_pin is not None else ucfg["buzzer"]["gpio_pin"])
    return SyncMarker(lp, bp, patterns, events_csv_path, simulate=simulate)


def main(argv: list[str] | None = None) -> int:
    """``python -m palmppg.capture.sync_marker [--simulate] --seconds N [--out sync_events.csv]``.

    Runs one full schedule for a clip of ``--seconds`` starting now (P1 at 2 s, P2 at ``N - 5`` s with the
    default config) and exits when the last pattern has finished. Prints a JSON summary. Exit 0 when every
    logged edge passed the GPIO self-check, 3 otherwise.
    """
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--simulate", action="store_true", help="never touch GPIO; use MockPin objects")
    ap.add_argument("--seconds", type=float, default=None, help="clip length driving the schedule (default: unit config)")
    ap.add_argument("--out", default="sync_events.csv", help="events csv path")
    ap.add_argument("--unit-config", default=str(DEFAULT_UNIT_CONFIG))
    ap.add_argument("--kardia-seconds", type=float, default=None, help="Kardia recording length (section 4.3)")
    ap.add_argument("--led-pin", type=int, default=None)
    ap.add_argument("--buzzer-pin", type=int, default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with open(args.unit_config, "r", encoding="utf-8") as fh:
        ucfg = yaml.safe_load(fh) or {}
    seconds = float(args.seconds) if args.seconds is not None else float(ucfg["capture"]["video_seconds"])
    marker = build_marker(ucfg, args.out, simulate=args.simulate, led_pin=args.led_pin, buzzer_pin=args.buzzer_pin)
    try:
        info = marker.schedule(mono_ns(), seconds, args.kardia_seconds)
        marker.wait()
    finally:
        marker.close()
    rows = marker.rows
    summary = {"events_csv": str(marker.events_csv_path), "n_rows": len(rows), "hardware": marker.hardware,
               "p1_mono_ns": info["p1_mono_ns"], "p2_mono_ns": info["p2_mono_ns"], "p2_mode": info["p2_mode"],
               "all_gpio_ok": all(r["gpio_ok"] for r in rows) if rows else False}
    print(json.dumps(summary))
    return 0 if summary["all_gpio_ok"] else 3


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
