"""ECGFounder preprocessing (no torch): the chain that turns a strip into model input, and the golden fixtures
that pin the Kotlin port in android/ecg-model."""
import base64
import json
from pathlib import Path

import numpy as np
import pytest

from palmppg.ecg import founder_prep as fp

ROOT = Path(__file__).resolve().parents[1]
FX_PATH = ROOT / "configs" / "founder_fixtures" / "preprocess.json"
FX = json.loads(FX_PATH.read_text())
CASES = {c["name"]: c for c in FX["cases"]}
FS_IN = 300.0


def f32(b64: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype="<f4").astype(np.float64)


def synth(seconds=30.0, bpm=72.0, fs=FS_IN, invert=False, seed=3):
    """The same builder the fixture generator uses, so a known rate goes in."""
    import tools.make_founder_fixtures as mk

    return mk.synth_strip(seconds, bpm, fs=fs, invert=invert, seed=seed)


# --------------------------------------------------------------------------- the chain, with known answers
def test_three_hundred_hertz_resamples_by_five_over_three():
    x = np.zeros(9000)
    y, ud = fp.resample_to_model(x, 300.0)
    assert ud == (5, 3)
    assert y.size == 15000                                   # 30 s at 500 Hz
    assert fp.resample_to_model(np.zeros(100), 500.0)[1] == (1, 1)


def test_resampling_keeps_the_frequency_of_a_known_sine():
    t = np.arange(9000) / FS_IN
    x = np.sin(2 * np.pi * 5.0 * t)                          # 5 Hz, well inside the band
    y, _ = fp.resample_to_model(x, FS_IN)
    freqs = np.fft.rfftfreq(y.size, 1 / 500.0)
    peak = freqs[np.argmax(np.abs(np.fft.rfft(y)))]
    assert abs(peak - 5.0) < 0.05


def test_thirty_seconds_gives_three_non_overlapping_windows():
    w = fp.preprocess(np.zeros(9000), FS_IN)
    assert w.x.shape == (3, 1, 5000)
    assert w.starts_s == [0.0, 10.0, 20.0]
    half = fp.preprocess(np.zeros(9000), FS_IN, step_s=5.0)
    assert half.x.shape[0] == 5                              # 0, 5, 10, 15, 20 s
    assert half.starts_s == [0.0, 5.0, 10.0, 15.0, 20.0]


def test_a_strip_under_ten_seconds_gives_no_window():
    w = fp.preprocess(np.zeros(int(8 * FS_IN)), FS_IN)
    assert w.x.shape[0] == 0
    assert any("shorter than 10 s" in n for n in w.notes)


def test_every_window_is_z_scored():
    w = fp.preprocess(synth(), FS_IN)
    assert w.x.shape == (3, 1, 5000)
    for win in w.x[:, 0, :]:
        assert abs(float(win.mean())) < 1e-6
        assert abs(float(win.std()) - 1.0) < 1e-5


def test_the_notch_removes_mains_and_the_band_pass_keeps_the_qrs():
    t = np.arange(5000) / 500.0
    mains = np.sin(2 * np.pi * 50.0 * t)
    y = fp.filter_bandpass(mains, 500.0)[0]
    # the 50 Hz notch and the 40 Hz low pass together must leave almost nothing
    assert float(np.std(y[500:-500])) < 0.05 * float(np.std(mains))
    beat = np.exp(-0.5 * ((t - 5.0) / 0.01) ** 2)
    yb = fp.filter_bandpass(beat, 500.0)[0]
    assert float(np.max(np.abs(yb))) > 0.3 * float(np.max(np.abs(beat)))


def test_the_running_median_removes_a_slow_baseline():
    t = np.arange(5000) / 500.0
    wander = 2.0 * np.sin(2 * np.pi * 0.2 * t)
    y = fp.filter_bandpass(wander, 500.0)[0]
    assert float(np.max(np.abs(y[500:-500]))) < 0.1 * float(np.max(np.abs(wander)))


def test_an_inverted_strip_is_detected_and_flipped():
    up = fp.preprocess(synth(invert=False), FS_IN)
    down = fp.preprocess(synth(invert=True, seed=4), FS_IN)
    assert up.polarity_flipped is False
    assert down.polarity_flipped is True
    assert down.polarity_beats >= fp.POLARITY_MIN_BEATS
    assert down.polarity_negative_fraction >= fp.POLARITY_NEG_FRAC
    # after the flip the two give nearly the same model input
    assert float(np.max(np.abs(up.x - fp.preprocess(synth(invert=True, seed=3), FS_IN).x))) < 1e-6


def test_polarity_is_left_alone_when_asked():
    w = fp.preprocess(synth(invert=True, seed=4), FS_IN, polarity="keep")
    assert w.polarity_flipped is False


def test_nans_do_not_reach_the_model():
    x = synth()
    x[100:140] = np.nan
    w = fp.preprocess(x, FS_IN)
    assert np.isfinite(w.x).all()


def test_the_window_rule_is_max_for_ectopy_and_mean_for_everything_else():
    probs = np.stack([np.full(150, 0.1), np.full(150, 0.9), np.full(150, 0.2)])
    c = fp.combine_windows(probs)
    for i in range(150):
        if i in fp.MAX_RULE_LABELS:
            assert c[i] == pytest.approx(0.9), i
            assert fp.combine_rule(i) == "max"
        else:
            assert c[i] == pytest.approx(0.4), i
            assert fp.combine_rule(i) == "mean"
    assert fp.MAX_RULE_LABELS == frozenset({9, 16, 19, 91, 142})


def test_the_rhythm_labels_match_the_vendored_task_list():
    tasks = fp.load_tasks()
    assert len(tasks) == fp.N_CLASSES
    for index, name in fp.RHYTHM_LABELS.items():
        assert tasks[index].strip().upper() == name, f"index {index}: tasks.txt says {tasks[index]!r}"


# --------------------------------------------------------------------------- fixtures (these pin the Kotlin port)
def test_the_fixture_file_is_synthetic_and_current():
    assert "ynthetic" in FX["note"]
    assert FX["fs_model"] == fp.FS_MODEL
    assert FX["window_samples"] == fp.WIN
    assert FX["median_kernel"] == int(0.4 * fp.FS_MODEL) + 1
    assert sorted(FX["combine"]["max_rule_indices"]) == sorted(fp.MAX_RULE_LABELS)


@pytest.mark.parametrize("name", list(CASES))
def test_fixture_cases_reproduce(name):
    c = CASES[name]
    x = f32(c["strip_f32_b64"])
    y, ud = fp.resample_to_model(x, c["fs_in"])
    assert list(ud) == c["resample_up_down"]
    assert float(np.max(np.abs(y - f32(c["resampled_f32_b64"])))) < 2e-6
    w = fp.preprocess(x, c["fs_in"])
    assert w.x.shape[0] == c["n_windows"]
    assert w.starts_s == c["window_starts_s"]
    assert w.polarity_flipped == c["polarity"]["flipped"]
    assert w.polarity_beats == c["polarity"]["beats"]
    if c["n_windows"]:
        want = f32(c["model_input_f32_b64"]).reshape(c["model_input_shape"])
        assert float(np.max(np.abs(w.x - want))) < 1e-4
