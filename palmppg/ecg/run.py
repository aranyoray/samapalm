"""Per-participant ECG processing (protocol 6.4) writing the CONTRACTS section 4 ECG artefacts:

  ecg/ecg_clean.parquet   t_ecg_s (native seconds), t_ref_s (NaN until the sync layer maps it), mv
  ecg/rpeaks.parquet      idx, t_ecg_s, t_ref_s (NaN), detector_agree
  ecg/rate_series.parquet t_ecg_s, bpm   (instantaneous rate at sync.xcorr.rate_fs for the HR xcorr)
  ecg/ecg_features.json   flat dict: rate and rhythm features, app_rhythm_label (covariate),
                          clinician_rhythm (label), ecg_digitised, export_format, artefact summary
  ecg/artefact.json       {onset_t_ecg_s, score, found, ...} for the fine anchor (section 4.3)

The ATC export is used when present, else the PDF strip is digitised (`ecg_digitised = True`). Every
time here is ECG-native; nothing is aligned to the video (that is the sync layer's job, and it never
uses wall clock for it). All features are registered `requires_ecg=True` through `register_features()`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config
from palmppg.core.paths import ParticipantPaths
from palmppg.ecg.artefact import artefact_onset
from palmppg.ecg.atc import ATCError, parse_atc
from palmppg.ecg.clean import clean_ecg, notch
from palmppg.ecg.features import ecg_features, instantaneous_rate, register_features
from palmppg.ecg.labels import load_clinician
from palmppg.ecg.pdf_digitiser import DigitiserError, digitise_pdf
from palmppg.ecg.rpeaks import detect_rpeaks

ECG_CLEAN_NAME = "ecg_clean.parquet"
RPEAKS_NAME = "rpeaks.parquet"
RATE_NAME = "rate_series.parquet"
FEATURES_NAME = "ecg_features.json"
ARTEFACT_NAME = "artefact.json"


class ECGInputError(FileNotFoundError):
    pass


def _json_ready(obj):
    """Numpy and NaN safe JSON conversion (NaN -> null, CONTRACTS 0.11)."""
    if isinstance(obj, dict):
        return {str(k): _json_ready(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_ready(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _json_ready(obj.tolist())
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_json(obj, path: Path) -> Path:
    """Write a per-clip JSON summary (CONTRACTS section 4) with numpy scalars and NaN made JSON-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(obj), indent=2), encoding="utf-8")
    return path


def load_ecg_source(pp: ParticipantPaths, cfg: Config, prefer: str = "atc") -> dict:
    """Pick the ECG export (ATC preferred, PDF fallback) and return {samples_mv, fs, export_format,
    ecg_digitised, source_file, atc (parse result | None), digitiser (result | None), problems}."""
    atc_path, pdf_path = pp.ecg_atc(), pp.ecg_pdf()
    problems: list[str] = []
    order = ("atc", "pdf") if prefer == "atc" else ("pdf", "atc")
    for kind in order:
        if kind == "atc" and atc_path is not None:
            try:
                parsed = parse_atc(atc_path)
            except ATCError as exc:
                problems.append(f"atc unreadable: {exc}")
                continue
            if parsed["n_samples"] == 0:
                problems.append("atc holds no samples")
                continue
            problems.extend(f"atc: {p}" for p in parsed["problems"])
            return {"samples_mv": parsed["samples_mv"], "fs": parsed["fs"], "export_format": "atc",
                    "ecg_digitised": False, "source_file": atc_path.name, "atc": parsed, "digitiser": None,
                    "problems": problems}
        if kind == "pdf" and pdf_path is not None:
            try:
                dig = digitise_pdf(pdf_path, fs_out=float(cfg.get("ecg.fs")))
            except DigitiserError as exc:
                problems.append(f"pdf digitiser failed: {exc}")
                continue
            problems.extend(f"pdf: {p}" for p in dig["quality"]["problems"])
            return {"samples_mv": dig["samples_mv"], "fs": dig["fs"], "export_format": "pdf",
                    "ecg_digitised": True, "source_file": pdf_path.name, "atc": None, "digitiser": dig,
                    "problems": problems}
    raise ECGInputError(f"{pp.study_id}: no usable ECG export under {pp.ecg} ({'; '.join(problems) or 'none found'})")


