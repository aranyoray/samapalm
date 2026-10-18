# Interim go/no-go dashboard (first 100; thresholds unchanged)

**Synthetic cohort.** This run measures the pipeline on generated data; it is not a study result.

MST 4-6 n = 9, MST 7-10 n = 19.
## Pilot go/no-go (frozen thresholds)

Frozen config payload sha256: `2e4af62695ea99df88a4d6463a0278b6d3fff3844eb541e489615e4972d1dd81` (frozen on 2026-10-17)

| criterion | threshold | measured | result | note |
|---|---|---|---|---|
| coverage_overall_pct | >= 90 | 56.67 | FAIL |  |
| coverage_drop_points_mst_4_6_minus_7_10 | <= 10 | 25.15 | FAIL | MST 4-6 77.8 vs 7-10 52.6 |
| pulse_rate_within_tolerance_pct_pi | >= 95 | 82.35 | FAIL | tolerance 3 bpm |
| pulse_rate_within_tolerance_pct_phone | >= 95 | 0.00 | report only | reported alongside; not a criterion |
| sbp_error_sd_reduction_temporal_vs_demographics_mmhg | >= 2 | -4.12 | FAIL | demographics-only 13.40 vs temporal 17.52 |

**Decision: NO-GO: stop and report.** Thresholds were read from the signed frozen config and were not modified after seeing results.

Product track alongside (E5, not a criterion):

- phone: SBP SD demographics 13.395223034843784, temporal 16.167603711910505, reduction -2.772380677066721
- pi_proxy: SBP SD demographics 13.395223034843784, temporal 19.03214380025632, reduction -5.636920765412537

At least one frozen criterion failed: the protocol says stop and report.
