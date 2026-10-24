# Task: ECGFounder (single-lead) offline runner, ONNX export, and an on-phone inference hook

Read /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md first,
then docs/onboarding_v2_design.md section 9, palmppg/ecg/atc.py, palmppg/ecg/clean.py, palmppg/cli.py and
palmppg/pipeline/commands.py (how subcommands are wired).

Research already done (trust it, cite these URLs in docstrings where useful):
* Official code: https://github.com/PKUDigitalHealth/ECGFounder (MIT). Files reachable here through
  raw.githubusercontent.com (github.com and huggingface.co are blocked): master/net1d.py, dataset.py, util.py,
  tasks.txt, ptbxl_eval.py, LICENSE. Local copies: scratchpad/ecgf_pku_master/ and a third-party wrapper with an
  ONNX export fix at scratchpad/openholter/ (scratchpad = /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad).
* Weights: huggingface PKUDigitalHealth/ECGFounder, file 1_lead_ECGFounder.pth (~370 MB incl. optimiser state;
  load `torch.load(p, map_location='cpu', weights_only=False)['state_dict']`). Cannot be downloaded here.
* Net1D(in_channels=1, base_filters=64, ratio=1, filter_list=[64,160,160,400,400,1024,1024],
  m_blocks_list=[2,2,2,3,3,4,4], kernel_size=16, stride=2, groups_width=16, verbose=False, use_bn=False,
  use_do=False, n_classes=150); ~30.8M parameters; sigmoid outputs named by tasks.txt (line i = output i-1).
* Input: (N,1,5000) = 10 s at 500 Hz, z-score per window ((x-mean)/(std+1e-8)). dataset.py additionally applies
  util.filter_bandpass (50 Hz notch Q=30, 4th-order Butterworth 0.67-40 Hz filtfilt, minus 0.4 s running median);
  ptbxl_eval.py applies none. Make the filter a switch (default: dataset.py filtering) and record which was used.
* ONNX: standard ops only; export with fixed length 5000, opset 17; ONNX Runtime fuses the zero Pad into MaxPool
  padding with -inf (logit errors up to 0.8): build that pad as a Concat of zeros (see openholter export_onnx.py).
* Strip handling: Kardia/BLE lead I at 300 Hz, 30 s: check polarity, resample_poly(x,5,3) -> 500 Hz, three
  non-overlapping 10 s windows (or 5 s step), combine with a rule fixed in advance: mean for sustained rhythms,
  max for ectopic beats.
* No published Indian/South-Asian evaluation exists; outputs are research annotations for the study clinician
  and the clinician-read comparison (hypothesis H6), never participant results without ethics approval and a
  clinician over-read.

You own (create):
* palmppg/ecg/founder.py: vendored Net1D (port net1d.py faithfully, keep the MIT notice and source URL in the
  module docstring), RHYTHM_LABELS subset (indices: 1 NORMAL SINUS RHYTHM, 3 SINUS RHYTHM, 4 SINUS BRADYCARDIA,
  5 ATRIAL FIBRILLATION, 6 SINUS TACHYCARDIA, 9 PVC, 16 PAC, 19 PSVC, 32 ATRIAL FLUTTER, 33 MARKED SINUS
  BRADYCARDIA, 34 WITH SINUS ARRHYTHMIA, 39 UNDETERMINED RHYTHM, 49 JUNCTIONAL RHYTHM, 79 1ST DEGREE AV BLOCK,
  91 BIGEMINY, 93 SVT, 98 VT, 142 SINUS PAUSE - verify against the downloaded tasks.txt), a vendored copy of
  tasks.txt as configs/ecgfounder_tasks.txt, load_model(weights_path) (asserts no missing keys, records sha256),
  preprocess(x, fs, filtered=True) -> windows, predict(model, x_mv, fs) -> per-label probabilities + per-window
  probs + metadata (weights sha, filter flag, windows, polarity flip), run on a folder of participants (ATC files
  via palmppg.ecg.atc, or BLE <clip>_ecg_samples.csv) writing ecg_founder.json per clip.
* CLI: `palmppg ecg founder --weights PATH (--atc FILE | --participants DIR) [--unfiltered]` wired like other
  subcommands (edit palmppg/cli.py and palmppg/pipeline/commands.py minimally; only add your subcommand).
* tools/export_ecgfounder_onnx.py: weights -> fp32 ONNX (opset 17, fixed 5000, Concat pad fix), then checks
  ONNX Runtime vs torch on random and synthetic inputs (max |delta p| < 1e-4) and writes a JSON report.
  onnx/onnxruntime are not installed: install them into the venv with pip (PyPI is reachable) and add them as an
  optional extra in pyproject.toml ([project.optional-dependencies] ecgmodel = [...]).
* tests/test_ecg_founder.py: with RANDOMLY INITIALISED weights (no download): architecture shape (N,150),
  parameter count ~30.8M, preprocessing (resampling 300->500, window count for 30 s, z-score stats, polarity
  flip on an inverted synthetic ECG), window combination rules, the Concat-pad fix gives torch == ONNX Runtime
  within 1e-4 (skip only if onnxruntime import fails), and loading a saved random state_dict through load_model.
  Mark slow tests with the existing `deep` marker (see pyproject.toml markers).
* docs/ecg_model.md: how to download the weights on a laptop, run the CLI, export ONNX, licence notes (code MIT;
  confirm weights/HEEDB terms with the authors), and the ethics position on returning results.

Not yours: everything else, including the Android app (the lead will wire on-phone inference later from your
ONNX export notes). Run your tests, the lint test, and the full pytest suite once at the end.