def default_search_from_s(cfg: Config, ecg_duration_s: float) -> dict:
    """Where to start looking for the fine-anchor artefact in ECG-native time when the sync layer has not
    yet supplied a coarse anchor (section 4.3).

    The lift happens at P2: `study.video_seconds - sync.p2.at_s_before_end` after the clip start (mode
    before_end) or `sync.p2.at_s_after_start` (mode after_start, 30 s Kardia apps). The Kardia starts
    near the clip start, within the coarse-anchor uncertainty plus the xcorr lag window, so the search
    starts that much earlier; when the ECG is shorter than the clip the ECG's own end stands in.
    """
    mode = str(cfg.get("sync.p2.mode", "before_end"))
    if mode == "after_start":
        p2_clip = float(cfg.get("sync.p2.at_s_after_start"))
    else:
        p2_clip = float(cfg.get("study.video_seconds")) - float(cfg.get("sync.p2.at_s_before_end"))
        p2_clip = min(p2_clip, float(ecg_duration_s) - float(cfg.get("sync.p2.at_s_before_end")))
    lead = float(cfg.get("sync.coarse_anchor_uncertainty_s")) + float(cfg.get("sync.xcorr.lag_s"))
    clean_w = float(cfg.get("sync.artefact.clean_window_s"))
    return {"search_from_s": max(clean_w, p2_clip - lead), "p2_expected_ecg_s": p2_clip, "mode": mode}


