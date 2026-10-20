"""CLI dispatch (palmppg.cli builds the parser; this module runs the commands with lazy imports)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from palmppg.core.config import load_pipeline_config
from palmppg.core.paths import StudyLayout, WorkLayout


def _cfg(args):
    cfg = load_pipeline_config()
    if getattr(args, "config", None):
        from palmppg.core.config import load_config

        cfg = load_config(Path("configs/pipeline.yaml"), args.config)
    if getattr(args, "work_root", None):
        cfg = cfg.with_overrides({"paths": {"work_root": args.work_root}})
    return cfg


def dispatch(args) -> int:
    cmd, sub = args.cmd, getattr(args, "sub", None)
    if cmd == "lint":
        from palmppg.core.lint import scan_path

        hits = scan_path(Path.cwd())
        for f, hs in hits.items():
            for line, word, text in hs:
                print(f"{f}:{line}: {word}: {text}")
        print(f"{sum(len(v) for v in hits.values())} hit(s)")
        return 1 if hits else 0

    if cmd == "crf" and sub == "pull":
        from palmppg.capture.crf_pull import pull

        r = pull(args.study_root)
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in r.items()}, indent=1, default=str))
        return 3 if r["problems"] else 0

    if cmd == "synth" and sub == "cohort":
        from palmppg.synth.cohort import make_cohort

        r = make_cohort(args.root, args.n, args.seed, load_pipeline_config(), small=args.small)
        print(json.dumps({k: v for k, v in r.items() if k != "participants"}, indent=1, default=str))
        return 0
    if cmd == "synth" and sub == "positive-control":
        from palmppg.pipeline.positive_control import run_positive_control

        r = run_positive_control(args.out, load_pipeline_config(), seed=args.seed, small=args.small)
        print(Path(args.out, "positive_control.md").read_text())
        return 0 if r["pass"] else 3

    if cmd == "bench":
        from palmppg.ingest import bench

        if sub == "selftest":
            rep = bench.synthetic_bench_selftest(n_trials=20, seed=1)
            print(rep["markdown"])
            return 0 if rep["n_pass"] == rep["n_trials"] else 3
        # hardware trials: one JSON file per trial in trials_dir, in the bench_trials_report trial shape
        files = sorted(Path(args.trials_dir).glob("*.json"))
        if not files:
            print(f"no trial JSON files in {args.trials_dir}", file=sys.stderr)
            return 2
        trials = [json.loads(f.read_text(encoding="utf-8")) for f in files]
        bench.bench_trials_report(trials, hardware=True)
        print("wrote reports/bench_sync_report.md")
        return 0

    if cmd == "pipeline" and sub == "run":
        from palmppg.pipeline.run_participant import run_cohort

        cfg = _cfg(args)
        work = WorkLayout(cfg.get("paths.work_root"))
        df = run_cohort(StudyLayout(args.study_root), work, cfg, limit=args.limit,
                        study_ids=[args.study_id] if args.study_id else None, cameras=tuple(args.cameras.split(",")))
        print(df.to_string())
        return 0 if bool(df["ok"].all()) else 3

    if cmd == "features" and sub == "build":
        from palmppg.features.build import build_feature_store

        cfg = _cfg(args)
        r = build_feature_store(cfg.get("paths.work_root"), StudyLayout(args.study_root), cfg)
        print(json.dumps(r, indent=1, default=str))
        return 0

    if cmd == "augment" and sub == "study":
        from palmppg.experiments.augmentation_study import run_augmentation_study

        cfg = _cfg(args)
        r = run_augmentation_study(StudyLayout(args.study_root), WorkLayout(cfg.get("paths.work_root")), cfg, n_clips=args.n, smoke=args.smoke)
        print(json.dumps({k: v for k, v in r.items() if k in ("n_clips", "n_transforms", "report")}, indent=1, default=str))
        return 0

    if cmd == "experiments":
        from palmppg.experiments.runner import run_all, run_experiments

        cfg = _cfg(args)
        names = None if sub == "run-all" else args.names
        res = run_all(cfg) if names is None else run_experiments(names, cfg)
        print(json.dumps({k: (v.get("status") if isinstance(v, dict) else str(v)) for k, v in res.items()}, indent=1))
        return 0

    if cmd == "gonogo":
        from palmppg.experiments.gonogo import run_gonogo

        cfg = _cfg(args)
        r = run_gonogo(cfg, interim=args.interim)
        print(r["markdown"])
        return 0

    if cmd == "reports" and sub == "build":
        from palmppg.reports.build import build_all_reports

        cfg = _cfg(args)
        paths = build_all_reports(cfg)
        for p in paths:
            print(p)
        return 0

    print(f"unknown command {cmd} {sub}", file=sys.stderr)
    return 2
