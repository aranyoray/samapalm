#!/usr/bin/env python3
"""Parse the ATC written by the Android app's own AtcWriter with the pipeline's parser.

The app has to produce files that `palmppg/ecg/atc.py` reads, so this checks the real artefact
rather than a reimplementation: run `./gradlew testDebugUnitTest` first, which leaves
`app/build/atc-roundtrip/kardia_test.atc` and the counts that went into it.

    python3 tools/check_atc_roundtrip.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]  # .../samapalm

# atc.py depends only on numpy and the standard library, but importing it as
# palmppg.ecg.atc drags in the package __init__ and with it pandas. Load the module file
# directly so this check runs anywhere numpy does.
_spec = importlib.util.spec_from_file_location("palmppg_atc", REPO / "palmppg" / "ecg" / "atc.py")
_atc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_atc)
describe, parse_atc = _atc.describe, _atc.parse_atc

ART = HERE.parent / "app" / "build" / "atc-roundtrip"
ATC = ART / "kardia_test.atc"
COUNTS = ART / "expected_counts.csv"
RESOLUTION_NV = 153  # must match AtcWriter.RESOLUTION_NV


def main() -> int:
    if not ATC.exists():
        print(f"missing {ATC}\nrun ./gradlew testDebugUnitTest first")
        return 2

    parsed = parse_atc(ATC)
    print(describe(ATC))

    problems = parsed.get("problems") or []
    expected = np.loadtxt(COUNTS, delimiter=",", skiprows=1, usecols=1).astype(np.int64)

    failures = []
    if problems:
        failures.append(f"parser reported problems: {problems}")
    if parsed["fs"] != 300:
        failures.append(f"fs {parsed['fs']} != 300")
    if parsed["resolution_nv"] != RESOLUTION_NV:
        failures.append(f"resolution {parsed['resolution_nv']} != {RESOLUTION_NV}")
    if len(parsed["raw_int16"]) != len(expected):
        failures.append(f"n samples {len(parsed['raw_int16'])} != {len(expected)}")
    elif not np.array_equal(parsed["raw_int16"].astype(np.int64), expected):
        n_bad = int(np.sum(parsed["raw_int16"].astype(np.int64) != expected))
        failures.append(f"{n_bad} samples differ from what was written")

    # the parser's mV are counts * resolution; confirm the documented 0.27 % offset and no more
    if len(parsed["raw_int16"]) == len(expected):
        exact_mv = expected * (1.0e6 * (10.0 / 65536.0)) / 1.0e6
        read_mv = parsed["samples_mv"].astype(np.float64)
        nz = np.abs(exact_mv) > 1e-6
        if nz.any():
            ratio = float(np.median(read_mv[nz] / exact_mv[nz]))
            print(f"\nmV scale read back / exact provisional scale = {ratio:.6f}")
            if not 1.0025 < ratio < 1.0030:
                failures.append(f"scale ratio {ratio:.6f} outside the documented 1.0027")

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"PASS: {len(expected)} samples round-tripped, fs=300, "
          f"resolution={RESOLUTION_NV} nV/LSB, crc ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
