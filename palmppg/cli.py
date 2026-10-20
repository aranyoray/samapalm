"""Command-line entry point. Sub-commands are wired to the pipeline, experiments and reports modules.

    palmppg synth cohort --root work/synthetic --n 3 [--small]
    palmppg synth positive-control [--out work/positive_control]
    palmppg bench selftest | bench report <trials_dir>
    palmppg pipeline run --study-root <dir> [--limit N] [--study-id ID]
    palmppg features build --study-root <dir>
    palmppg augment study --study-root <dir> --n 100
    palmppg experiments run <E1> | run-all
    palmppg gonogo [--interim]
    palmppg reports build
    palmppg crf pull --study-root <dir>
    palmppg lint
"""
from __future__ import annotations

import argparse
import sys


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default=None, help="pipeline.yaml override path")
    p.add_argument("--work-root", default=None)
    p.add_argument("--seed", type=int, default=None)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="palmppg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="synthetic data and positive control")
    ss = s.add_subparsers(dest="sub", required=True)
    c = ss.add_parser("cohort")
    c.add_argument("--root", default="work/synthetic")
    c.add_argument("--n", type=int, default=3)
    c.add_argument("--small", action="store_true")
    c.add_argument("--seed", type=int, default=1)
    pc = ss.add_parser("positive-control")
    pc.add_argument("--out", default="work/positive_control")
    pc.add_argument("--seed", type=int, default=1)
    pc.add_argument("--small", action="store_true")

    b = sub.add_parser("bench", help="bench sync acceptance")
    bs = b.add_subparsers(dest="sub", required=True)
    bs.add_parser("selftest")
    br = bs.add_parser("report")
    br.add_argument("trials_dir")

    p = sub.add_parser("pipeline", help="per-participant processing")
    ps = p.add_subparsers(dest="sub", required=True)
    pr = ps.add_parser("run")
    pr.add_argument("--study-root", required=True)
    pr.add_argument("--study-id", default=None)
    pr.add_argument("--limit", type=int, default=None)
    pr.add_argument("--cameras", default="pi,phone,pi_proxy")
    _add_common(pr)

    f = sub.add_parser("features", help="feature store")
    fs = f.add_subparsers(dest="sub", required=True)
    fb = fs.add_parser("build")
    fb.add_argument("--study-root", required=True)
    _add_common(fb)

    a = sub.add_parser("augment", help="synthetic augmentation study")
    asub = a.add_subparsers(dest="sub", required=True)
    ast = asub.add_parser("study")
    ast.add_argument("--study-root", required=True)
    ast.add_argument("--n", type=int, default=100)
    ast.add_argument("--smoke", action="store_true", help="few clips, few transforms, to prove the runner")
    _add_common(ast)

    e = sub.add_parser("experiments", help="E0..E17")
    es = e.add_subparsers(dest="sub", required=True)
    er = es.add_parser("run")
    er.add_argument("names", nargs="+")
    _add_common(er)
    ea = es.add_parser("run-all")
    _add_common(ea)

    g = sub.add_parser("gonogo", help="frozen go/no-go dashboard")
    g.add_argument("--interim", action="store_true")
    _add_common(g)

    r = sub.add_parser("reports", help="regenerate every table and figure")
    rs = r.add_subparsers(dest="sub", required=True)
    rb = rs.add_parser("build")
    _add_common(rb)

    c = sub.add_parser("crf", help="onboarding-app CRFs from Supabase")
    cs = c.add_subparsers(dest="sub", required=True)
    cp = cs.add_parser("pull", help="write participants/<PID>/crf.json from Supabase (credentials from SUPABASE_* env vars)")
    cp.add_argument("--study-root", required=True)

    sub.add_parser("lint", help="banned vocabulary scan")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from palmppg.pipeline import commands

    return commands.dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
