> Synthetic cohort: these pages measure the pipeline on generated data and are not study results.

# STARD flow (pilot)

```mermaid
flowchart TD
  A["Enrolled, CRF complete: n=30 (valid CRF 30)"]
  B["Palm clip captured: n=30 (re-shoots 0)"]
  C["Valid Pi clip: n=17<br/>Valid phone clip: n=29"]
  D["Sync grade fine 14 / coarse 15 / none 1"]
  E["ECG readable: n=29 (digitised from PDF 0)"]
  F["BP analysed: n=17; abstained 0 (counted as failures)"]
  G["Rhythm analysed: n=17"]
  A --> B --> C --> D --> E
  E --> F
  E --> G
```

## Exclusion reasons (Pi, first clip)

| reason | n |
|---|---|
| flicker_flag | 10 |
| sqi_flag | 5 |

Failed and abstained readings are failures in every coverage figure.
