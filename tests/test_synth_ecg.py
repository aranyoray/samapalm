"""Synthetic ECG, ATC writer and Kardia metadata (palmppg.synth.ecg_synth)."""
import datetime as dt
import json
import struct
import zlib

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.synth import bayer_video as bv
from palmppg.synth import ecg_synth as es
from palmppg.synth.pulse_wave import generate_pulse

SECONDS, PAT = 30.0, 0.22

def _cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()



def read_atc(path):
    """Minimal independent ATC reader: header, then (length, id, data, crc32) blocks."""
    b = open(path, "rb").read()
    assert b[:5] == b"ALIVE"
    pos, blocks = 8, {}
    while pos + 12 <= len(b):
        (n,) = struct.unpack_from("<I", b, pos)
        bid = b[pos + 4:pos + 8]
        data = b[pos + 8:pos + 8 + n]
        (crc,) = struct.unpack_from("<I", b, pos + 8 + n)
        blocks[bid] = (data, crc == (zlib.crc32(bid + data) & 0xFFFFFFFF))
        pos += 12 + n
    fmt = struct.unpack("<BHHBH", blocks[b"fmt "][0])
    ecg = np.frombuffer(blocks[b"ecg "][0], "<i2").astype(float) * fmt[2] * 1e-6
    return {"version": b[5:8], "fs": fmt[1], "resolution_nv": fmt[2], "mv": ecg, "info": blocks[b"info"][0],
            "crc_ok": all(v[1] for v in blocks.values()), "date": blocks[b"info"][0][:32].rstrip(b"\x00").decode()}


@pytest.fixture(scope="module")
def record(tmp_path_factory):
    cfg = _cfg()
    out = tmp_path_factory.mktemp("ecg")
    pt = generate_pulse(SECONDS + 4, 68.0, rng(2, "pulse"), hrv_sd_s=0.02, resp_amp=0.04, t_start=-2.0)
    sched = bv.led_schedule(cfg, SECONDS)
    p2 = min(p["on_s"] for p in sched if p["pattern"] == "P2")
    pi_truth = {"led_schedule": sched, "thumb_contact_t_ref_s": 1.0, "thumb_lift_t_ref_s": p2 + 0.6, "thumb_down_t_ref_s": p2 + 1.1}
    truth = es.write_ecg_record(out, "SWHT-PP-003-0007", 7, np.asarray(pt["foot_t"]), PAT, "sinus", cfg, rng(2, "ecg"), pi_truth,
                                SECONDS, bv.DEFAULT_WALL0_NS, pi_wall_offset_s=0.003, kardia_clock_offset_s=-0.8, app_latency_s=0.9,
                                kardia_duration_s=SECONDS, is_ectopic=np.asarray(pt["schedule"]["is_ectopic"]))
    return {"dir": out, "truth": truth, "pt": pt, "atc": read_atc(out / "kardia_0007.atc")}


def detect_r(mv, fs):
    idx = np.where((mv[1:-1] > mv[:-2]) & (mv[1:-1] >= mv[2:]) & (mv[1:-1] > 0.5))[0] + 1
    keep = [i for i in idx if not keep_last(i, fs)] if False else []
    last = -1e9
    for i in idx:
        if i - last > 0.3 * fs:
            keep.append(i)
            last = i
    return np.array(keep) / fs


def keep_last(i, fs):  # pragma: no cover - helper placeholder for readability
    return False


def test_atc_header_blocks_and_samples(record, cfg):
    a = record["atc"]
    assert a["version"] == bytes(es.ATC_VERSION) and a["crc_ok"]
    assert a["fs"] == cfg.get("ecg.fs") == 300 and a["resolution_nv"] == 500
    assert a["mv"].size == int(SECONDS * 300)
    assert 0.8 < a["mv"].max() < 4.0 and a["mv"].min() < -0.05
    assert a["date"] == record["truth"]["start_wall_ts"]


