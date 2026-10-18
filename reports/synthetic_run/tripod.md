> Synthetic cohort: these pages measure the pipeline on generated data and are not study results.

# TRIPOD+AI checklist

| item | description | where addressed | status |
|---|---|---|---|
| 1 | Title: identify the study as developing or evaluating a prediction model, the target population and the outcome | reports/README (title block) | pending: filled when the pilot tables exist |
| 2 | Abstract: structured summary of objectives, design, setting, participants, outcome, model, results, conclusions | reports/summary.md | pending: filled when the pilot tables exist |
| 3a | Background: medical context and rationale | PREREGISTRATION.md: Design | pending: filled when the pilot tables exist |
| 3b | Objectives: development and/or evaluation | PREREGISTRATION.md: Endpoints | pending: filled when the pilot tables exist |
| 4 | Source of data: design, dates, setting | PREREGISTRATION.md; CONTRACTS.md section 3 | pending: filled when the pilot tables exist |
| 5a-c | Participants: eligibility, recruitment, single site | PREREGISTRATION.md: Design; STARD flow | pending: filled when the pilot tables exist |
| 6 | Data preparation: cleaning, QC, exclusions | qc_table.parquet; reports/stard.md; ingest/qc.py | pending: filled when the pilot tables exist |
| 7 | Outcome: definition, timing, blinding | core/crf.py (bp_target rule); clinician.json rhythm label | pending: filled when the pilot tables exist |
| 8 | Predictors: definition, measurement, blinding | reports/data_dictionary.md; feature registry | pending: filled when the pilot tables exist |
| 9 | Sample size: how determined | PREREGISTRATION.md: pilot n = 500 nested in 8,000; frozen go/no-go | pending: filled when the pilot tables exist |
| 10 | Missing data: handling | features/store.py (nullable columns); abstentions counted as failures | pending: filled when the pilot tables exist |
| 11 | Analytical methods: model types, hyperparameters, selection | configs/experiments/*.yaml; models/zoo.py; experiments/ | pending: filled when the pilot tables exist |
| 12 | Class imbalance / outcome frequency handling | eval/metrics.py operating points; rhythm prevalence reported | pending: filled when the pilot tables exist |
| 13 | Fairness: evaluation across groups | audits/equity.py; strata tables per MST band | pending: filled when the pilot tables exist |
| 14 | Model output: interpretation, abstain option | models/uncertainty.py (conformal + abstain) | pending: filled when the pilot tables exist |
| 15 | Training vs evaluation data: participant-level splits, no overlap | features/splits.py; audits/leakage.py | pending: filled when the pilot tables exist |
| 16 | Performance measures: discrimination, calibration, clinical utility | eval/metrics.py; eval/calibration.py | pending: filled when the pilot tables exist |
| 17 | Model updating / recalibration | none performed; no within-person calibration (protocol 11.5) | pending: filled when the pilot tables exist |
| 18 | Open science: code, data availability, protocol registration | this repository; PREREGISTRATION.md | pending: filled when the pilot tables exist |
| 19 | Patient and public involvement | study protocol document (not in this repository) | pending: filled when the pilot tables exist |
| 20 | Results: participant flow | reports/stard.md | pending: filled when the pilot tables exist |
| 21 | Model development: parameters, final model specification | MLflow runs; reports/model_cards/ | pending: filled when the pilot tables exist |
| 22 | Model performance overall and per stratum with CIs | reports/strata/*.md | pending: filled when the pilot tables exist |
| 23 | Heterogeneity across subgroups and fairness results | reports/equity.md; audits/equity.py | pending: filled when the pilot tables exist |
| 24 | Model usability: inputs, runtime, availability | reports/model_cards/; capture/phone_settings.md | pending: filled when the pilot tables exist |
| 25 | Discussion: limitations, single site, no external dataset | reports/summary.md (limitations stated) | pending: filled when the pilot tables exist |
| 26 | Interpretation: for whom, in what setting | reports/summary.md | pending: filled when the pilot tables exist |
| 27 | Registration, protocol, funding, conflicts | PREREGISTRATION.md; study protocol document | pending: filled when the pilot tables exist |

Single-site pilot: items about external datasets are answered as not applicable, not as satisfied.
