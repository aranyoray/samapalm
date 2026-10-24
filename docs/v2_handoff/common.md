# Shared rules for every v2 build agent

Repository: /home/user/samapalm (git, branch master). Python venv: /home/user/samapalm/.venv/bin/python
(run tests with `.venv/bin/python -m pytest -q -p no:cacheprovider <files>`). Kotlin/Gradle: `cd android &&
./gradlew --offline -q :crf-core:test` (Gradle works offline from the local cache; Google Maven is blocked, so
`:app` cannot be built here). Android app compile check without the SDK:
`/tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/kc/compile_app.sh`
(read kc/README.txt next to it first).

The design contract is docs/onboarding_v2_design.md. Read it fully before you start. Ids, file names, function
signatures and value formats in it are contracts other agents code against in parallel; do not rename them. If
the contract is wrong or incomplete for your part, implement the closest faithful version, and list the deviation
in your final report.

Rules:
* Stay inside the files you own (listed in your task). Other agents are editing other files at the same time. Do
  not run `git add/commit/push/stash/checkout/reset` - the lead integrates and commits.
* Match the surrounding code: comment density, naming, idiom. Keep comments short and factual.
* Never use the banned vocabulary listed in palmppg/core/lint.py in code, comments, labels or docs:
  tests/test_core_lint.py enforces it repository-wide. Say "screening heuristic", "research use",
  "for clinician review" instead.
* Tests must check real behaviour against independently known answers (synthetic signals with known heart rate,
  hand-computed thresholds), not just "runs without error".
* When Python and Kotlin implement the same logic, Python generates golden fixtures (a tools/ script writes JSON
  under configs/) and both test suites check them.
* Before you finish: run every test file you touched (and tests/test_core_lint.py), and fix failures. Report
  honestly what passed, what you could not run, and any deviation from the contract.
* Final report (your last message): files changed, tests run with pass/fail counts, deviations, open issues. Under
  600 words.
