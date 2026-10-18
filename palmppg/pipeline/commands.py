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
            out = Path("reports/bench_sync_report.md")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rep["markdown"] if isinstance(rep, dict) and "markdown" in rep else str(rep), encoding="utf-8")
            print(out.read_text())
            return 0
        trials = bench.load_trials(args.trials_dir) if hasattr(bench, "load_trials") else None
        md = bench.bench_trials_report(trials)
        Path("reports/bench_sync_report.md").write_text(md if isinstance(md, str) else md["markdown"], encoding="utf-8")
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
