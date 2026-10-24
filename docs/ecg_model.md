# ECGFounder single-lead model: offline runner, ONNX export, on-phone notes

Design contract section 9. ECGFounder (Li et al., NEJM AI 2025, <https://github.com/PKUDigitalHealth/ECGFounder>)
is a Net1D network trained on 10 s hospital ECGs. Its 1-lead checkpoint takes lead I, which is what the Kardia
records. We run it offline on the analysis laptop and compare it with the clinician read of the same strip
(hypothesis H6).

Code: `palmppg/ecg/founder.py` (vendored Net1D, preprocessing, window rule, folder runner),
`palmppg ecg founder` (CLI), `tools/export_ecgfounder_onnx.py` (ONNX export with a parity check),
`configs/ecgfounder_tasks.txt` (the 150 output labels, a copy of upstream `tasks.txt`; line i is output i - 1),
`tests/test_ecg_founder.py`.

## Ethics position on results

* Participants get the Kardia app's own result (its FDA-cleared determination and heart rate) on the one-page
  summary, with the signal-quality grade and a note that a study clinician reviews the strip.
* ECGFounder outputs are research annotations for the study clinician and for the H6 comparison. They are not
  shown or given to participants unless the ethics committee approves it and a clinician has over-read the strip.
  Every output file carries this note in its `use` field.
* No published evaluation of ECGFounder on Indian or South-Asian ECGs exists. The model has also not been
  evaluated on Kardia lead I (a handheld, finger-contact recording) by its authors. Treat its probabilities as
  uncalibrated for this cohort.

## 1. Get the weights (on a laptop with internet access)

The checkpoint is `1_lead_ECGFounder.pth` (about 370 MB, includes optimiser state) in the Hugging Face repository
`PKUDigitalHealth/ECGFounder`. It cannot be fetched from the build sandbox. Keep it under `work/` (git-ignored);
never commit it.

```bash
mkdir -p work/ecgfounder
# either
pip install huggingface_hub
huggingface-cli download PKUDigitalHealth/ECGFounder 1_lead_ECGFounder.pth --local-dir work/ecgfounder
# or
curl -L -o work/ecgfounder/1_lead_ECGFounder.pth \
  https://huggingface.co/PKUDigitalHealth/ECGFounder/resolve/main/1_lead_ECGFounder.pth
sha256sum work/ecgfounder/1_lead_ECGFounder.pth
```

If the repository asks you to accept terms or to log in, do that (`huggingface-cli login`) and note what you
accepted. Record the sha256 in DECISIONS.md the first time; every output JSON carries `weights_sha256`, so a
result can always be tied to the exact file.

Install the extra: `pip install -e ".[ecgmodel]"` (torch, onnx, onnxruntime).

## 2. Run it

```bash
palmppg ecg founder --weights work/ecgfounder/1_lead_ECGFounder.pth --atc data/.../kardia_0001.atc
palmppg ecg founder --weights work/ecgfounder/1_lead_ECGFounder.pth --participants <study_root or folder>
palmppg ecg founder ... --unfiltered        # z-score only, as upstream ptbxl_eval.py
palmppg ecg founder ... --out work/ecgfounder/run1   # write <out>/<PID>/<clip>_ecg_founder.json instead
```

`--atc` takes one ATC file (a BLE `<clip>_ecg_samples.csv` also works). `--participants` takes a folder of
participant folders, or a study root (its `participants/` is used). Under each participant folder every
`<clip>_ecg_samples.csv` (BLE capture, `t_ref_ns` + `lead1_mv`), `<clip>_ecg.atc`, `<clip>_kardia.atc` and
`kardia_*.atc` is found; for one clip the BLE CSV is preferred over the ATC written from the same capture. One
`<clip>_ecg_founder.json` is written per clip, next to the input unless `--out` is given. The command prints one
summary row per clip; exit code 3 if any clip failed.

Weights loading: the checkpoint is read with torch's weights-only unpickler (numpy scalar types allowed), and
every model weight must be present. If that load is refused, check the file's sha256 and pass `--trust-pickle`
(full unpickle, as upstream does: it runs code from the file).

### What happens to a strip

1. NaN -> 0; resample to 500 Hz with `resample_poly` (300 Hz: up 5, down 3). BLE CSV: fs from the `t_ref_ns`
   span, rounded to a whole number when within 1 percent (the measured value is kept as `fs_measured`).
2. Polarity check on the whole strip: peaks of the band-passed |signal| (above half its 99th percentile, at least
   0.3 s apart) are beats; if at least 70 percent of at least 3 beats have a negative dominant deflection, the
   strip is inverted (for example fingers on the wrong electrodes). Recorded as `polarity_flipped` with
   `polarity_negative_fraction`.
3. Non-overlapping 10 s windows from t = 0 (30 s -> 3 windows; a tail shorter than 10 s is dropped; a strip
   shorter than 10 s gives no window and null probabilities).
4. Default: each window filtered on its own exactly as upstream `dataset.py` / `util.filter_bandpass` (50 Hz notch
   Q = 30, 4th-order Butterworth 0.67-40 Hz filtfilt, minus a 0.4 s running median). `--unfiltered`: no filter,
   as `ptbxl_eval.py`. Recorded as `filtered` and `filter`.
5. z-score per window, `(x - mean) / (std + 1e-8)`, then Net1D and a sigmoid per label.
6. Window combination, fixed before any study data: max over windows for ectopic beats and pauses
   (PVC, PAC, PSVC, bigeminy, sinus pause: they can sit in one window only), mean for every other label
   (sustained rhythms, including SVT and VT). Per-window probabilities are always written too, so a short run in
   one window stays visible.

### Output JSON (`<clip>_ecg_founder.json`)

`pid`, `clip`, `input`, `input_kind`, `labels` (the 18-label rhythm subset: `index`, `rule`, `prob`,
`window_probs`), `all_labels` (150 names -> combined probability), `window_probs` (n x 150), `n_windows`,
`window_starts_s`, `filtered`, `filter`, `polarity_flipped`, `polarity_negative_fraction`, `fs_in`,
`resample_up_down`, `weights_sha256`, `torch_version`, `created_at`, `notes`, `use`.

Rhythm subset (index: label): 1 NORMAL SINUS RHYTHM, 3 SINUS RHYTHM, 4 SINUS BRADYCARDIA, 5 ATRIAL FIBRILLATION,
6 SINUS TACHYCARDIA, 9 PREMATURE VENTRICULAR COMPLEXES, 16 PREMATURE ATRIAL COMPLEXES, 19 PREMATURE
SUPRAVENTRICULAR COMPLEXES, 32 ATRIAL FLUTTER, 33 MARKED SINUS BRADYCARDIA, 34 WITH SINUS ARRHYTHMIA,
39 UNDETERMINED RHYTHM, 49 JUNCTIONAL RHYTHM, 79 WITH 1ST DEGREE AV BLOCK, 91 IN A PATTERN OF BIGEMINY,
93 SUPRAVENTRICULAR TACHYCARDIA, 98 VENTRICULAR TACHYCARDIA, 142 WITH SINUS PAUSE.

No probability threshold is applied here. Thresholds for the H6 comparison are fixed in the analysis plan, not in
this runner.

## 3. Export to ONNX

```bash
python tools/export_ecgfounder_onnx.py --weights work/ecgfounder/1_lead_ECGFounder.pth
# -> work/ecgfounder/ecgfounder_1lead_fp32.onnx and ecgfounder_1lead_fp32.report.json
python tools/export_ecgfounder_onnx.py --random-weights --out /tmp/rand.onnx   # pipeline check only
```

The tool exports fp32, opset 17, and runs ONNX Runtime against torch on random z-scored windows and on synthetic
ECG windows (sinus, AF-like, ectopy, inverted; filtered and unfiltered). Pass: max |delta p| < 1e-4 on all 150
outputs. The JSON report lists versions, operators, sizes, both sha256 values and the parity numbers.

Checked with the real weights (2026-10-24, torch 2.14.1 / onnx 1.23.2 / onnxruntime 1.31.0): the export passes
with max |delta p| 2.1e-6 on random windows and 6.9e-7 on synthetic ECG, and max |delta logit| 1.8e-5. The file
is 123.3 MB. Weights sha256 `f863a38897fb49a27fec7e44008ea3c7bdbd29c77fa4a02ecbb8c56df4f37603`
(`1_lead_ECGFounder.pth`, 369,807,481 bytes); the CI model job checks that sum before exporting.

Pad fix: upstream zero-pads before each max-pool. After constant folding, ONNX Runtime fuses that Pad into
MaxPool's own padding, which pads with -inf instead of 0; with the trained weights this gave logit errors up to
0.8 (reported by the OpenHolter wrapper, which found the fix). The export writes that pad as a Concat of zeros
(`founder.onnx_export_mode`), which cannot be fused; the maths is unchanged and the test suite checks
torch == ONNX Runtime within 1e-4.

## 4. On the phone

Built, as of 2026-10-24.

* Preprocessing: `android/ecg-model` (`org.samahealth.ecgmodel.FounderPrep`) is a port of
  `palmppg/ecg/founder_prep.py`, which was split out of `founder.py` so the chain can be imported, tested and
  used to generate fixtures without torch. `tools/make_founder_fixtures.py` writes
  `configs/founder_fixtures/preprocess.json` (synthetic strips, every intermediate stage, the filter
  coefficients and the combination rule) and both `tests/test_founder_prep.py` and
  `android/ecg-model/src/test/.../FounderPrepTest.kt` check against it. The Kotlin resampling matches scipy to
  2e-6, the filtered windows to 5e-6 and the model input to 1e-4, all in float32, which is the precision the
  model is fed in.
* Checked end to end on 2026-10-24: the tensors the Kotlin port produces were run through the real exported
  graph with ONNX Runtime and compared with the Python runner's, giving max |delta p| 4.8e-6 per window and
  1.0e-6 after combining, with the same top labels (a synthetic 72 bpm sinus strip reads "sinus rhythm" 0.99).
  Reproduce it with `./gradlew :ecg-model:test -PfounderDump=<dir>`, which writes the tensors, then run the
  graph on those files and on `model_input_f32_b64` from the fixture.
* Inference: `org.samahealth.onboarding.ecg.FounderOnnx` in the app. The model file is optional: it is looked
  for in the APK assets and then in `<externalFilesDir>/model/ecgfounder_1lead_fp32.onnx`, so a phone can be
  given the file without a new build, and the app simply offers no pre-read when it is absent.
* Where it shows: the Quality tab's clip detail, behind "Research pre-read (study clinician)", with a line
  saying what it is. It is never on the participant summary.
* APK size: ONNX Runtime's native library is 17.5 MB for arm64 and 20 MB for each other ABI, so
  `android/app/build.gradle.kts` packages arm64-v8a only (add x86_64 there to run on an emulator). That makes
  the APK about 47 MB without the model. The 123 MB model is not bundled by default: the `model` job in
  `.github/workflows/onboarding.yml`, run by hand with `build_model: true`, downloads the weights, exports,
  checks torch against ONNX Runtime and uploads a separate APK with the model inside.

### Notes from the export (for reference)

* Model I/O: input `ecg`, float32 `[batch, 1, 5000]` (batch dynamic, length fixed); outputs `logits` and `probs`,
  float32 `[batch, 150]`; label i is line i + 1 of `configs/ecgfounder_tasks.txt`. Run all windows of a strip as
  one batch.
* The graph is the network only. The phone must reproduce steps 1-6 above: resample 300 -> 500 Hz (polyphase,
  as scipy `resample_poly(x, 5, 3)`), polarity check, 10 s windows, optional filter, z-score, window combination.
  The unfiltered setting needs only resampling and z-score, which is the simplest faithful port; record which
  setting the phone used, exactly as the laptop JSON does. Python should generate golden fixtures (strip in,
  window tensor and probabilities out) under `configs/` for the Kotlin port, as for the quality scorer.
* Runtime: ONNX Runtime Android (`com.microsoft.onnxruntime:onnxruntime-android`, full build; the graph uses
  Conv, MaxPool, Gemm, Einsum, Pad, Concat, Slice, ReduceMean, Sigmoid and a few shape ops, all standard ONNX).
  A reduced-operator build must include Einsum.
* Size and speed: 123 MB fp32 (copy it to app storage; do not bundle it in the APK by default). About 1.1 GMAC
  per 10 s window; the OpenHolter wrapper measured about 48 ms per window on one desktop CPU core with ONNX
  Runtime, so a 30 s strip (3 windows) should take well under a few seconds on a mid-range phone; measure it.
* int8: do not ship. OpenHolter measured max |delta p| about 0.76 for both dynamic and static int8 against fp32.
* Show the result to the operator only as "research output for clinician review", never on the participant
  summary (section 9).

## 5. Licences

* Code: ECGFounder is MIT (c) 2025 PKUDigitalHealth. The vendored Net1D in `palmppg/ecg/founder.py` keeps the
  licence text and the source URL in its module docstring; `configs/ecgfounder_tasks.txt` is upstream
  `tasks.txt` unchanged.
* Weights: published alongside the MIT code on Hugging Face, but they were trained on HEEDB (Harvard-Emory ECG
  Database) and other data with their own access terms. Confirm with the authors in writing that research use
  of the weights in this study is covered, and whether any HEEDB data-use terms carry over, before results are
  reported. Do not redistribute the checkpoint or the exported ONNX file outside the study team until that is
  settled.