def process_ecg(participant_paths: ParticipantPaths, work_clip_dir: str | Path, cfg: Config, clip_id: str = "clip1",
                search_from_s: float | None = None, prefer: str = "atc") -> dict:
    """Run the whole ECG chain for one participant and write the ecg/ artefacts (protocol 6.4, 4.3).

    `work_clip_dir` is `work/<study_id>/<clip_id>/`; outputs go to its `ecg/` subfolder. `search_from_s`
    (ECG-native seconds) overrides the default artefact search start (see `default_search_from_s`).
    Returns a summary {paths, export_format, ecg_digitised, fs, n_samples, duration_s, n_peaks,
    agree_frac, hr_mean_bpm, artefact {found, onset_t_ecg_s, score}, clinician_rhythm, problems}.
    """
    pp = participant_paths
    cols = register_features()
    out_dir = Path(work_clip_dir) / "ecg"
    out_dir.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []

    src = load_ecg_source(pp, cfg, prefer=prefer)
    problems.extend(src["problems"])
    mv = np.asarray(src["samples_mv"], dtype=np.float64)
    fs = float(src["fs"])
    n = mv.size
    duration = n / fs
    t_ecg = np.arange(n, dtype=np.float64) / fs
    nan_col = np.full(n, np.nan)

    meta: dict = {}
    if pp.ecg_meta.exists():
        try:
            meta = json.loads(pp.ecg_meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"kardia_meta.json unreadable: {exc}")
    clin: dict | None = None
    if pp.clinician.exists():
        try:
            clin = load_clinician(pp.clinician, cfg)
            problems.extend(f"clinician: {p}" for p in clin["problems"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"clinician.json unreadable: {exc}")
    else:
        problems.append("clinician.json missing")

    # cleaning (ecg.band, ecg.notch_hz) and R-peaks (ecg.detectors, ecg.agreement_ms)
    clean = clean_ecg(mv, fs, cfg=cfg)
    pd.DataFrame({"t_ecg_s": t_ecg, "t_ref_s": nan_col, "mv": clean.astype(np.float32)}).to_parquet(
        out_dir / ECG_CLEAN_NAME, index=False)
    rp = detect_rpeaks(clean, fs, cfg=cfg)
    pd.DataFrame({"idx": rp["idx"].astype(np.int64), "t_ecg_s": rp["t_s"], "t_ref_s": np.full(rp["t_s"].size, np.nan),
                  "detector_agree": rp["agree"].astype(bool)}).to_parquet(out_dir / RPEAKS_NAME, index=False)
    rate_t, rate_bpm = instantaneous_rate(rp["t_s"], cfg=cfg)
    pd.DataFrame({"t_ecg_s": rate_t, "bpm": rate_bpm}).to_parquet(out_dir / RATE_NAME, index=False)

    # fine-anchor artefact (section 4.3) on the mains-notched signal: the notch removes the 50 Hz slew
    # floor while the band-pass is skipped so the lead-off edge keeps its full height and sharpness
    search = default_search_from_s(cfg, duration)
    if search_from_s is not None:
        search["search_from_s"] = float(search_from_s)
        search["source"] = "caller"
    else:
        search["source"] = "default_from_config"
    notched = notch(np.where(np.isfinite(mv), mv, np.nanmedian(mv)), fs, float(cfg.get("ecg.notch_hz")))
    art = artefact_onset(notched, fs, search["search_from_s"], cfg=cfg)
    artefact = {"onset_t_ecg_s": art["onset_t_s"], "score": art["score"], "found": bool(art["found"]),
                "threshold": art["threshold"], "feature": art["feature"], "reason": art["reason"],
                "search_from_s": search["search_from_s"], "search_source": search["source"],
                "p2_expected_ecg_s": search["p2_expected_ecg_s"], "p2_mode": search["mode"],
                "signal": "notched_raw", "thresholds": art.get("thresholds"), "candidates": art.get("candidates")}
    write_json(artefact, out_dir / ARTEFACT_NAME)

    # features on the window before the lift (or before the tail exclusion when no artefact was found)
    tail = float(cfg.get("window.tail_exclusion_s"))
    window_end = float(art["onset_t_s"]) if art["found"] else max(0.0, duration - tail)
    mask = rp["t_s"] < window_end
    feats = ecg_features(rp["t_s"], clean, fs, window_mask=mask, agree=rp["agree"], cfg=cfg)
    second = [m for m in rp["detectors_run"][1:] if rp["per_detector"][m]["error"] is None]
    dig = src["digitiser"]
    atc = src["atc"]
    feats.update({
        "fs": fs, "n_samples": int(n), "ecg_duration_s": float(duration), "ecg_digitised": bool(src["ecg_digitised"]),
        "export_format": src["export_format"], "source_file": src["source_file"],
        "start_time": atc["start_time"].isoformat() if (atc and atc["start_time"] is not None) else None,
        "crc_ok_all": bool(all(atc["crc_ok"].values())) if atc else None,
        "clipped_frac": float(atc["clipped_frac"]) if atc else None,
        "detectors": ";".join(rp["detectors_run"]), "n_peaks_primary": int(rp["n_peaks"]),
        "secondary_matched_frac": float(rp["per_detector"][second[0]]["matched_frac"]) if second else None,
        "artefact_found": bool(art["found"]), "artefact_onset_t_ecg_s": art["onset_t_s"], "artefact_score": art["score"],
        "feature_window_end_s": window_end,
        "app_rhythm_label": meta.get("app_rhythm_label"),
        "clinician_rhythm": clin["rhythm"] if clin else None,
        "clinician_rhythm_unmapped": bool(clin["rhythm_unmapped"]) if clin else None,
        "clinician_ecg_hr": clin["ecg_hr"] if clin else None,
        "hard_non_af": bool(clin["is_hard_non_af"]) if clin else None,
        "digitiser_rows_found": int(dig["rows_found"]) if dig else None,
        "digitiser_px_per_mm": float(dig["calibration"]["px_per_mm"]) if dig else None,
        "digitiser_trace_coverage": float(dig["quality"]["trace_coverage"]) if dig else None,
        "digitiser_skew_deg": float(np.mean(dig["calibration"]["skew_deg"])) if dig else None,
    })
    record = {"study_id": pp.study_id, "clip_id": clip_id, "requires_ecg": True, **feats,
              "export_format_meta": meta.get("export_format"), "problems": problems}
    write_json(record, out_dir / FEATURES_NAME)

    return {
        "study_id": pp.study_id, "clip_id": clip_id, "export_format": src["export_format"],
        "ecg_digitised": bool(src["ecg_digitised"]), "fs": fs, "n_samples": int(n), "duration_s": float(duration),
        "n_peaks": int(rp["n_peaks"]), "agree_frac": rp["agree_frac"], "hr_mean_bpm": feats["hr_mean_bpm"],
        "artefact": {"found": bool(art["found"]), "onset_t_ecg_s": art["onset_t_s"], "score": art["score"]},
        "clinician_rhythm": clin["rhythm"] if clin else None, "registered_columns": len(cols),
        "paths": {"ecg_clean": out_dir / ECG_CLEAN_NAME, "rpeaks": out_dir / RPEAKS_NAME,
                  "rate_series": out_dir / RATE_NAME, "features": out_dir / FEATURES_NAME,
                  "artefact": out_dir / ARTEFACT_NAME},
        "problems": problems,
    }
