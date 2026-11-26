#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py — one-command orchestration of the whole skill (used for demo + fallback).

    python run_all.py --case-dir /input --work /app/work --out /app/output

Stages: prepare_case -> (annotations must already exist, or a heuristic extractor is used)
        -> build_graph -> query_graph -> export_graph -> finalize

If /app/work/annotations.json is absent, this script calls heuristic_extract.py to create a
first-pass annotation file so the pipeline still produces a graph (clearly marked as
heuristic in the run report). The LLM-quality path is: the agent writes annotations.json
itself following SKILL.md, then runs run_all.py with --no-heuristic.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(cmd, label):
    print(f"\n=== {label} ===")
    r = subprocess.run(cmd, text=True)
    if r.returncode != 0:
        print(f"[run_all] stage failed: {label} (exit {r.returncode})")
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", default=None)
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--out", default="/app/output")
    ap.add_argument("--annotations", default=None)
    ap.add_argument("--no-heuristic", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.work, exist_ok=True)
    os.makedirs(args.out, exist_ok=True)
    bundle = os.path.join(args.work, "case_bundle.json")
    ann = args.annotations or os.path.join(args.work, "annotations.json")
    graph = os.path.join(args.work, "graph.json")
    qres = os.path.join(args.work, "queries_result.json")

    cmd = [PY, os.path.join(HERE, "prepare_case.py"), "--out", bundle]
    if args.case_dir:
        cmd += ["--case-dir", args.case_dir]
    run(cmd, "Stage 1 prepare_case")

    if not os.path.exists(ann):
        if args.no_heuristic:
            print(f"[run_all] annotations missing at {ann} and --no-heuristic set: stopping.")
            sys.exit(3)
        run([PY, os.path.join(HERE, "heuristic_extract.py"), "--bundle", bundle, "--out", ann],
            "Stage 2 heuristic_extract (fallback)")

    run([PY, os.path.join(HERE, "build_graph.py"), "--bundle", bundle, "--annotations", ann,
         "--out", graph] + (["--strict"] if args.strict else []), "Stage 3 build_graph")
    run([PY, os.path.join(HERE, "query_graph.py"), "--graph", graph, "--out", qres], "Stage 4 query_graph")
    run([PY, os.path.join(HERE, "export_graph.py"), "--graph", graph, "--queries", qres,
         "--outdir", args.out], "Stage 5 export_graph")
    run([PY, os.path.join(HERE, "render_png.py"), "--graph", graph,
         "--out", os.path.join(args.out, "graph.png")], "Stage 5b render_png (optional)")
    run([PY, os.path.join(HERE, "finalize.py"), "--bundle", bundle, "--graph", graph,
         "--queries", qres, "--out", os.path.join(args.out, "result.json"), "--outdir", args.out],
        "Stage 6 finalize")
    print("\n[run_all] done. Inspect result.json.validation for honest status.")


if __name__ == "__main__":
    main()
