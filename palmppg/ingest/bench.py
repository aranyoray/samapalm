"""Bench acceptance of the sync chain (protocol section 4.5) and the synthetic self-test of the detectors.

Section 4.5: twenty trials with a flashing marker in the aperture; both cameras and the Pi log must agree
on the LED onsets within one frame; the audio onset within ``sync.audio.onset_tolerance_ms`` of the Pi
log; a simulated ECG artefact (tap on the card) aligns within one frame. ``bench_trials_report`` scores a
list of trials (hardware captures prepared by the operator tooling, or the synthetic trials made here) and
writes the one-page markdown report. Its header states which of the two it is.

``synthetic_bench_selftest`` is the only part that can run without hardware: it generates LED block traces,
audio and artefact pairs with known offsets, drift and jitter, runs the real detectors and fits, and
scores the recovered values against the truth. It exercises the detectors; it says nothing about the
cameras, the buzzer or the GPIO timing, and the report says so.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from palmppg.core.config import REPO_ROOT, Config, load_pipeline_config, rng
from palmppg.ingest import anchors as _anchors
from palmppg.ingest import audio as _audio
from palmppg.ingest import led as _led
from palmppg.ingest.sync_events import pattern_edges, pattern_specs

DEFAULT_REPORT_PATH = REPO_ROOT / "reports" / "bench_sync_report.md"


# --------------------------------------------------------------------------- synthetic signal generators
def on_intervals(onsets_s: Mapping[str, float], specs: Mapping[str, Mapping]) -> list[tuple[float, float]]:
    """LED/buzzer on-intervals ``[(t_on, t_off), ...]`` for patterns fired at ``onsets_s``."""
    out: list[tuple[float, float]] = []
    for name, t0 in onsets_s.items():
        edges = pattern_edges(t0, specs[name])
        for (a, ka), (b, kb) in zip(edges[::2], edges[1::2]):
            out.append((a, b))
    return sorted(out)


def integrated_on_fraction(t_exposure_start: np.ndarray, exposure_s: float,
                           intervals: Sequence[tuple[float, float]]) -> np.ndarray:
    """Fraction of each exposure window ``[t, t + exposure_s]`` during which the source is on.
    ``exposure_s == 0`` samples the state at ``t``. This is the camera model used in the self-test:
    a sensor integrates light over its exposure, so an edge inside the exposure gives a partial frame."""
    t = np.asarray(t_exposure_start, dtype=float)
    frac = np.zeros_like(t)
    if exposure_s <= 0:
        for a, b in intervals:
            frac += ((t >= a) & (t < b)).astype(float)
        return np.clip(frac, 0, 1)
    for a, b in intervals:
        frac += np.clip(np.minimum(t + exposure_s, b) - np.maximum(t, a), 0.0, None) / exposure_s
    return np.clip(frac, 0, 1)


def synth_led_trace(t_native_s: np.ndarray, intervals_ref: Sequence[tuple[float, float]], offset_s: float = 0.0,
                    drift: float = 0.0, exposure_s: float = 0.0, lo: float = 100.0, hi: float = 400.0,
                    noise_sd: float = 2.0, gen: np.random.Generator | None = None) -> np.ndarray:
    """LED block intensity per frame for a camera whose frame times ``t_native_s`` map to the reference
    clock as ``t_ref = t_native * (1 + drift) + offset_s`` (the ClockMap convention)."""
    gen = gen or rng(0, "synth_led")
    t_ref = np.asarray(t_native_s, dtype=float) * (1.0 + drift) + offset_s
    frac = integrated_on_fraction(t_ref, exposure_s * (1.0 + drift), intervals_ref)
    return lo + (hi - lo) * frac + gen.normal(0.0, noise_sd, size=frac.shape)


def synth_audio(fs: float, duration_s: float, intervals_s: Sequence[tuple[float, float]], tone_hz: float,
                amplitude: float = 0.3, noise_sd: float = 0.1, rise_s: float = 0.0,
                gen: np.random.Generator | None = None) -> np.ndarray:
    """Mono audio with tone bursts on ``intervals_s`` (audio-stream seconds) plus white noise."""
    gen = gen or rng(0, "synth_audio")
    n = round(duration_s * fs)
    t = np.arange(n) / fs
    x = gen.normal(0.0, noise_sd, size=n)
    for a, b in intervals_s:
        env = np.clip((t - a) / rise_s, 0, 1) if rise_s > 0 else (t >= a).astype(float)
        env = env * (t < b)
        phase = gen.uniform(0, 2 * np.pi)
        x += amplitude * env * np.sin(2 * np.pi * tone_hz * t + phase)
    return x


def synth_thumb_trace(t_s: np.ndarray, contact_t: float, lift_t: float, lift_duration_s: float = 0.8,
                      base: float = 300.0, contact_shift: float = -60.0, lift_jump: float = 35.0,
                      noise_sd: float = 3.0, gen: np.random.Generator | None = None) -> np.ndarray:
    """Thumb block trace: level step at ``contact_t`` (thumb lands), transient bump for ``lift_duration_s``
    from ``lift_t`` (lift and put back), Gaussian noise."""
    gen = gen or rng(0, "synth_thumb")
    t = np.asarray(t_s, dtype=float)
    y = base + contact_shift * (t >= contact_t) + lift_jump * ((t >= lift_t) & (t < lift_t + lift_duration_s))
    return y + gen.normal(0.0, noise_sd, size=t.shape)


# --------------------------------------------------------------------------- scoring one trial
def evaluate_trial(trial: Mapping, cfg: Config) -> dict:
    """Score one bench trial against the section 4.5 criteria.

    Trial keys: ``fps`` (Pi), ``phone_fps``, ``pi_log_edges`` ``{pattern: [(t_ref_s, kind)]}``,
    ``pi_video_edges`` / ``phone_video_edges`` / ``audio_edges`` ``{pattern: [edge dicts]}`` or None,
    ``artefact`` ``{"pairs": [(video_t_ref_s, ecg_t_ecg_s), ...], "true_offset_s": float | None}`` or None,
    and, for synthetic trials, ``truth`` ``{phone_offset_s, phone_drift, audio_offset_s}``.
    Criteria: Pi video and phone video edges within one frame of the log after one offset (+ drift);
    audio within ``sync.audio.onset_tolerance_ms``; artefact pair within one frame (``fine_anchor_uncertainty_s``).
    """
    fps = float(trial.get("fps", 30.0))
    phone_fps = float(trial.get("phone_fps", fps))
    tol_frames = float(cfg.get("sync.edge_tolerance_frames"))
    min_edges = int(cfg.get("sync.min_edges"))
    audio_tol_ms = float(cfg.get("sync.audio.onset_tolerance_ms"))
    frame_unc = float(cfg.get("sync.fine_anchor_uncertainty_s"))
    truth = dict(trial.get("truth") or {})
    log = trial["pi_log_edges"]
    out: dict = {"trial_id": trial.get("trial_id"), "criteria": {}}

    def _led_crit(name: str, edges, stream: str, f: float, truth_offset: float | None, truth_drift: float | None):
        if not edges:
            out["criteria"][name] = {"pass": False, "reason": "no edges detected", "residual_max_frames": None}
            return
        cm, rep = _led.fit_led_offset(edges, log, stream, f, tol_frames, min_edges)
        crit = {"pass": bool(rep["accepted"]), "residual_max_frames": rep["residual_max_frames"],
                "n_matched": rep["n_matched"], "offset_s": rep["offset_s"], "drift": rep["drift"], "reason": rep["reason"]}
        if cm is not None and truth_offset is not None:
            err = abs(cm.offset_s - truth_offset)
            crit["offset_error_frames"] = float(err * f)
            crit["pass"] = crit["pass"] and err * f <= tol_frames
        if cm is not None and truth_drift is not None:
            crit["drift_error"] = float(abs(cm.drift - truth_drift))
        out["criteria"][name] = crit

    _led_crit("pi_video", trial.get("pi_video_edges"), "pi_video", fps, 0.0 if truth else None, None)
    _led_crit("phone_video", trial.get("phone_video_edges"), "phone_video", phone_fps,
              truth.get("phone_offset_s"), truth.get("phone_drift"))

    aud = trial.get("audio_edges")
    if not aud:
        out["criteria"]["audio"] = {"pass": False, "reason": "no beeps detected", "residual_max_ms": None}
    else:
        cm, rep = _led.fit_led_offset(aud, log, "phone_audio", phone_fps, tol_frames, min_edges, method="audio_beep")
        res_ms = None if rep["residual_max_s"] is None else 1e3 * rep["residual_max_s"]
        ok = rep["n_matched"] >= min_edges and res_ms is not None and res_ms <= audio_tol_ms
        crit = {"pass": bool(ok), "residual_max_ms": res_ms, "n_matched": rep["n_matched"], "offset_s": rep["offset_s"],
                "reason": rep["reason"]}
        if cm is not None and truth.get("audio_offset_s") is not None:
            err_ms = 1e3 * abs(cm.offset_s - float(truth["audio_offset_s"]))
            crit["offset_error_ms"] = float(err_ms)
            crit["pass"] = crit["pass"] and err_ms <= audio_tol_ms
        out["criteria"]["audio"] = crit

    art = trial.get("artefact")
    if not art or not art.get("pairs"):
        out["criteria"]["artefact"] = {"pass": False, "reason": "no artefact pair", "error_frames": None}
    else:
        pairs = np.asarray(art["pairs"], dtype=float)
        offs = pairs[:, 0] - pairs[:, 1]
        if art.get("true_offset_s") is not None:
            err = float(np.max(np.abs(offs - float(art["true_offset_s"]))))
            crit = {"pass": bool(err <= frame_unc), "error_frames": float(err / frame_unc), "n_pairs": len(pairs),
                    "reason": "offset error vs known truth"}
        elif len(pairs) >= 2:
            err = float(np.max(np.abs(offs - np.mean(offs))))
            crit = {"pass": bool(err <= frame_unc), "error_frames": float(err / frame_unc), "n_pairs": len(pairs),
                    "reason": "spread of the per-tap offsets about their mean"}
        else:
            crit = {"pass": None, "error_frames": None, "n_pairs": 1,
                    "reason": "one tap only: an offset can be formed but not checked; record two taps per trial"}
        out["criteria"]["artefact"] = crit
    out["pass"] = all(c["pass"] for c in out["criteria"].values() if c["pass"] is not None) and \
        all(c["pass"] is not None for c in out["criteria"].values())
    return out


# --------------------------------------------------------------------------- the markdown report
def _fmt(v, nd=2):
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "pass" if v else "FAIL"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return f"{float(v):.{nd}f}"


def bench_trials_report(trials: Sequence[Mapping], cfg: Config | None = None, hardware: bool = True,
                        out_path: str | Path | None = DEFAULT_REPORT_PATH, title: str | None = None) -> str:
    """Score bench trials and write the one-page markdown report (section 4.5).

    ``hardware=True`` labels the trials as hardware captures (the acceptance that must pass before any
    patient); ``hardware=False`` labels them as the synthetic self-test, which exercises the detectors only.
    Returns the markdown; writes it to ``out_path`` when given (default ``reports/bench_sync_report.md``).
    The text reports measured numbers only.
    """
    cfg = cfg or load_pipeline_config()
    results = [evaluate_trial(t, cfg) for t in trials]
    n = len(results)
    crits = ("pi_video", "phone_video", "audio", "artefact")
    n_pass = {c: sum(1 for r in results if r["criteria"][c]["pass"] is True) for c in crits}
    n_checkable = {c: sum(1 for r in results if r["criteria"][c]["pass"] is not None) for c in crits}
    overall = sum(1 for r in results if r["pass"])
    mode = ("HARDWARE CAPTURES: metronome flash in the aperture, both cameras, Pi log, buzzer and a card tap"
            if hardware else
            "SYNTHETIC SELF-TEST: generated LED traces, audio and artefact pairs with known offsets, drift and jitter; "
            "no camera, buzzer or GPIO was involved. This exercises the detectors and fits only.")
    today = dt.date.today().isoformat()
    L: list[str] = []
    L.append(f"# {title or 'Sync bench report'} (SWHT-PP-003, protocol section 4.5)")
    L.append("")
    L.append(f"Generated {today}. Trials: {n}. Source: **{mode}**")
    L.append("")
    L.append("## Acceptance criteria (from configs/pipeline.yaml)")
    L.append("")
    L.append(f"- LED onsets: Pi video and phone video edges within {cfg.get('sync.edge_tolerance_frames')} frame period(s) of the "
             f"Pi log after one offset (+ drift when >= 4 edges), at least {cfg.get('sync.min_edges')} edges matched (D-003).")
    L.append(f"- Audio: beep edges within {cfg.get('sync.audio.onset_tolerance_ms')} ms of the Pi log after one offset.")
    L.append(f"- Artefact: card-tap pair (video event vs ECG artefact) within {cfg.get('sync.fine_anchor_uncertainty_s')} s (one frame).")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append("| criterion | pass | checkable | trials |")
    L.append("|---|---|---|---|")
    for c in crits:
        L.append(f"| {c} | {n_pass[c]} | {n_checkable[c]} | {n} |")
    L.append(f"| **all four** | **{overall}** | {n} | {n} |")
    L.append("")
    verdict = "ACCEPTED" if n > 0 and overall == n else "NOT ACCEPTED"
    L.append(f"Overall: {overall}/{n} trials pass every criterion: **{verdict}**"
             + ("" if hardware else " (synthetic self-test; hardware acceptance still outstanding)"))
    L.append("")
    L.append("## Per-trial results")
    L.append("")
    L.append("| trial | Pi video max resid (frames) | phone video max resid (frames) | phone offset err (frames) | "
             "phone drift | audio max resid (ms) | audio offset err (ms) | artefact err (frames) | pass |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        c = r["criteria"]
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["trial_id"], _fmt(c["pi_video"].get("residual_max_frames")), _fmt(c["phone_video"].get("residual_max_frames")),
            _fmt(c["phone_video"].get("offset_error_frames")), _fmt(c["phone_video"].get("drift"), 6),
            _fmt(c["audio"].get("residual_max_ms")), _fmt(c["audio"].get("offset_error_ms")),
            _fmt(c["artefact"].get("error_frames")), "pass" if r["pass"] else "FAIL"))
    L.append("")
    fails = [(r["trial_id"], c, r["criteria"][c].get("reason")) for r in results for c in crits
             if r["criteria"][c]["pass"] is False]
    if fails:
        L.append("## Failing criteria")
        L.append("")
        for tid, c, reason in fails:
            L.append(f"- trial {tid}, {c}: {reason}")
        L.append("")
    L.append("## What this report shows")
    L.append("")
    if hardware:
        L.append("Measured agreement between the Pi GPIO log, the Pi camera, the phone camera, the phone microphone and "
                 "the ECG artefact on the bench rig. It is the acceptance gate before the first participant "
                 "(run order step 2). Numbers are what was measured on these trials; nothing is extrapolated.")
    else:
        L.append("Recovery of known offsets by the detector and fitting code on generated signals. It is a software "
                 "self-test and is labelled as such; it does not stand in for the hardware bench acceptance, which "
                 "must be run on the rig and reported with `hardware=True`.")
    md = "\n".join(L) + "\n"
    if out_path is not None:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
    return md


# --------------------------------------------------------------------------- synthetic self-test
def make_synthetic_trial(trial_id: int, cfg: Config, gen: np.random.Generator, clip_s: float = 12.0,
                         fs_audio: float = 48000.0) -> dict:
    """One synthetic trial with known truth: Pi trace (identity, short exposure), phone trace (offset,
    drift, full-frame exposure, PTS jitter), audio (offset, noise), thumb-lift/ECG-artefact pairs."""
    fps = float(cfg.get("pi.nominal_fps"))
    phone_fps = float(cfg.get("phone.nominal_fps"))
    specs = pattern_specs(cfg)
    p1_on = float(cfg.get("sync.p1.at_s_after_start")) + gen.uniform(-0.02, 0.02)
    p2_on = clip_s - float(cfg.get("sync.p2.at_s_before_end")) + gen.uniform(-0.02, 0.02)
    onsets = {"P1": p1_on, "P2": p2_on}
    intervals = on_intervals(onsets, specs)
    log = {name: pattern_edges(t, specs[name]) for name, t in onsets.items()}
    truth = {"phone_offset_s": float(gen.uniform(-1.5, 1.5)), "phone_drift": float(gen.uniform(-1e-4, 1e-4)),
             "audio_offset_s": float(gen.uniform(-0.5, 0.5)), "audio_start_offset_s": float(gen.uniform(0.0, 0.05))}
    # Pi: exposure 8 ms, timestamps at exposure start
    pi_exp = float(cfg.get("pi.nominal_fps") and 0.008)
    n_pi = int(clip_s * fps)
    t_pi = np.arange(n_pi) / fps + gen.uniform(-2e-4, 2e-4, size=n_pi)
    y_pi = synth_led_trace(t_pi, intervals, 0.0, 0.0, pi_exp, 90.0, 380.0, 3.0, gen)
    det_pi = {k: d for k, d in ((k, _led.detect_pattern(t_pi, y_pi, s, fps, exposure_s=pi_exp)) for k, s in specs.items()) if d}
    # phone: native frames; LED state from the reference clock through the true map
    n_ph = int(clip_s * phone_fps) + 60
    t_ph = np.arange(n_ph) / phone_fps + gen.uniform(-5e-4, 5e-4, size=n_ph)
    ph_exp = 0.9 / phone_fps
    y_ph = synth_led_trace(t_ph, intervals, truth["phone_offset_s"], truth["phone_drift"], ph_exp, 40.0, 220.0, 2.5, gen)
    det_ph = {k: d for k, d in ((k, _led.detect_pattern(t_ph, y_ph, s, phone_fps, exposure_s=ph_exp)) for k, s in specs.items()) if d}
    # audio: video time = audio time + start offset; ref = video + audio_offset
    tone = float(cfg.get("sync.audio.tone_hz"))
    a_int = [(a - truth["audio_offset_s"] - truth["audio_start_offset_s"], b - truth["audio_offset_s"] - truth["audio_start_offset_s"])
             for a, b in intervals]
    x = synth_audio(fs_audio, clip_s + 1.0, a_int, tone, 0.3, 0.1, 0.0, gen)
    beeps = _audio.detect_beeps(x, fs_audio, tone, float(cfg.get("sync.audio.bandwidth_hz")), specs,
                                audio_start_offset_s=truth["audio_start_offset_s"])
    # artefact: two taps near P2, ECG clock offset known
    ecg_off = float(gen.uniform(-3.0, 3.0))
    taps = [p2_on + 0.6 + gen.uniform(0, 0.2), p2_on + 2.5 + gen.uniform(0, 0.2)]
    pairs = []
    win = cfg.get("sync.lift.search_s", _anchors.DEFAULTS["sync.lift.search_s"])
    for j, tap in enumerate(taps):
        y_th = synth_thumb_trace(t_pi, 0.5, tap, 0.8, 300.0, -60.0, 35.0, 3.0, gen)
        w0 = p2_on + float(win[0]) + (0.0 if j == 0 else 1.9)
        ev = _anchors.thumb_lift_event(t_pi, y_th, (w0, p2_on + float(win[1])), k_mad=float(cfg.get("sync.artefact.k_mad")))
        if ev["found"]:
            # ECG sees the tap at the same instant on its own clock, with sub-sample jitter
            pairs.append((ev["t_s"], tap - ecg_off + gen.uniform(-0.003, 0.003)))
    return {
        "trial_id": trial_id, "fps": fps, "phone_fps": phone_fps, "pi_log_edges": log,
        "pi_video_edges": det_pi or None, "phone_video_edges": det_ph or None, "audio_edges": _audio.beep_edges(beeps) or None,
        "artefact": {"pairs": pairs, "true_offset_s": ecg_off}, "truth": truth, "onsets_s": onsets,
    }


def synthetic_bench_selftest(n_trials: int = 20, seed: int | None = None, cfg: Config | None = None,
                             out_path: str | Path | None = DEFAULT_REPORT_PATH, clip_s: float = 12.0) -> dict:
    """Generate ``n_trials`` synthetic trials, run the detectors and fits, score them and write the report
    labelled as the synthetic self-test (section 4.5; software only). Returns ``{n_trials, n_pass, results,
    markdown, trials}``."""
    cfg = cfg or load_pipeline_config()
    seed = int(cfg.get("study.seed")) if seed is None else int(seed)
    gen = rng(seed, "bench_selftest")
    trials = [make_synthetic_trial(i + 1, cfg, gen, clip_s=clip_s) for i in range(int(n_trials))]
    md = bench_trials_report(trials, cfg, hardware=False, out_path=out_path, title="Sync bench self-test")
    results = [evaluate_trial(t, cfg) for t in trials]
    return {"n_trials": len(trials), "n_pass": sum(1 for r in results if r["pass"]), "results": results,
            "markdown": md, "trials": trials, "seed": seed}


if __name__ == "__main__":  # pragma: no cover - manual entry point
    res = synthetic_bench_selftest()
    print(f"synthetic self-test: {res['n_pass']}/{res['n_trials']} trials pass; report at {DEFAULT_REPORT_PATH}")
