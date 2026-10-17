"""Model cards for every reported model, with the track stated first."""
from __future__ import annotations

from pathlib import Path


def model_card_markdown(name: str, track: str, task: str, inputs: list[str], training: dict, metrics_overall: dict,
                        strata_paths: list[str], baselines: dict, limitations: list[str], seeds: list[int],
                        config_sha: str, data_sha: str) -> str:
    assert track in ("product_candidate", "science")
    lines = [f"# Model card: {name}", "", f"**Track:** `{track}`" + ("" if track == "product_candidate" else " (not a product result)"),
             f"**Task:** {task}", "", "## Inputs", ""]
    lines += [f"- {c}" for c in inputs] or ["- none listed"]
    lines += ["", "## Training", ""] + [f"- {k}: {v}" for k, v in training.items()]
    lines += ["", "## Measured performance (overall)", "", "| metric | model | predict-the-mean | demographics-only |", "|---|---|---|---|"]
    for k, v in metrics_overall.items():
        pm = baselines.get("predict_mean", {}).get(k, "")
        dm = baselines.get("demographics_only", {}).get(k, "")
        lines.append(f"| {k} | {v} | {pm} | {dm} |")
    lines += ["", "## Per-stratum tables", ""] + [f"- {p}" for p in strata_paths]
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in (limitations + ["Single site, one visit per participant, cuff reference bracketing the clip."])]
    lines += ["", f"Seeds: {seeds}. Config sha256: `{config_sha}`. Data manifest sha256: `{data_sha}`.", ""]
    return "\n".join(lines)


def write_model_card(path: str | Path, **kw) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model_card_markdown(**kw), encoding="utf-8")
    return path
