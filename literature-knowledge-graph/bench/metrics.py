#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""metrics.py — turn one run directory into one row of numbers.

Every metric is read from files the pipeline already writes, so a reviewer can recompute it
without rerunning the model step:

    result.json         status, validation, merge_log, conflict_log, uncertainty
    graph.json          nodes, edges, conflicts
    queries_result.json per-query status
    evidence.csv        one row per evidence record

    python3 bench/metrics.py --run-dir /app/output
    python3 bench/metrics.py --run-dir /app/output --json

Nothing here invents a value: a metric whose source is missing is reported as null and listed
under `missing`, rather than reported as 0.
"""
import argparse
import csv
import json
import os
import sys


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def compute(run_dir, work_dir=None, wall_s=None):
    """Metrics from a finished run. `work_dir` defaults to run_dir (graph.json may live there)."""
    work_dir = work_dir or run_dir
    result = _load(os.path.join(run_dir, "result.json"))
    graph = _load(os.path.join(work_dir, "graph.json"))
    queries = _load(os.path.join(work_dir, "queries_result.json")) or \
        _load(os.path.join(run_dir, "queries_result.json"))

    m, missing = {}, []
    for name, val in (("result", result), ("graph", graph), ("queries", queries)):
        if val is None:
            missing.append(name)

    nodes = (graph or {}).get("nodes", [])
    edges = (graph or {}).get("edges", [])
    conflicts = (graph or {}).get("conflict_log", [])

    m["status"] = (result or {}).get("status")
    m["nodes"] = len(nodes) if graph else None
    m["edges"] = len(edges) if graph else None
    if graph:
        m["nodes_typed"] = sum(1 for n in nodes if n.get("type") not in (None, "", "other"))
        m["typed_share"] = round(m["nodes_typed"] / len(nodes), 3) if nodes else None
        m["node_types"] = len({n.get("type") for n in nodes if n.get("type")})
        m["relation_types"] = len({e.get("type") for e in edges if e.get("type")})
        m["nodes_verified"] = sum(1 for n in nodes if n.get("evidence_status") == "verified")
        m["edges_verified"] = sum(1 for e in edges if e.get("evidence_status") == "verified")
        m["unresolved_endpoints"] = sum(1 for c in conflicts if c.get("kind") == "edge_endpoint_missing")
        m["merge_decisions"] = len((graph or {}).get("merge_log", []))
        m["kept_separate"] = sum(1 for x in (graph or {}).get("merge_log", [])
                                 if x.get("decision") == "kept_separate")
        m["conflicts"] = len(conflicts)
        m["conflicts_by_kind"] = _count(conflicts, "kind")
    if result:
        v = result.get("validation") or {}
        m["evidence_coverage"] = v.get("evidence_coverage")
        m["merge_log_entries"] = len(result.get("merge_log") or [])
        m["conflict_log_entries"] = len(result.get("conflict_log") or [])
        m["uncertainty_entries"] = len(result.get("uncertainty") or [])
        m["status_reasons"] = result.get("status_reasons") or []
    if queries:
        m["queries_total"] = queries.get("n_queries")
        m["queries_answered"] = queries.get("n_answered")
        m["queries_partial"] = queries.get("n_partial")
        m["queries_undetermined"] = queries.get("n_undetermined")
        total = queries.get("n_queries") or 0
        answered = (queries.get("n_answered") or 0) + (queries.get("n_partial") or 0)
        m["query_hit_rate"] = round(answered / total, 3) if total else None

    ev = os.path.join(run_dir, "evidence.csv")
    if os.path.exists(ev):
        rows = list(csv.DictReader(open(ev, encoding="utf-8")))
        m["evidence_rows"] = len(rows)
        m["evidence_quote_share"] = round(
            sum(1 for r in rows if (r.get("quote") or "").strip()) / len(rows), 3) if rows else None
        m["evidence_match"] = _count(rows, "match")
    m["wall_s"] = round(wall_s, 1) if wall_s is not None else None
    m["missing"] = missing
    return m


def _count(rows, key):
    out = {}
    for r in rows:
        v = r.get(key)
        if v:
            out[v] = out.get(v, 0) + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    m = compute(args.run_dir, args.work_dir)
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return 0
    for k, v in m.items():
        print(f"{k:>22}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
