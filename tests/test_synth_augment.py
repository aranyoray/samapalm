"""Augmentation library: frame counts, parameter logs, rate preservation, no temporal mixing (palmppg.synth.augment)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.synth import augment as ag
from palmppg.synth import positive_control as pc
from palmppg.synth.pulse_wave import generate_pulse

FPS, N, HW = 30.0, 600, (192, 108)     # full-res 192 x 108 -> planes 54 x 96 (half the small cohort profile)
T = np.arange(N) / FPS
HR = 78.0

def _cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()



def base_frames(seed: str, rgb: bool = False):
    """Static skin-like frames (dark border, 5 % static texture, sensor noise) at the test geometry."""
    r = rng(1, seed)
    if rgb:
        tex = 1.0 + 0.05 * np.clip(r.standard_normal((HW[1], HW[0], 1)), -2, 2).astype(np.float32)
    else:
        tex = 1.0 + 0.05 * np.clip(r.standard_normal((1, HW[1] // 2, HW[0] // 2)), -2, 2).astype(np.float32)
    for k in range(N):
        if rgb:
            lin = np.full((HW[1], HW[0], 3), 0.35, np.float32)
            lin[..., 0], lin[..., 2] = 0.45, 0.25
            lin = lin * tex
            lin[:6, :, :] = lin[-6:, :, :] = lin[:, :6, :] = lin[:, -6:, :] = 0.02
            lin += np.sqrt(lin / 3000.0 + 0.004**2) * r.standard_normal(lin.shape, dtype=np.float32)
            yield ag.Frame.rgb((np.clip(ag.srgb_oetf(np.clip(lin, 0, 1)), 0, 1) * 255 + 0.5).astype(np.uint8), T[k], k)
        else:
            h2, w2 = HW[1] // 2, HW[0] // 2
            planes = np.stack([np.full((h2, w2), 300.0, np.float32), np.full((h2, w2), 450.0, np.float32),
                               np.full((h2, w2), 450.0, np.float32), np.full((h2, w2), 330.0, np.float32)]) * tex
            planes[:, :3, :] = planes[:, -3:, :] = planes[:, :, :3] = planes[:, :, -3:] = 10.0
            planes += np.sqrt(planes / 8.3 + 4.0) * r.standard_normal(planes.shape, dtype=np.float32) + 64.0
            yield ag.Frame.bayer(np.clip(np.rint(planes), 0, 1023).astype(np.uint16), T[k], k)


@pytest.fixture(scope="module")
def pulsed():
    cfg = _cfg()
    pt = generate_pulse(22.0, HR, rng(2, "p"), hrv_sd_s=0.02, resp_amp=0.04)
    mask = np.zeros((HW[1], HW[0]), bool)
    mask[24:-24, 40:-40] = True
    frames = list(pc.inject_known_pulse(base_frames("b"), pt, 0.008, {"R": 0.5, "G": 1.0, "B": 0.6}))
    rgb_frames = list(pc.inject_known_pulse(base_frames("r", rgb=True), pt, 0.008, {"R": 0.5, "G": 1.0, "B": 0.6}))
    return {"pt": pt, "mask": mask, "bayer": frames, "rgb": rgb_frames}


def rate_error(frames, mask, pt, cfg):
    t, x, _ = pc.extract_region_trace(frames, mask, "G1" if frames[0].kind == "bayer" else "G")
    return abs(pc.dense_dft_rate(t, pc._highpass_trace(t, -x), tuple(cfg.get("pulse.band_rate"))) - pt["hr_bpm"])


def test_registry_covers_section_8_and_levels_come_from_cfg(cfg):
    expected = {"Rotate", "Translate", "Scale", "Perspective", "MicroJitter", "ExposureShift", "IlluminantShift", "VignettingGain",
                "MovingShadow", "ShotNoise", "ReadNoise", "Quantise8bit", "Defocus", "MotionBlur", "FrameDrops", "TimestampJitter",
                "VFRResample", "FlickerModulation", "H264Compress", "H265Compress", "Downscale", "ChromaSubsample", "SyntheticToneShift"}
    assert set(ag.TRANSFORMS) == expected
    grid = ag.severity_grid(cfg)
    assert grid["Rotate"] == cfg.get("augment.rotation_deg") and grid["H264Compress"] == cfg.get("augment.h264_crf")
    assert grid["SyntheticToneShift"] == cfg.get("augment.melanin_levels") and len(grid["Downscale"]) == 2
    assert all(not cls.temporal_interpolation for cls in ag.TRANSFORMS.values())
    with pytest.raises(ValueError):
        ag.Rotate(severity_index=7, cfg=cfg)


@pytest.mark.parametrize("name", sorted(ag.TRANSFORMS))
def test_each_transform_preserves_count_logs_params_and_keeps_rate_at_mildest_severity(name, pulsed, cfg):
    log = []
    out = list(ag.apply_chain(iter(pulsed["bayer"]), [(name, 0)], rng(3, name), log, cfg))
    entry = log[0]
    assert entry["name"] == name and entry["severity_index"] == 0 and entry["params"]
    if name == "FrameDrops":
        assert len(out) < N and len(out) + len(entry["runtime"]["dropped_idx"]) == N
        assert sorted(entry["runtime"]["dropped_idx"]) == sorted(set(range(N)) - {f.idx for f in out})
    else:
        assert len(out) == N
    if name in ("H264Compress", "H265Compress", "ChromaSubsample"):
        assert out[0].kind == "rgb" and "pi_proxy" in out[0].labels
    if name == "SyntheticToneShift":
        assert "synthetic tone shift" in out[0].labels and entry["label"] == "synthetic tone shift"
    assert rate_error(out, pulsed["mask"], pulsed["pt"], cfg) <= cfg.get("augment.rate_preservation_bpm")


# Transforms expected to keep the rate at their highest severity on this fixture. Left out on purpose:
# ExposureShift (+1.5 EV saturates, tested below), MovingShadow (a 30 % sweep is a broadband transient) and the two
# codecs (CRF 35 removes a sub-DN modulation from static blocks; the degradation is recorded, not assumed benign).
BENIGN_AT_MAX = ["Rotate", "Translate", "Scale", "Perspective", "MicroJitter", "IlluminantShift", "VignettingGain", "ShotNoise",
                 "ReadNoise", "Quantise8bit", "Defocus", "MotionBlur", "FrameDrops", "TimestampJitter", "VFRResample",
                 "FlickerModulation", "Downscale", "ChromaSubsample", "SyntheticToneShift"]


@pytest.mark.parametrize("name", BENIGN_AT_MAX)
def test_benign_transforms_keep_rate_at_highest_severity(name, pulsed, cfg):
    sev = len(ag.TRANSFORMS[name].levels(cfg)) - 1
    out = list(ag.apply_chain(iter(pulsed["bayer"]), [(name, sev)], rng(4, name), None, cfg))
    assert rate_error(out, pulsed["mask"], pulsed["pt"], cfg) <= cfg.get("augment.rate_preservation_bpm")


def test_compression_degradation_is_measurable(pulsed, cfg):
    """CRF 18 keeps the rate on this fixture; the pulse-band SNR falls with CRF and the log carries the file size."""
    def snr(frames):
        t, x, _ = pc.extract_region_trace(frames, pulsed["mask"], "G")
        xd = pc._highpass_trace(t, -x)
        f = np.arange(0.5, 4.0, 0.01)
        power = np.abs(np.exp(-2j * np.pi * np.outer(f, t)) @ xd) ** 2
        return float(power[np.argmin(np.abs(f - pulsed["pt"]["hr_bpm"] / 60.0))] / np.median(power))

    logs = {}
    out = {}
    for sev in (0, 3):
        log = []
        out[sev] = list(ag.apply_chain(iter(pulsed["bayer"]), [("H264Compress", sev)], rng(10, f"c{sev}"), log, cfg))
        logs[sev] = log[0]
    assert logs[0]["params"]["crf"] == cfg.get("augment.h264_crf")[0] and logs[3]["params"]["crf"] == cfg.get("augment.h264_crf")[3]
    assert logs[0]["runtime"]["bytes"] > logs[3]["runtime"]["bytes"] > 0
    assert rate_error(out[0], pulsed["mask"], pulsed["pt"], cfg) <= cfg.get("augment.rate_preservation_bpm")
    assert snr(out[3]) < 0.5 * snr(out[0])


def test_exposure_shift_down_is_benign_and_up_saturates(pulsed, cfg):
    down = list(ag.apply_chain(iter(pulsed["bayer"]), [{"name": "ExposureShift", "severity_index": 2, "params": {"sign": -1}}], rng(5, "d"), None, cfg))
    assert rate_error(down, pulsed["mask"], pulsed["pt"], cfg) <= cfg.get("augment.rate_preservation_bpm")
    up = list(ag.apply_chain(iter(pulsed["bayer"]), [{"name": "ExposureShift", "severity_index": 2, "params": {"sign": 1}}], rng(5, "u"), None, cfg))
    sat = np.mean([(f.data[1] >= 1023).mean() for f in up])
    assert sat > 0.5                                                   # +1.5 EV clips the G planes: recorded degradation
    mean_down = np.mean([f.linear()[1].mean() for f in down])
    mean_in = np.mean([f.linear()[1].mean() for f in pulsed["bayer"]])
    assert abs(mean_down / mean_in - 2 ** -1.5) < 0.02


def test_rgb_frames_through_photometric_and_codec_paths(pulsed, cfg):
    for spec in (("ExposureShift", 0, {"sign": -1}), ("H264Compress", 0), ("SyntheticToneShift", 1), ("Downscale", 1)):
        out = list(ag.apply_chain(iter(pulsed["rgb"]), [spec], rng(6, spec[0]), None, cfg))
        assert len(out) == N and out[0].kind == "rgb" and out[0].data.dtype == np.uint8
        assert rate_error(out, pulsed["mask"], pulsed["pt"], cfg) <= cfg.get("augment.rate_preservation_bpm")
    tone = list(ag.apply_chain(iter(pulsed["rgb"][:5]), [("SyntheticToneShift", 2)], rng(6, "t"), None, cfg))
    lin_in, lin_out = pulsed["rgb"][0].linear(), tone[0].linear()
    m = pulsed["mask"]
    ratio = [lin_out[..., c][m].mean() / lin_in[..., c][m].mean() for c in range(3)]
    assert ratio[2] < ratio[1] < ratio[0] < 1.0


@pytest.mark.parametrize("name", ["Rotate", "MicroJitter", "ShotNoise", "Defocus", "FlickerModulation", "SyntheticToneShift", "MovingShadow"])
def test_no_temporal_mixing(name, pulsed, cfg):
    frames = pulsed["bayer"][:40]
    perturbed = [f if f.idx != 20 else f.with_data(np.clip(f.data.astype(np.int32) + 60, 0, 1023).astype(np.uint16)) for f in frames]
    a = list(ag.apply_chain(iter(frames), [(name, 1)], rng(7, name), None, cfg))
    b = list(ag.apply_chain(iter(perturbed), [(name, 1)], rng(7, name), None, cfg))
    changed = [i for i, (x, y) in enumerate(zip(a, b)) if not np.array_equal(x.data, y.data)]
    assert changed == [20]


def test_timestamp_transforms_and_apply_times(cfg):
    t = np.arange(300) / FPS
    r = rng(8, "t")
    assert np.array_equal(ag.apply_chain_times(t, [("Rotate", 0)], r, cfg), t)
    tj = ag.apply_chain_times(t, [("TimestampJitter", 2)], rng(8, "j"), cfg)
    assert 0.006 < np.std(tj - t) < 0.014
    tv = ag.apply_chain_times(t, [("VFRResample", 2)], rng(8, "v"), cfg)
    assert np.std(np.diff(tv)) > 1e-3 and abs(np.polyfit(t, tv, 1)[0] - 1.001) < 1e-4   # alternation + wobble + 0.1 % drift
    fd = ag.FrameDrops(2, cfg)
    td = fd.apply_times(t, rng(8, "d"))
    assert td.size < t.size and td.size + len(fd.runtime["dropped_idx"]) == t.size and td[0] == 0.0
    frames = list(base_frames("x"))[:100]
    out = list(ag.apply_chain(iter(frames), [("VFRResample", 1)], rng(8, "vf"), None, cfg))
    assert np.array_equal([f.data for f in out][5], frames[5].data) and out[5].t_s != frames[5].t_s


def test_chain_logs_every_step_and_refuses_temporal_interpolation(pulsed, cfg):
    log = {"clip_id": "clip1"}
    out = list(ag.apply_chain(iter(pulsed["bayer"][:30]), [("Rotate", 1), ("ShotNoise", 0), ("H264Compress", 1)], rng(9, "c"), log, cfg))
    assert [e["name"] for e in log["chain"]] == ["Rotate", "ShotNoise", "H264Compress"] and len(out) == 30
    assert log["chain"][0]["runtime"]["sign"] in (-1, 1) and log["chain"][2]["runtime"]["bytes"] > 0

    class Smoother(ag.Transform):
        name = "Smoother"
        temporal_interpolation = True

    with pytest.raises(AssertionError):
        list(ag.apply_chain(iter(pulsed["bayer"][:3]), [Smoother()], rng(9, "s")))
