"""Positive control: injection and scoring roundtrip (palmppg.synth.positive_control)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.synth import augment as ag
from palmppg.synth import positive_control as pc
from palmppg.synth.pulse_wave import generate_pulse

FPS, N = 30.0, 660
T = np.arange(N) / FPS
HW = (36, 64)                       # Bayer planes; full-resolution frame 72 x 128
MASK = np.ones((2 * HW[0], 2 * HW[1]), bool)


def static_frames(seed: str, noise: bool):
    r = rng(1, seed)
    for k in range(N):
        planes = np.stack([np.full(HW, 300.0, np.float32), np.full(HW, 450.0, np.float32),
                           np.full(HW, 450.0, np.float32), np.full(HW, 330.0, np.float32)])
        if noise:
            planes += np.sqrt(planes / 8.3 + 4.0) * r.standard_normal(planes.shape, dtype=np.float32)
        yield ag.Frame.bayer(np.clip(np.rint(planes + 64.0), 0, 1023).astype(np.uint16), T[k], k)


def test_injection_amplitude_and_channel_ratios(cfg):
    pt = generate_pulse(24.0, 66.0, rng(2, "p"), hrv_sd_s=0.0, resp_amp=0.0)
    out = list(pc.inject_known_pulse(static_frames("a", False), pt, 0.006, {"R": 0.5, "G": 1.0, "B": 0.6}))
    assert len(out) == N and out[0].kind == "bayer" and out[0].data.dtype == np.uint16
    w = np.array([f.meta["injected_w"] for f in out])
    for ch, expect in (("R", 0.003), ("G1", 0.006), ("G2", 0.006), ("B", 0.0036)):
        t, x, _ = pc.extract_region_trace(out, MASK, ch)
        coef = np.linalg.lstsq(np.c_[np.ones(N), w], x, rcond=None)[0]
        assert abs(-coef[1] / coef[0] - expect) / expect < 0.03, ch
    half = np.zeros(MASK.shape, np.float32)
    half[:, MASK.shape[1] // 2:] = 1.0
    out2 = list(pc.inject_known_pulse(static_frames("a", False), pt, 0.006, (0.5, 1.0, 0.6), ac_map=half))
    t, x_left, _ = pc.extract_region_trace(out2, half < 0.5, "G1")
    assert np.ptp(x_left) == 0.0


def test_rgb_srgb_injection_is_linear_light(cfg):
    pt = generate_pulse(24.0, 66.0, rng(2, "p"), hrv_sd_s=0.0, resp_amp=0.0)
    img = (ag.srgb_oetf(np.full((*MASK.shape, 3), 0.35, np.float32)) * 255 + 0.5).astype(np.uint8)
    frames = [ag.Frame.rgb(img, T[k], k) for k in range(N)]
    out = list(pc.inject_known_pulse(frames, pt, 0.02, (0.5, 1.0, 0.6)))
    t, x, _ = pc.extract_region_trace(out, MASK, "G")
    w = np.array([f.meta["injected_w"] for f in out])
    coef = np.linalg.lstsq(np.c_[np.ones(N), w], x, rcond=None)[0]
    assert abs(-coef[1] / coef[0] - 0.02) / 0.02 < 0.10          # 8-bit quantisation limits the precision


@pytest.mark.parametrize("noise", [False, True])
def test_roundtrip_passes(cfg, noise):
    pt = generate_pulse(22.0, 72.0, rng(3, "p"), hrv_sd_s=0.02, resp_amp=0.04)
    out = list(pc.inject_known_pulse(static_frames("rt", noise), pt, 0.008, {"R": 0.5, "G": 1.0, "B": 0.6}))
    t, x, _ = pc.extract_region_trace(out, MASK, "G1")
    rec = pc.reference_recovery(t, x, cfg)
    score = pc.score_recovery(pt, rec, fps=FPS, cfg=cfg)
    assert score["hr"]["pass"] and score["hr"]["abs_err_bpm"] < 0.5
    assert score["feet"]["pass"] and score["feet"]["median_abs_err_frames"] < 0.6 and score["feet"]["match_rate"] > 0.85
    scored = {k: v for k, v in score["morphology"].items() if v["pass"] is not None}
    assert {"upstroke_s", "systolic_width_s", "notch_time_s", "reflection_index"} <= set(scored)
    assert all(v["pass"] for v in scored.values()), scored
    assert score["pass"]


def test_roundtrip_after_crf28_proxy(cfg):
    """CRF-28 leg of the positive control on 256 x 144 Bayer frames (pi_proxy 128 x 72). At this quarter-scale
    geometry x264 drops a sub-1 % modulation from static blocks (sub-quantiser residuals are skipped) and the
    rate survives from about 2 % AC/DC, so 2 % is injected here and only the rate is required; the degradation
    of foot timing and morphology is recorded in the score. The at-scale check (0.3-1 %, full geometry)
    belongs to the integrator's run on full-size clips."""
    pt = generate_pulse(22.0, 72.0, rng(3, "p"), hrv_sd_s=0.02, resp_amp=0.04)
    r = rng(4, "big")
    tex = 1.0 + 0.05 * np.clip(r.standard_normal((1, 72, 128)), -2, 2).astype(np.float32)
    frames = []
    for k in range(N):
        planes = np.stack([np.full((72, 128), 300.0, np.float32), np.full((72, 128), 450.0, np.float32),
                           np.full((72, 128), 450.0, np.float32), np.full((72, 128), 330.0, np.float32)]) * tex
        planes += np.sqrt(planes / 8.3 + 4.0) * r.standard_normal(planes.shape, dtype=np.float32)
        frames.append(ag.Frame.bayer(np.clip(np.rint(planes + 64.0), 0, 1023).astype(np.uint16), T[k], k))
    inj = pc.inject_known_pulse(frames, pt, 0.02, {"R": 0.5, "G": 1.0, "B": 0.6})
    log = []
    out = list(ag.apply_chain(inj, [("H264Compress", 2)], rng(4, "h"), log, cfg))
    assert log[0]["params"]["crf"] == cfg.get("augment.h264_crf")[2]
    assert out[0].kind == "rgb" and "h264" in out[0].labels and out[0].data.shape == (72, 128, 3)
    mask = np.zeros((144, 256), bool)
    mask[20:-20, 30:-30] = True
    t, x, _ = pc.extract_region_trace(out, mask, "G")
    score = pc.score_recovery(pt, pc.reference_recovery(t, x, cfg), fps=FPS, cfg=cfg)
    assert score["hr"]["pass"]
    assert np.isfinite(score["feet"]["median_abs_err_frames"]) and "pass" in score["feet"]   # recorded, not required


