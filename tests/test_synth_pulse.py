"""Beat schedule and beat template ground truth (palmppg.synth.pulse_wave)."""
import numpy as np

from palmppg.core.config import rng
from palmppg.synth.pulse_wave import (DEFAULT_MORPHOLOGY, MEASURED_KEYS, beat_times, composite_scale, generate_pulse,
                                      instantaneous_hr, measure_beats, measure_template, ppg_waveform)


def test_regular_schedule_has_exact_rate():
    s = beat_times(120.0, 72.0, 0.0, 0.25, 0.0, rng(1, "a"))
    ibi = np.diff(s.foot_t)
    assert np.allclose(ibi, 60.0 / 72.0, atol=1e-9)
    assert abs(s.n_beats - 144) <= 1
    assert abs(s.mean_hr_bpm() - 72.0) < 1e-6
    assert not s.is_ectopic.any() and np.all(s.amplitude == 1.0)


def test_hrv_and_rsa_modulation():
    s = beat_times(300.0, 70.0, 0.03, 0.25, 0.0, rng(2, "hrv"))
    sd = float(np.std(np.diff(s.foot_t)))
    assert 0.02 < sd < 0.04                        # Gaussian beat-to-beat jitter of 30 ms
    s2 = beat_times(300.0, 70.0, 0.0, 0.25, 0.05, rng(3, "rsa"))
    ibi = np.diff(s2.foot_t)
    mid = s2.foot_t[:-1] + ibi / 2
    f = np.arange(0.05, 0.6, 0.005)
    power = np.abs(np.exp(-2j * np.pi * np.outer(f, mid)) @ (ibi - ibi.mean())) ** 2
    assert abs(f[np.argmax(power)] - 0.25) < 0.01   # IBI series oscillates at the breathing rate
    assert abs((ibi.max() - ibi.min()) / 2 / ibi.mean() - 0.05) < 0.01


def test_ectopic_beats_are_premature_with_compensatory_pause():
    s = beat_times(60.0, 60.0, 0.0, 0.25, 0.0, rng(4, "ect"), n_ectopic=3)
    assert int(s.is_ectopic.sum()) == 3
    ibi0 = 1.0
    for k in np.where(s.is_ectopic)[0]:
        assert abs((s.foot_t[k] - s.foot_t[k - 1]) - 0.6 * ibi0) < 1e-9     # coupling interval
        assert abs((s.foot_t[k + 1] - s.foot_t[k - 1]) - 2 * ibi0) < 1e-9   # full compensatory pause
        assert s.amplitude[k] == 0.7 and s.amplitude[k + 1] > 1.0


def test_template_measured_values_match_design_targets():
    m = measure_template()
    assert m["upstroke_s"] == DEFAULT_MORPHOLOGY["upstroke_s"]
    assert m["notch_present"]
    assert abs(m["reflection_index"] - DEFAULT_MORPHOLOGY["reflection_index"]) < 0.02
    assert abs(m["notch_time_s"] - DEFAULT_MORPHOLOGY["notch_time_s"]) < 0.05
    assert abs(m["systolic_width_s"] - DEFAULT_MORPHOLOGY["systolic_width_s"]) < 0.05
    assert abs(m["decay_tau_s"] - DEFAULT_MORPHOLOGY["decay_tau_s"]) < 0.02
    assert abs(m["notch_depth"] - DEFAULT_MORPHOLOGY["notch_depth"]) < 0.05
    m2 = measure_template({"reflection_index": 0.6, "notch_depth": 0.05})
    assert m2["reflection_index"] > m["reflection_index"] and m2["notch_depth"] < m["notch_depth"]


def test_composite_waveform_unit_rise_and_one_peak_per_beat():
    s = beat_times(30.0, 70.0, 0.02, 0.25, 0.03, rng(5, "w"))
    t = np.arange(0.0, 30.0, 0.001)
    w = ppg_waveform(t, s.foot_t)
    assert w.min() >= 0.0 and 1.0 < w.max() < 1.4
    rises = []
    for k in range(s.n_beats - 1):
        i0, i1 = np.searchsorted(t, s.foot_t[k]), np.searchsorted(t, s.foot_t[k + 1])
        seg = w[i0:i1]
        rises.append(seg.max() - seg[0])
        assert abs(t[i0 + int(np.argmax(seg))] - s.foot_t[k] - DEFAULT_MORPHOLOGY["upstroke_s"]) < 0.004
    assert abs(np.median(rises) - 1.0) < 2e-3                      # composite_scale works on a 2 ms grid
    assert composite_scale(s.foot_t) > 0


def test_per_beat_table_consistency():
    s = beat_times(40.0, 65.0, 0.02, 0.25, 0.03, rng(6, "tbl"), n_ectopic=2)
    tb = measure_beats(s.foot_t, None, s.amplitude, s.is_ectopic)
    assert len(tb) == s.n_beats and list(tb["is_ectopic"]) == list(s.is_ectopic)
    assert np.allclose(tb["onset_t"], s.foot_t)
    assert np.allclose(tb["ibi_s"].to_numpy()[:-1], np.diff(s.foot_t))
    ok = ~tb["is_ectopic"].to_numpy() & np.r_[True, ~tb["is_ectopic"].to_numpy()[:-1]]
    sub = tb[ok]
    assert np.all((sub["foot_t"] - sub["onset_t"]) > 0.0) and np.all((sub["foot_t"] - sub["onset_t"]) < 0.06)
    assert np.all(sub["peak_t"] > sub["foot_t"])
    notched = sub[sub["notch_present"]]
    assert len(notched) > 0.8 * len(sub)
    assert np.all(notched["notch_t"] > notched["peak_t"]) and np.all(notched["dicrotic_t"] > notched["notch_t"])
    assert np.allclose(sub["upstroke_s"], sub["peak_t"] - sub["foot_t"], atol=0.002)


def test_generate_pulse_truth_dict_and_hr_series():
    pt = generate_pulse(30.0, 80.0, rng(7, "gp"), hrv_sd_s=0.0, resp_amp=0.0)
    assert abs(pt["hr_bpm"] - 80.0) < 1e-6 and pt["n_ectopic"] == 0
    assert set(MEASURED_KEYS) <= set(pt["morphology_measured"]) and set(MEASURED_KEYS) <= set(pt["morphology_template"])
    assert len(pt["foot_t_tangent"]) == len(pt["foot_t"])
    hr = instantaneous_hr(np.asarray(pt["foot_t"]), np.arange(1.0, 29.0, 0.25))
    assert np.allclose(hr, 80.0, atol=1e-6)
