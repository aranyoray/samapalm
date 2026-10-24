# Task: quality-core (Kotlin) + Python reference: clip and ECG grades, Kardia file readers, rhythm summary

Read /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md first,
then docs/onboarding_v2_design.md sections 2.4, 4 and 9, then the recorder that produces the inputs:
android/app/src/main/java/org/samahealth/onboarding/recorder/PalmRecorderActivity.kt (roi.csv, frames.csv,
ecg_samples.csv, meta.json writers), BleKardia.kt, AtcWriter.kt, PulseMeter.kt; palmppg/ingest/phone_tap.py;
palmppg/ecg/atc.py; palmppg/pulse/sqi.py (existing SNR conventions); CONTRACTS.md 3.5-3.6.

Goal: after each clip, and in a "Quality" tab, the phone shows Good / Borderline / Retake for the palm video and
for the ECG, with plain reasons, plus a participant-friendly rhythm summary. Rule-based, transparent, offline.

You own (create):
* android/quality-core/ : new Gradle module, plain Kotlin JVM like android/crf-core (copy its build.gradle.kts
  pattern; kotlinx-serialization not required). Add `include(":quality-core")` to android/settings.gradle.kts
  (the only line you may change there). Package org.samahealth.quality. Public API exactly as design section 4
  (Grade, RoiSeries, RoiCsv, FramesCsv, VideoQuality, EcgCsv, AtcReader, EcgTrace, EcgQuality, EcgSummary +
  RhythmSummary) plus `object KardiaPdf { fun extract(pdfBytes: ByteArray): EcgTrace }` replacing the raster
  EcgDigitiser idea (drop EcgDigitiser): Kardia PDFs store the trace as vector line paths, one point per sample
  (300 Hz, 0.2362 pt per sample, 25 mm/s, 10 mm/mV, ~0.4 pt black stroke, 4 strips on US-Letter for single lead;
  strip 1 starts with a 1 mV x 0.2 s calibration pulse; short ticks under strips mark beats; 1 s grid lines and
  baselines are also black but thinner/straight). Write a minimal pure-Kotlin PDF reader: find content streams,
  inflate /FlateDecode with java.util.zip.Inflater, tokenize path operators (m l c re h S s f n w cm q Q RG rg G g
  K k), track CTM and line width, keep stroked polylines that look like the trace (many points, ~0.24 pt x-step),
  drop calibration pulse/ticks/grid, order strips top to bottom, convert to mV using the scale (measure the 1 mV
  calibration pulse when present, else 10 mm/mV), concatenate, return fs 300. Warnings for anything assumed.
  Also parse the page text for "Kardia Determination" / heart rate when cheaply possible (best effort; optional
  fields in EcgTrace may be added: determination: String?, hrBpm: Int?, enhancedFilter: Boolean?, mainsHz: Int?).
* Algorithms (document defaults as PROVISIONAL, to be calibrated on pilot clips like DECISIONS D-008):
  Video (from roi.csv; frames.csv optional): duration_s, fps, dropped_frac (frame-time gaps), mean_level (median
  y_mean), clipped_frac (median clip_frac), dark_frac (rows with y_mean < 20: catches the black-frame failure in
  D-033), motion (median relative change of the 3x3 grid between rows; from y when no grid), pulse via POS
  (Wang 2017, 1.6 s windows) on r/g/b resampled to 30 Hz, spectrum 0.7-3.5 Hz, pulse_bpm, snr_db (de Haan & Jeanne
  2013: power within +/-0.1 Hz of f0 and +/-0.2 Hz of 2 f0 over the rest of 0.5-4 Hz; f0 = refHr when given),
  perfusion_pct, skewness. Retake: duration < 0.9 x expected, mean_level < 25 or dark_frac > 0.2, clipped_frac >
  0.25, dropped_frac > 0.05, snr_db < -3. Borderline: snr_db < 1.5, clipped_frac > 0.05, motion > 0.02,
  dropped_frac > 0.01, |pulse - refHr| > 8 bpm. Else good.
  ECG (mV at fs): 0.5-40 Hz Butterworth biquads forward-backward, QRS detector (Pan-Tompkins style: derivative,
  square, 150 ms integration, adaptive thresholds, 250 ms refractory, refine to max |x| within +/-75 ms), polarity
  (inverted flag), metrics duration_s, n_beats, hr_bpm (60/median RR), rr_max_s, rr_ratio, template_corr (mean
  Pearson of beats with the median template, -0.25..+0.45 s), ksqi (kurtosis), flat_frac (1 s windows with
  ptp < 0.05 mV), irregularity per Dash et al. 2009 (RMSSD/meanRR >= 0.1, turning point ratio within the random
  expectation band, Shannon entropy >= 0.7 over 16 bins after outlier removal) -> irregular_flag. Retake: duration
  < 20 s, flat_frac > 0.3, fewer than 8 beats, template_corr < 0.5, hr outside 30-220. Borderline: template_corr
  < 0.66 (Orphanidou 2015), ksqi < 5, rr_max_s > 3, hr outside 40-180, flat_frac > 0.1. The irregular flag never
  lowers the grade; the rr_ratio rule is not applied when irregular. RhythmSummary gives hr, regular/irregular/
  insufficient, inverted, and 2-3 plain sentences for a participant ending with "This is not a medical result. A study
  doctor reviews every recording." Never output rhythm names such as AF.
* palmppg/quality/__init__.py, palmppg/quality/onsite.py: numpy-only Python reference with identical algorithms
  (same biquad and FFT/periodogram code paths so numbers match); readers for roi.csv / ecg_samples.csv / ATC
  (reuse palmppg.ecg.atc) / Kardia PDF (pymupdf or a port of your reader).
* tools/make_quality_fixtures.py, configs/quality_fixtures/*.json: synthetic cases with known answers (clean
  pulse at known bpm, noisy, black frames, short clip, clipping, dropped frames; ECG clean at known bpm, noisy,
  flat, inverted, irregular RR series, pause) generated as recorder-format CSV text + expected metrics/grade.
  Also a synthetic vector Kardia-like PDF (reportlab, already a dependency: see palmppg/ecg/pdf_digitiser.py
  render_synthetic_strip_pdf) with known samples, stored small (base64 or a .pdf under configs/quality_fixtures).
  Real Kardia sample PDFs downloaded by a research agent are at
  /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/dl_jph1l/kardiamobile-1l-ecg.pdf
  (and dl_jph6l/ for 6-lead; helper scripts in scratchpad/scripts/pdftrace.py): use them ONLY for local checks
  (they contain a stranger's personal data: never copy them, or values from them, into the repository) and report
  whether your reader recovers 9000 samples and a plausible HR from the 1-lead file.
* Tests: tests/test_quality_onsite.py (Python, known answers) and android/quality-core/src/test/... (Kotlin:
  fixtures within tolerance: identical grades and reasons, metrics within 1e-6 relative or a stated tolerance).

Not yours: anything else (the app module, crf-core, schema). Run: pytest on your tests + lint test,
`cd android && ./gradlew --offline -q :quality-core:test`.
