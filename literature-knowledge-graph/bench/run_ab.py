#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_ab.py — the measurement harness for the gain dimension.

Two subcommands:

    ab      run one case under two extraction conditions on the *same normalized input*, repeat,
            and emit a table of metrics (bench/ab_report.md + .json)
    budget  turn a case's size into a request/window model and recommend a --max-paragraphs cap

What `ab` does and does not claim
---------------------------------
The conditions differ only in the extraction step, because that is the step the Skill governs:

    baseline   heuristic_extract.py — deterministic, no Skill rules, no alias reasoning
    treatment  an annotations file produced under SKILL.md's rules

This is a *pipeline-level* control, reproducible offline and free. It is **not** the platform's
base-agent vs skill-agent comparison, and its numbers must not be reported as that. For a real
agent comparison, point either side at a command that writes annotations.json:

    --baseline-cmd  'python my_baseline_agent.py --input /input --out {out}'
    --treatment-cmd 'python my_skill_agent.py   --input /input --out {out}'

The harness then runs that command and measures whatever it produced.
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
PY = sys.executable
sys.path.insert(0, HERE)

import metrics as M  # noqa: E402

CHARS_PER_TOKEN = 4.0          # stated approximation, not a measurement
REQUESTS_FIXED = 5             # queries + review/repair + summary, outside the reading windows


def sh(args, timeout=900):
    t0 = time.time()
    r = subprocess.run([PY] + args, capture_output=True, text=True, timeout=timeout)
    return r, time.time() - t0


