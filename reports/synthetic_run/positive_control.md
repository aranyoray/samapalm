# Positive control (default synthetic geometry, seed 1)

Overall: **FAIL**. Truth HR 70.62 bpm; injected AC/DC {'R': 0.0028224000000000005, 'G': 0.00504, 'B': 0.0030492}.

| run | camera | sync | source | HR truth | HR recovered | abs err (bpm) | feet matched | foot median err (frames) | morphology passes | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| crf18 | pi | fine | trace_reference | 70.56 | 70.43 | 0.13 | 62/63 | 0.15 | 4/4 | PASS |
| crf18 | pi_proxy | fine | trace_reference | 70.56 | 70.43 | 0.14 | 61/63 | 0.91 | 3/4 | FAIL |

Failed pipeline stages in crf18: beats_pi, beats_pi_proxy

| crf28 | pi | fine | trace_reference | 70.56 | 70.43 | 0.13 | 62/63 | 0.15 | 4/4 | PASS |
| crf28 | pi_proxy | fine | trace_reference | 70.56 | 30.91 | 39.66 | 1/63 | 1.67 | 0/0 | FAIL |

Failed pipeline stages in crf28: beats_pi, beats_pi_proxy


Tolerances: HR within 1 bpm; foot timing median within one frame; morphology parameters within the configured relative tolerance.
A failing row is reported as it is; nothing is re-tuned on this result.
