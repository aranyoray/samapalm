# SQI threshold calibration against null clips

Synthetic null clips (AC/DC = 0) and synthetic pulse clips at the small test geometry. This calibrates the procedure, not the study threshold, which is frozen at run-order step 3 from bench null recordings on the real unit.

Provisional threshold 0.35. Null quantile 95.

| camera | null n | signal n | null median | null q | signal median | null clips passing provisional | signal clips passing provisional | signal clips at or above null q |
|---|---|---|---|---|---|---|---|---|
| pi | 8 | 30 | 0.296 | 0.384 | 0.662 | 38% | 83% | 80% |
| phone | 8 | 30 | 0.464 | 0.581 | 0.434 | 100% | 97% | 3% |
| pi_proxy | 8 | 30 | 0.381 | 0.556 | 0.377 | 50% | 67% | 3% |

Where the signal median does not exceed the null quantile, the camera path carries no recoverable pulse at this geometry and compression; that is reported as a negative result, not tuned away.