def prepare(case_dir, out_bundle, caps=None):
    args = [os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", case_dir, "--out", out_bundle]
    if caps:
        args += caps
    r, _ = sh(args)
    if r.returncode != 0:
        raise SystemExit(f"prepare_case failed: {r.stderr[-800:]}")
    return json.load(open(out_bundle, encoding="utf-8"))


def produce_annotations(kind, bundle, work, ref_annotations=None, cmd=None):
    """Return a path to an annotations.json for this condition."""
    os.makedirs(work, exist_ok=True)
    if cmd:
        out = os.path.join(work, f"ann_{kind}.json")
        filled = cmd.replace("{out}", out).replace("{bundle}", bundle).replace("{work}", work)
        r = subprocess.run(filled, shell=True, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or not os.path.exists(out):
            raise SystemExit(f"{kind} command produced no annotations: {r.stderr[-600:]}")
        return out
    if kind == "baseline":
        out = os.path.join(work, "ann_baseline.json")
        r, _ = sh([os.path.join(SCRIPTS, "heuristic_extract.py"), "--bundle", bundle, "--out", out])
        if r.returncode != 0:
            raise SystemExit(f"heuristic_extract failed: {r.stderr[-600:]}")
        return out
    return ref_annotations


def run_condition(bundle, annotations, work, out, queries_path=None):
    os.makedirs(work, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    g = os.path.join(work, "graph.json")
    q = os.path.join(work, "queries_result.json")
    t_total = 0.0
    for args in (
        ["build_graph.py", "--bundle", bundle, "--annotations", annotations, "--out", g],
        ["query_graph.py", "--graph", g, "--out", q] + (["--queries", queries_path] if queries_path else []),
        ["export_graph.py", "--graph", g, "--queries", q, "--outdir", out],
        ["finalize.py", "--bundle", bundle, "--graph", g, "--queries", q,
         "--out", os.path.join(out, "result.json"), "--outdir", out],
    ):
        r, dt = sh([os.path.join(SCRIPTS, args[0])] + args[1:])
        t_total += dt
        if r.returncode != 0:
            raise SystemExit(f"{args[0]} failed: {r.stderr[-600:]}")
    return M.compute(out, work, wall_s=t_total)


KEYS = ["status", "nodes", "edges", "typed_share", "node_types", "relation_types",
        "nodes_verified", "edges_verified", "evidence_coverage", "unresolved_endpoints",
        "merge_decisions", "kept_separate", "conflicts", "queries_answered",
        "queries_partial", "queries_undetermined", "query_hit_rate", "wall_s"]


def cmd_ab(args):
    root = args.out
    os.makedirs(root, exist_ok=True)
    bundle = os.path.join(root, "bundle.json")
    prep = prepare(args.case_dir, bundle)
    print(f"[ab] case: {prep.get('case_id')}  paragraphs={len(prep['paragraphs'])} "
          f"sources={len(prep.get('sources', []))}")

    conds = {
        "baseline": {"cmd": args.baseline_cmd, "ref": None},
        "treatment": {"cmd": args.treatment_cmd, "ref": args.annotations},
    }
    runs = {}
    for kind, c in conds.items():
        if kind == "treatment" and not c["ref"] and not c["cmd"]:
            raise SystemExit("treatment needs --annotations or --treatment-cmd")
        rows = []
        for i in range(args.repeats):
            work = os.path.join(root, kind, f"rep{i + 1}", "work")
            out = os.path.join(root, kind, f"rep{i + 1}", "out")
            ann = produce_annotations(kind, bundle, os.path.dirname(work), c["ref"], c["cmd"])
            m = run_condition(bundle, ann, work, out, args.queries)
            rows.append(m)
            print(f"[ab] {kind} rep{i + 1}: status={m['status']} nodes={m['nodes']} "
                  f"edges={m['edges']} cov={m['evidence_coverage']} t={m['wall_s']}s")
        runs[kind] = rows

    table = {}
    for kind, rows in runs.items():
        table[kind] = {}
        for k in KEYS:
            vals = [r.get(k) for r in rows if r.get(k) is not None]
            if not vals:
                table[kind][k] = None
            elif isinstance(vals[0], (int, float)):
                table[kind][k] = round(statistics.median(vals), 3)
            else:
                table[kind][k] = vals[0]

    report = {
        "case_id": prep.get("case_id"),
        "case_dir": os.path.abspath(args.case_dir),
        "paragraphs": len(prep["paragraphs"]),
        "sources": len(prep.get("sources", [])),
        "repeats": args.repeats,
        "conditions": {"baseline": "heuristic_extract.py (no Skill rules)",
                       "treatment": "annotations produced under SKILL.md"},
        "baseline_cmd": args.baseline_cmd, "treatment_cmd": args.treatment_cmd,
        "median": table, "runs": runs,
        "claim_limit": "pipeline-level control on one case; NOT the platform's base-vs-skill comparison",
    }
    jpath = os.path.join(root, "ab_report.json")
    json.dump(report, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    lines = [f"# A/B report — {prep.get('case_id')}", "",
             f"Input: `{os.path.abspath(args.case_dir)}` — {len(prep['paragraphs'])} paragraphs, "
             f"{len(prep.get('sources', []))} sources; {args.repeats} repeat(s) per condition.",
             "", "| metric | baseline (no Skill rules) | treatment (Skill rules) |",
             "|---|---|---|"]
    for k in KEYS:
        lines.append(f"| {k} | {table['baseline'].get(k)} | {table['treatment'].get(k)} |")
    lines += ["", "Baseline = `heuristic_extract.py`; treatment = annotations written under `SKILL.md`. "
                  "Both run the same build/query/finalize scripts on the same normalized bundle, so the "
                  "difference is attributable to the extraction step only.",
              "", "**What this is not**: the platform's base-agent vs skill-agent comparison. It is the "
                  "offline control we can run on any case, any number of times, for free."]
    mpath = os.path.join(root, "ab_report.md")
    open(mpath, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"[ab] wrote {jpath} and {mpath}")
    return 0


def cmd_budget(args):
    bundle_path = args.bundle
    tmp = None
    if not bundle_path:
        tmp = tempfile.mkdtemp(prefix="lkg_budget_")
        bundle_path = os.path.join(tmp, "bundle.json")
        prepare(args.case_dir, bundle_path)
    bundle = json.load(open(bundle_path, encoding="utf-8"))
    paras = bundle["paragraphs"]
    chars = sum(len(p["text"]) for p in paras)
    avg = chars / len(paras) if paras else 0
    windows = -(-chars // args.window_chars)
    requests = windows + REQUESTS_FIXED
    tokens_in = round(args.window_chars / CHARS_PER_TOKEN)
    wall_model = windows * args.seconds_per_request + args.fixed_seconds

    # largest prefix (in reading order) whose window count still fits a budget
    order = sorted(paras, key=lambda p: (p["source_id"], p.get("order_in_source", 0)))

    def prefix_for_windows(budget_windows):
        keep, acc = 0, 0
        for p in order:
            acc += len(p["text"])
            if -(-acc // args.window_chars) > max(1, budget_windows):
                break
            keep += 1
        return keep

    budget_windows = max(1, args.max_requests - REQUESTS_FIXED)
    windows_by_time = int(max(1.0, (args.max_seconds - args.fixed_seconds)) // args.seconds_per_request)
    cap_req = prefix_for_windows(budget_windows)
    cap_time = prefix_for_windows(windows_by_time)
    recommended = min(len(paras), cap_req, cap_time)

    out = {
        "bundle": bundle_path, "paragraphs": len(paras), "chars": chars,
        "avg_chars_per_paragraph": round(avg, 1),
        "window_chars": args.window_chars, "window_tokens_est": tokens_in,
        "windows": windows, "requests_model": requests, "max_requests": args.max_requests,
        "windows_allowed_by_requests": budget_windows,
        "windows_allowed_by_time": windows_by_time,
        "seconds_per_request": args.seconds_per_request,
        "wall_time_model_s": round(wall_model, 1), "wall_time_budget_s": args.max_seconds,
        "fits_time": wall_model <= args.max_seconds,
        "cap_paragraphs_by_requests": cap_req,
        "cap_paragraphs_by_time": cap_time,
        "recommended_max_paragraphs": recommended,
        "token_cap_per_response": 16384,
        "token_headroom": 16384 - tokens_in,
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json_out:
        json.dump(out, open(args.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ab", help="two-condition comparison on one case")
    a.add_argument("--case-dir", required=True)
    a.add_argument("--annotations", help="treatment annotations (the Skill path)")
    a.add_argument("--baseline-cmd", help="command writing annotations.json for the baseline condition")
    a.add_argument("--treatment-cmd", help="command writing annotations.json for the treatment condition")
    a.add_argument("--queries", help="fixed query set, so both conditions answer the same questions")
    a.add_argument("--repeats", type=int, default=3)
    a.add_argument("--out", required=True)
    a.set_defaults(func=cmd_ab)

    b = sub.add_parser("budget", help="request/window model and a --max-paragraphs recommendation")
    b.add_argument("--case-dir")
    b.add_argument("--bundle")
    b.add_argument("--window-chars", type=int, default=6000)
    b.add_argument("--max-requests", type=int, default=60)
    b.add_argument("--seconds-per-request", type=float, default=20.0)
    b.add_argument("--fixed-seconds", type=float, default=60.0)
    b.add_argument("--max-seconds", type=float, default=900.0)
    b.add_argument("--json-out")
    b.set_defaults(func=cmd_budget)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
