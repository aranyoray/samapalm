"""Build configs/crf_fixtures/strata_golden.json: candidate strata keys and server counts with the Python priority,
cell table and most-needed output on the real configs/recruitment_targets.json. The Kotlin StrataGoldenTest must
reproduce every case exactly. Re-run after a targets change and review the diff."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from palmppg.core.strata import cell_table, load_targets, most_needed, priority  # noqa: E402

FULL = {"sex:F": 1000, "sex:M": 1000, **{f"mst:{b}": 200 for b in range(4, 11)}}
MIDWAY = {"sex:F": 400, "sex:M": 700, "mst:4": 150, "mst:5": 180, "mst:6": 90, "mst:7": 40, "mst:8": 10, "mst:9": 2,
          "cond:htn": 210, "cond:af": 40, "cond:diabetes": 330, "haem:thal_trait": 75, "haem:ida": 149,
          "haem:non_anaemic": 300, "sex_mst:F:8": 5, "sex_mst:M:5": 100, "cond_mstgrp:af:dark": 12,
          "haem_mstgrp:ida:dark": 50, "rhythm:af": 30, "rhythm:nsr": 480}

CASES = [
    ("no_keys", [], MIDWAY),
    ("only_unknown_keys", ["mst:2", "mstgrp:light", "dm:no_known", "preg:yes"], MIDWAY),
    ("empty_counts_male_dark_af", ["sex:M", "mst:8", "mstgrp:dark", "cond:af", "dm:no_known", "sex_mst:M:8", "cond_mstgrp:af:dark"], {}),
    ("all_met", ["sex:F", "mst:6", "mstgrp:medium"], FULL),
    ("midway_female_mst8_af", ["sex:F", "mst:8", "mstgrp:dark", "cond:af", "dm:no_known", "sex_mst:F:8", "cond_mstgrp:af:dark"], MIDWAY),
    ("midway_male_mst5_htn", ["sex:M", "mst:5", "mstgrp:medium", "cond:htn", "dm:no_known", "sex_mst:M:5", "cond_mstgrp:htn:medium"], MIDWAY),
    ("medium_level", ["sex:M", "mst:4", "mstgrp:light"], {"sex:M": 700, "mst:4": 150}),
    ("low_level", ["sex:M", "mst:4", "mstgrp:light"], {"sex:M": 900, "mst:4": 190}),
    ("high_boundary_exact", ["sex:F"], {"sex:F": 500}),
    ("medium_boundary_float_rounding", ["sex:F"], {"sex:F": 800}),
    ("only_the_weighted_cell_unfilled", ["sex:F", "mst:7", "sex_mst:F:7"], {"sex:F": 1000, "mst:7": 200, "sex_mst:F:7": 0}),
    ("tie_ordering_by_key", ["mst:9", "mst:10", "mst:4"], {"mst:9": 100, "mst:10": 100, "mst:4": 100}),
    ("over_target_counts_clip_at_zero", ["sex:F", "haem:ida"], {"sex:F": 1200, "haem:ida": 400}),
    ("thal_trait_dark", ["sex:F", "mst:9", "mstgrp:dark", "cond:thal", "haem:thal_trait", "dm:no_known", "sex_mst:F:9",
                         "cond_mstgrp:thal:dark", "haem_mstgrp:thal_trait:dark"], MIDWAY),
    ("scan_keys_weight_zero", ["rhythm:af", "scan:done"], MIDWAY),
    ("duplicate_keys_counted_once", ["cond:htn", "cond:htn", "sex:M"], MIDWAY),
]


def main():
    targets = load_targets()
    cases = [{"name": n, "keys": k, "counts": c, "expected": priority(k, c, targets)} for n, k, c in CASES]
    tables = [("midway", MIDWAY, 5), ("empty", {}, 3), ("full_sex_mst", FULL, 4)]
    out = {"targets_version": targets["version"], "cases": cases,
           "tables": [{"name": n, "counts": c, "k": k, "cell_table": cell_table(c, targets), "most_needed": most_needed(c, targets, k)}
                      for n, c, k in tables]}
    path = ROOT / "configs" / "crf_fixtures" / "strata_golden.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(cases)} priority cases, {len(out['tables'])} tables)")


if __name__ == "__main__":
    main()
