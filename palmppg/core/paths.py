"""Study data layout (section 3), work-dir layout, and the locked prospective test stream.

The test stream lives on a separate path and may be read once, at the end, with an access log.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path


class TestStreamAccessDenied(PermissionError):
    pass


@dataclass
class ParticipantPaths:
    study_id: str
    root: Path

    @property
    def crf(self) -> Path:
        return self.root / "crf.json"

    @property
    def clinician(self) -> Path:
        return self.root / "clinician.json"

    @property
    def pi(self) -> Path:
        return self.root / "pi"

    @property
    def phone(self) -> Path:
        return self.root / "phone"

    @property
    def ecg(self) -> Path:
        return self.root / "ecg"

    def clip_ids(self) -> list[str]:
        ids = []
        for p in sorted(self.pi.glob("clip*_meta.json")):
            ids.append(p.name.replace("_meta.json", ""))
        return ids

    def pi_raw(self, clip_id: str = "clip1") -> Path:
        return self.pi / f"{clip_id}.raw"

    def pi_pts(self, clip_id: str = "clip1") -> Path:
        return self.pi / f"{clip_id}_pts.csv"

    def pi_meta(self, clip_id: str = "clip1") -> Path:
        return self.pi / f"{clip_id}_meta.json"

    def sync_events(self, clip_id: str = "clip1") -> Path:
        p = self.pi / f"sync_events_{clip_id}.csv"
        return p if p.exists() or clip_id != "clip1" else self.pi / "sync_events.csv"

    def phone_mp4(self, clip_id: str = "clip1") -> Path:
        return self.phone / f"{clip_id}.mp4"

    def phone_frames(self, clip_id: str = "clip1") -> Path:
        return self.phone / f"{clip_id}_frames.csv"

    def phone_meta(self, clip_id: str = "clip1") -> Path:
        return self.phone / f"{clip_id}_meta.json"

    def ecg_atc(self) -> Path | None:
        hits = sorted(self.ecg.glob("kardia_*.atc"))
        return hits[0] if hits else None

    def ecg_pdf(self) -> Path | None:
        hits = sorted(self.ecg.glob("kardia_*.pdf"))
        return hits[0] if hits else None

    @property
    def ecg_meta(self) -> Path:
        return self.ecg / "kardia_meta.json"

    def parts_present(self) -> dict[str, bool]:
        return {
            "crf": self.crf.exists(), "clinician": self.clinician.exists(),
            "pi": self.pi_raw().exists() and self.pi_pts().exists() and self.pi_meta().exists(),
            "phone": self.phone_mp4().exists() and self.phone_meta().exists(),
            "ecg": (self.ecg_atc() is not None or self.ecg_pdf() is not None) and self.ecg_meta.exists(),
        }


@dataclass
class StudyLayout:
    root: Path

    def __post_init__(self):
        self.root = Path(self.root)

    @property
    def clock_sync_log(self) -> Path:
        return self.root / "clock_sync_log.csv"

    @property
    def units_dir(self) -> Path:
        return self.root / "units"

    def unit(self, unit_id: str) -> Path:
        return self.units_dir / unit_id

    @property
    def participants_dir(self) -> Path:
        return self.root / "participants"

    def participants(self) -> list[ParticipantPaths]:
        if not self.participants_dir.exists():
            return []
        return [ParticipantPaths(p.name, p) for p in sorted(self.participants_dir.iterdir()) if p.is_dir()]

    def participant(self, study_id: str) -> ParticipantPaths:
        return ParticipantPaths(study_id, self.participants_dir / study_id)


@dataclass
class WorkLayout:
    """Cache / derived-data layout: work/<study_id>/<clip_id>/<camera>/..."""

    root: Path

    def __post_init__(self):
        self.root = Path(self.root)

    def clip(self, study_id: str, clip_id: str = "clip1") -> Path:
        p = self.root / study_id / clip_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def camera(self, study_id: str, clip_id: str, camera: str) -> Path:
        p = self.clip(study_id, clip_id) / camera
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def tables(self) -> Path:
        p = self.root / "tables"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def reports(self) -> Path:
        p = self.root / "reports"
        p.mkdir(parents=True, exist_ok=True)
        return p


class TestStreamGuard:
    """Gate on the locked prospective test stream: separate mount, access log, read once."""

    def __init__(self, test_root: str | os.PathLike, log_path: str | os.PathLike | None = None, allow_reads: int = 1):
        self.test_root = Path(test_root)
        self.log_path = Path(log_path) if log_path else self.test_root / "ACCESS_LOG.jsonl"
        self.allow_reads = int(allow_reads)

    def reads_so_far(self) -> int:
        if not self.log_path.exists():
            return 0
        n = 0
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("action") == "read":
                    n += 1
            except json.JSONDecodeError:
                continue
        return n

    def open(self, reason: str, operator: str, frozen_config_sha: str) -> StudyLayout:
        """Append an access-log entry and return the layout; refuse beyond the allowed read count."""
        if not self.test_root.exists():
            raise TestStreamAccessDenied(f"test stream mount {self.test_root} not present")
        n = self.reads_so_far()
        entry = {"ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "operator": operator, "reason": reason,
                 "frozen_config_sha": frozen_config_sha}
        if n >= self.allow_reads:
            entry["action"] = "denied"
            self._append(entry)
            raise TestStreamAccessDenied(f"test stream already read {n} time(s); allowed {self.allow_reads}")
        entry["action"] = "read"
        self._append(entry)
        return StudyLayout(self.test_root)

    def _append(self, entry: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
