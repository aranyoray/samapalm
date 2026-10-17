"""TRIPOD+AI checklist (Collins et al., BMJ 2024) as a table that the pipeline fills from its own outputs.

Every item maps to where the pilot addresses it. Items the pilot cannot address (single site, no external
dataset) are stated as such rather than left blank.
"""
from __future__ import annotations

from pathlib import Path

ITEMS: list[tuple[str, str, str]] = [
    ("1", "Title: identify the study as developing or evaluating a prediction model, the target population and the outcome", "reports/README (title block)"),
    ("2", "Abstract: structured summary of objectives, design, setting, participants, outcome, model, results, conclusions", "reports/summary.md"),
    ("3a", "Background: medical context and rationale", "PREREGISTRATION.md: Design"),
    ("3b", "Objectives: development and/or evaluation", "PREREGISTRATION.md: Endpoints"),
    ("4", "Source of data: design, dates, setting", "PREREGISTRATION.md; CONTRACTS.md section 3"),
    ("5a-c", "Participants: eligibility, recruitment, single site", "PREREGISTRATION.md: Design; STARD flow"),
    ("6", "Data preparation: cleaning, QC, exclusions", "qc_table.parquet; reports/stard.md; ingest/qc.py"),
    ("7", "Outcome: definition, timing, blinding", "core/crf.py (bp_target rule); clinician.json rhythm label"),
    ("8", "Predictors: definition, measurement, blinding", "reports/data_dictionary.md; feature registry"),
    ("9", "Sample size: how determined", "PREREGISTRATION.md: pilot n = 500 nested in 8,000; frozen go/no-go"),
    ("10", "Missing data: handling", "features/store.py (nullable columns); abstentions counted as failures"),
    ("11", "Analytical methods: model types, hyperparameters, selection", "configs/experiments/*.yaml; models/zoo.py; experiments/"),
    ("12", "Class imbalance / outcome frequency handling", "eval/metrics.py operating points; rhythm prevalence reported"),
    ("13", "Fairness: evaluation across groups", "audits/equity.py; strata tables per MST band"),
    ("14", "Model output: interpretation, abstain option", "models/uncertainty.py (conformal + abstain)"),
    ("15", "Training vs evaluation data: participant-level splits, no overlap", "features/splits.py; audits/leakage.py"),
    ("16", "Performance measures: discrimination, calibration, clinical utility", "eval/metrics.py; eval/calibration.py"),
    ("17", "Model updating / recalibration", "none performed; no within-person calibration (protocol 11.5)"),
    ("18", "Open science: code, data availability, protocol registration", "this repository; PREREGISTRATION.md"),
    ("19", "Patient and public involvement", "study protocol document (not in this repository)"),
    ("20", "Results: participant flow", "reports/stard.md"),
    ("21", "Model development: parameters, final model specification", "MLflow runs; reports/model_cards/"),
    ("22", "Model performance overall and per stratum with CIs", "reports/strata/*.md"),
    ("23", "Heterogeneity across subgroups and fairness results", "reports/equity.md; audits/equity.py"),
    ("24", "Model usability: inputs, runtime, availability", "reports/model_cards/; capture/phone_settings.md"),
    ("25", "Discussion: limitations, single site, no external dataset", "reports/summary.md (limitations stated)"),
    ("26", "Interpretation: for whom, in what setting", "reports/summary.md"),
    ("27", "Registration, protocol, funding, conflicts", "PREREGISTRATION.md; study protocol document"),
]


def tripod_markdown(status: dict[str, str] | None = None) -> str:
    status = status or {}
    lines = ["# TRIPOD+AI checklist", "", "| item | description | where addressed | status |", "|---|---|---|---|"]
    for item, desc, where in ITEMS:
        lines.append(f"| {item} | {desc} | {where} | {status.get(item, 'pending: filled when the pilot tables exist')} |")
    lines += ["", "Single-site pilot: items about external datasets are answered as not applicable, not as satisfied."]
    return "\n".join(lines) + "\n"


def write_tripod(path: str | Path, status: dict[str, str] | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tripod_markdown(status), encoding="utf-8")
    return path