def test_scoring_fails_on_wrong_recoveries(cfg):
    pt = generate_pulse(22.0, 72.0, rng(3, "p"), hrv_sd_s=0.02, resp_amp=0.04)
    feet = np.asarray(pt["foot_t_tangent"])
    good = {"hr_bpm": pt["hr_bpm"], "foot_times": feet, "morphology": dict(pt["morphology_measured"])}
    assert pc.score_recovery(pt, good, fps=FPS, cfg=cfg)["pass"]
    assert not pc.score_recovery(pt, {**good, "hr_bpm": pt["hr_bpm"] + 3.0}, fps=FPS, cfg=cfg)["hr"]["pass"]
    late = pc.score_recovery(pt, {**good, "foot_times": feet + 2.0 / FPS}, fps=FPS, cfg=cfg)
    assert not late["feet"]["pass"] and late["feet"]["median_abs_err_frames"] == pytest.approx(2.0)
    bad_m = dict(good["morphology"])
    bad_m["upstroke_s"] *= 1.5
    s = pc.score_recovery(pt, {**good, "morphology": bad_m}, fps=FPS, cfg=cfg)
    assert not s["morphology"]["upstroke_s"]["pass"] and not s["pass"]
    assert s["tolerances"]["hr_bpm"] == 1.0 and s["tolerances"]["morphology_rel"] == 0.2
