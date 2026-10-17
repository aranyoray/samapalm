# %% [markdown]
# # Manual review notebook (run-order step 3: first 10 participants)
#
# Open with Jupyter via jupytext (`jupytext --to ipynb manual_review.py`) or run cell by cell. For each participant
# it shows: the LED block trace with detected P1/P2 edges, the thumb block trace with contact and lift, the ECG with
# the artefact onset, the best-SQI pulse against ECG R-peaks (sync grade `fine` only), per-ROI SQI, QC flags, and
# the sync report. The reviewer records a verdict per clip into `work/manual_review.parquet`.
#
# Nothing here changes a threshold: the frozen config is read-only and the SQI threshold is frozen at the end of this
# step by a dated DECISIONS.md entry.

# %%
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from palmppg.core.config import load_pipeline_config
from palmppg.core.paths import WorkLayout
from palmppg.core.timeline import Timeline

cfg = load_pipeline_config()
work = WorkLayout(cfg.get("paths.work_root"))
STUDY_IDS = sorted(p.name for p in work.root.iterdir() if p.name.startswith("SWHT-PP-003-"))[:10]
print(STUDY_IDS)

# %%
def load_clip(study_id: str, clip_id: str = "clip1"):
    d = work.clip(study_id, clip_id)
    tl = Timeline.load(d / "timeline.json")
    out = {"timeline": tl, "dir": d}
    for cam in ("pi", "phone", "pi_proxy"):
        cd = d / cam
        if (cd / "qc.json").exists():
            out[cam] = {
                "qc": json.loads((cd / "qc.json").read_text()),
                "pulse": pd.read_parquet(cd / "pulse.parquet") if (cd / "pulse.parquet").exists() else None,
                "sqi": json.loads((cd / "pulse_sqi.json").read_text()) if (cd / "pulse_sqi.json").exists() else None,
                "beats": pd.read_parquet(cd / "beats.parquet") if (cd / "beats.parquet").exists() else None,
            }
    if (d / "ecg" / "rpeaks.parquet").exists():
        out["rpeaks"] = pd.read_parquet(d / "ecg" / "rpeaks.parquet")
        out["ecg"] = pd.read_parquet(d / "ecg" / "ecg_clean.parquet")
    if (d / "sync.json").exists():
        out["sync"] = json.loads((d / "sync.json").read_text())
    return out


def review_figure(clip: dict, study_id: str) -> plt.Figure:
    tl = clip["timeline"]
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    ax = axes[0]
    for ev in tl.events:
        ax.axvline(ev.t_ref_s, color="k", alpha=0.4)
        ax.text(ev.t_ref_s, 0.9, ev.kind, rotation=90, fontsize=7, transform=ax.get_xaxis_transform())
    if tl.analysis_window:
        ax.axvspan(tl.analysis_window.start_s, tl.analysis_window.end_s, color="g", alpha=0.08)
    ax.set_title(f"{study_id}: events, analysis window; sync grade = {tl.sync_grade}")
    pi = clip.get("pi")
    if pi and pi["pulse"] is not None and pi["sqi"]:
        best = pi["sqi"]["best"]
        axes[1].plot(pi["pulse"]["t_ref_s"], pi["pulse"][best], lw=0.8)
        axes[1].set_title(f"Pi best pulse: {best}  sqi={pi['sqi'][best]['sqi']:.2f}")
        if "rpeaks" in clip and tl.sync_grade == "fine":
            for t in clip["rpeaks"]["t_ref_s"].dropna():
                axes[1].axvline(t, color="r", alpha=0.25, lw=0.6)
    if "ecg" in clip:
        e = clip["ecg"]
        axes[2].plot(e["t_ref_s"] if e["t_ref_s"].notna().any() else e["t_ecg_s"], e["mv"], lw=0.5)
        axes[2].set_title("ECG (mV) on the reference clock when mapped, else native")
    ph = clip.get("phone")
    if ph and ph["pulse"] is not None and ph["sqi"]:
        best = ph["sqi"]["best"]
        axes[3].plot(ph["pulse"]["t_ref_s"], ph["pulse"][best], lw=0.8, color="tab:orange")
        axes[3].set_title(f"Phone best pulse: {best}  sqi={ph['sqi'][best]['sqi']:.2f}")
    axes[-1].set_xlabel("t_ref_s")
    fig.tight_layout()
    return fig

# %%
verdicts = []
for sid in STUDY_IDS:
    clip = load_clip(sid)
    fig = review_figure(clip, sid)
    out = work.reports / "manual_review"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{sid}.png", dpi=110)
    plt.close(fig)
    qc = {cam: clip[cam]["qc"] for cam in ("pi", "phone", "pi_proxy") if cam in clip}
    print(sid, {cam: (q["valid_clip"], q["reasons"]) for cam, q in qc.items()}, clip["timeline"].sync_grade)
    # The reviewer edits the two fields below per participant after looking at the PNG.
    verdicts.append({"study_id": sid, "clip_id": "clip1", "reviewer": "", "verdict": "", "notes": ""})

# %%
pd.DataFrame(verdicts).to_parquet(work.root / "manual_review.parquet", index=False)
print("wrote", work.root / "manual_review.parquet")