def test_r_peaks_precede_feet_by_pat(record):
    a, truth = record["atc"], record["truth"]
    r = detect_r(a["mv"], a["fs"])
    r = r[r < truth["artefacts_ecg_s"][0][0] - 0.5]                     # clean part before the lift artefact
    feet = np.asarray(truth["foot_t_ref_s"]) - truth["ecg_t0_ref_s"]
    pat = []
    for rt in r:
        nxt = feet[feet > rt]
        if nxt.size:
            pat.append(nxt[0] - rt)
    pat = np.array(pat)
    assert pat.size >= 0.9 * r.size and r.size > 20
    assert abs(np.median(pat) - PAT) < 0.008 and np.percentile(np.abs(pat - PAT), 90) < 0.02
    assert abs(truth["ecg_hr_bpm"] - record["pt"]["hr_bpm"]) < 1.0


def test_thumb_lift_artefact_is_a_step_with_recovery(record):
    a, truth = record["atc"], record["truth"]
    t_art = truth["artefacts_ecg_s"][0][0]
    i = int(round(t_art * a["fs"]))
    before = a["mv"][i - 150:i - 1]
    assert a["mv"][i + 2] - np.median(before) > 1.5                      # 2-3 mV step
    assert a["mv"][i + 300] - np.median(before) < 0.5 * (a["mv"][i + 2] - np.median(before))  # mostly recovered after 1 s
    assert np.abs(np.diff(a["mv"]))[i:i + 3].max() > 5 * np.percentile(np.abs(np.diff(before)), 99)
    assert t_art == pytest.approx(truth["artefact_onset_ref_s"] - truth["ecg_t0_ref_s"])


def test_kardia_meta_and_clock_relationships(record):
    truth = record["truth"]
    meta = json.loads((record["dir"] / "kardia_meta.json").read_text())
    assert set(meta) == {"start_wall_ts", "duration_s", "fs", "app_rhythm_label", "device_id", "export_format"}
    assert meta["export_format"] == "atc" and meta["duration_s"] == SECONDS and meta["fs"] == 300
    assert truth["ecg_t0_ref_s"] == pytest.approx(1.0 + 0.9) and truth["anchor_kind"] == "thumb_contact"
    start = dt.datetime.fromisoformat(meta["start_wall_ts"])
    true_start = dt.datetime.fromtimestamp(bv.DEFAULT_WALL0_NS / 1e9 + truth["ecg_t0_ref_s"], tz=start.tzinfo)
    assert abs((start - true_start).total_seconds() - (-0.8)) < 2e-3   # Kardia clock offset


def test_pdf_export_route(cfg, tmp_path):
    import fitz

    pt = generate_pulse(20.0, 75.0, rng(3, "p"))
    sched = bv.led_schedule(cfg, 20.0)
    pi_truth = {"led_schedule": sched, "thumb_contact_t_ref_s": 1.0, "thumb_lift_t_ref_s": 15.6, "thumb_down_t_ref_s": 16.1}
    truth = es.write_ecg_record(tmp_path, "SWHT-PP-003-0008", 8, np.asarray(pt["foot_t"]), 0.25, "af", cfg, rng(3, "e"), pi_truth,
                                20.0, bv.DEFAULT_WALL0_NS, export_format="pdf", kardia_duration_s=20.0)
    doc = fitz.open(tmp_path / "kardia_0008.pdf")
    assert doc.page_count >= 1 and truth["export_format"] == "pdf"
    assert json.loads((tmp_path / "kardia_meta.json").read_text())["export_format"] == "pdf"


def test_rhythm_profiles_shape_the_waveform(cfg):
    r = np.arange(0.5, 10.0, 0.8)
    t = np.arange(0, 10, 1 / 300)
    sinus = es.ecg_waveform(t, r, rng(1, "a"), p_wave=True, baseline_mv=0, mains_mv=0, noise_mv=0)
    af = es.ecg_waveform(t, r, rng(1, "a"), p_wave=False, baseline_mv=0, mains_mv=0, noise_mv=0)
    i = int(round((r[3] - 0.16) * 300))
    assert sinus[i] > 0.08 and abs(af[i]) < 0.02                        # P wave present only in sinus
    paced = es.ecg_waveform(t, r, rng(1, "a"), pacing_spike=True, baseline_mv=0, mains_mv=0, noise_mv=0)
    assert paced[int(round((r[3] - 0.040) * 300))] > 1.0
    for name in cfg.get("ecg.rhythm_classes"):
        assert "hr" in es.rhythm_profile(name)
