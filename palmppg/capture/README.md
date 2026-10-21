# palmppg.capture: the capture-side toolkit (protocol sections 4.1, 4.2, 4.5, 4.6, 5)

| file | role | protocol |
|---|---|---|
| `capture_pi.py` | picamera2 raw capture with preflight gates, locked camera, packed raw frames, per-frame `SensorTimestamp`, clip meta; starts the marker | 4.6 |
| `sync_marker.py` | LED + buzzer patterns P1/P2 on GPIO, logged as edges on `CLOCK_BOOTTIME` with a GPIO self-check | 4.2 |
| `clock_sync.sh` | `chronyc makestep` at shift start/end and the `clock_sync_log.csv` row; manual Kardia tablet row | 4.1 |
| `offload.sh` | rsync to the SSD/laptop, SHA-256 manifest from the source verified on the copy, completeness check and `COMPLETE.flag` | 4.6 |
| `phone_settings.md` | OnePlus 12 operator checklist | 5 |
| `android/` | Open Camera route and its limitation; the onboarding app recorder (clip + ECG on one clock) | 5, 4.6 |

Every script runs without hardware: `--simulate` on the Python scripts (MockPin objects, a software frame
source at 384x216 with the LED block painted from the marker's own pin state), `--simulate` on
`clock_sync.sh`, and `offload.sh` on any directory tree. picamera2 and gpiozero are imported lazily.

```
python -m palmppg.capture.sync_marker --simulate --seconds 8 --out /tmp/sync_events.csv
python -m palmppg.capture.capture_pi --simulate --study-id SWHT-PP-003-0001 --out-dir /tmp/p1/pi \
       --video-seconds 8 --clock-log /tmp/clock_sync_log.csv
palmppg/capture/clock_sync.sh --simulate RB unit_01 /tmp/clock_sync_log.csv
palmppg/capture/offload.sh --check /tmp/study ; palmppg/capture/offload.sh /tmp/study /mnt/ssd
```

On the Pi (real run), in this order: `clock_sync.sh <operator>` at shift start, then per participant
`python -m palmppg.capture.capture_pi --study-id <id> --out-dir <study_root>/participants/<id>/pi --operator <op> --dept <dept>`.
Exit code 2 means a preflight refusal (free space below `capture.min_free_gb`, or no `makestep` row for this
unit dated today); fix the cause and re-run. The script writes `clip1.raw`, `clip1_pts.csv`, `clip1_meta.json`
and `sync_events.csv`; a re-shoot uses `--clip-id clip1b` (the marker log then goes to `sync_events_clip1b.csv`).

## Bench acceptance procedure (protocol section 4.5), step by step

Run this before the first patient and after any change to the box, the LED, the buzzer, the phone mount or
the capture software. Twenty trials. Each trial is a short recording (the configured `video_seconds` is fine,
15 s is enough) with no participant.

Set-up (once):

1. Shift-start clock step on the Pi (`clock_sync.sh <operator>`), Kardia tablet row added. Phone settings per
   `phone_settings.md`, phone in its mount, LED visible in the phone frame (simultaneous mode).
2. Place a second phone in the aperture, screen up, running a metronome / strobe app that flashes a white
   screen at a known rate (for example 60 bpm, 100 ms flashes). This is the "metronome app flashing" of
   section 4.5: an optical event both cameras see and that is independent of the Pi marker.
3. Put the Kardia card in its position; tape a dummy electrode pair or leave the card bare. Have a pen ready
   for the card tap.

Per trial (repeat 20 times; number the trials 01..20):

4. Start the phone recording. Start `capture_pi.py --study-id BENCH-<unit>-<trial> --out-dir <bench_root>/trial_NN/pi`.
   The marker emits P1 at 2 s and P2 at `t_end - 5 s`; both cameras see the LED, the phone hears the buzzer.
5. At P2 (two long beeps) tap the Kardia card once with the pen, firmly, while the Kardia app is recording.
   This is the simulated ECG artefact of section 4.5 (same mechanism as the thumb lift of section 4.3).
6. Stop the phone recording after the Pi reports the clip end. Export the Kardia recording (ATC preferred,
   PDF otherwise) into `trial_NN/ecg/` with `kardia_meta.json`; copy the phone file and its meta into
   `trial_NN/phone/`.
7. Note in `trial_NN/notes.txt`: metronome rate, which pattern the tap followed, anything odd (phone moved,
   buzzer faint, LED partly hidden).

Scoring and the report:

8. Run `palmppg bench report <bench_root>` (see `palmppg/ingest/bench.py` and `palmppg/cli.py`). For each
   trial it detects the LED edges in the Pi video and the phone video, the beep edges in the phone audio and
   the card-tap pair, fits one offset (+ drift) per stream against `sync_events.csv`, and scores the four
   criteria from `configs/pipeline.yaml`:
   - Pi video and phone video LED onsets agree with the Pi log within one frame period after one offset and
     drift term, with at least `sync.min_edges` edges matched (DECISIONS D-003);
   - audio onsets within `sync.audio.onset_tolerance_ms` (20 ms) of the Pi log;
   - the simulated ECG artefact aligns with the video tap within one frame (`sync.fine_anchor_uncertainty_s`).
9. The command writes the one-page report `reports/bench_sync_report.md` with the per-trial residuals, the
   pass counts per criterion, and the verdict. Its header says whether the trials were hardware captures or
   the synthetic self-test (`palmppg bench selftest`), which exercises the detectors only and is not an
   acceptance.

How to file the bench report:

10. Acceptance requires all four criteria to pass in every one of the 20 hardware trials. If any trial fails,
    fix the cause (LED position, buzzer level, phone mount, exposure), re-run the full 20, do not drop trials.
11. Commit `reports/bench_sync_report.md` together with the bench root's `MANIFEST.sha256` (from
    `offload.sh <bench_root> <dest>`), the unit id, the date, the operator and the software version
    (`git rev-parse HEAD`) in the commit message. Add a one-line entry to DECISIONS.md: "bench acceptance
    unit_XX passed on <date>, report <path>". Keep the bench root on the SSD with the study data.
12. Record the measured numbers only (max residual per stream, audio offset, artefact error). Do not write
    an expected or target value anywhere in the report beyond the configured tolerances it already prints.

## Files written per clip

```
pi/clip1.raw            packed 10-bit Bayer frames, stride_bytes x height bytes each, no header
pi/clip1_pts.csv        frame_idx, sensor_ts_ns, wall_ns, exposure_us, analogue_gain, digital_gain, lux
pi/clip1_meta.json      every CONTRACTS section 3.3 key (+ "simulated" and a "capture_extra" block)
pi/sync_events.csv      event_id, kind, pattern, mono_ns, wall_ns, gpio_ok  (10 rows: P1 3+3, P2 2+2)
```

`frame_idx` is the position of the frame in the raw file (0-based); dropped frames show up as gaps in
`sensor_ts_ns`, never as gaps in the index. `motion_flag` is the median per-frame mean absolute difference of
the high 8 bits (subsampled, LED block excluded) against `capture.motion_energy_dn_max`; `live_sqi` is `null`
until a live estimator exists.
