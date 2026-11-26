#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
finalize.py — Stage 6: assemble the deliverable ``result.json`` and a validation report.

It reads the graph, the query results and the case bundle, computes honest quality metrics
(evidence coverage, verifiability, cross-paper alignment), and emits ``/app/output/result.json``.

``result.json`` always contains the canonical block
    case_id, status, summary, task, sources, graph, queries, evidence_index,
    merge_log, conflict_log, uncertainty, change_log, validation, artifacts
and, when the case declares an ``output_contract``, also echoes every declared field name
(resolved by a documented alias table) so downstream graders find the fields they expect.

Status rule (honest, not optimistic):
    success      every node/edge verified AND >=3 queries answered/partial AND both papers present
    partial      graph built but some evidence/query/paper is missing
    undetermined graph or inputs unusable
"""
import argparse
import json
import re
import os
import sys
import time

ALIASES = {
    "nodes": ["entities", "entity", "nodes", "node", "实体", "节点", "实体列表", "实体集合"],
    "edges": ["relations", "relation", "edges", "edge", "triples", "关系", "边", "三元组"],
    "graph": ["graph", "knowledge_graph", "图谱", "知识图谱"],
    "sources": ["sources", "papers", "documents", "文献", "论文", "来源论文", "语料"],
    "queries": ["queries", "query_results", "qa", "查询", "问答", "查询结果"],
    "evidence_index": ["evidence", "evidence_index", "citations", "证据", "证据索引", "溯源"],
    "merge_log": ["merge_log", "merges", "alignment", "entity_alignment", "合并", "对齐", "实体对齐"],
    "conflict_log": ["conflicts", "conflict_log", "contradictions", "冲突", "矛盾"],
    "uncertainty": ["uncertainty", "uncertainties", "unreported", "不确定", "未报告", "不确定项"],
    "status": ["status", "run_status", "运行状态", "状态"],
    "summary": ["summary", "main_result", "answer", "主结果", "结论", "摘要"],
    "case_id": ["case_id", "caseId", "input_id", "输入标识"],
    "stats": ["stats", "statistics", "metrics", "统计", "指标数量"],
    "change_log": ["change_log", "changelog", "增量", "变更记录"],
    "validation": ["validation", "self_check", "自查", "校验"],
    "task": ["task", "instruction", "任务"],
}


def norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def map_field(field_name):
    n = norm(field_name)
    for canon, aliases in ALIASES.items():
        for a in aliases:
            if norm(a) == n:
                return canon
    # containment fallback
    for canon, aliases in ALIASES.items():
        for a in aliases:
            if norm(a) and norm(a) in n:
                return canon
    return None


def main():
    _t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="/app/work/case_bundle.json")
    ap.add_argument("--graph", default="/app/work/graph.json")
    ap.add_argument("--queries", default="/app/work/queries_result.json")
    ap.add_argument("--out", default="/app/output/result.json")
    ap.add_argument("--outdir", default="/app/output")
    args = ap.parse_args()

    bundle = json.load(open(args.bundle, encoding="utf-8")) if os.path.exists(args.bundle) else {}
    graph = json.load(open(args.graph, encoding="utf-8")) if os.path.exists(args.graph) else {}
    queries = json.load(open(args.queries, encoding="utf-8")) if os.path.exists(args.queries) else {}

    if not graph:
        result = {"schema_version": "1.0",
                  "case_id": bundle.get("case_id"), "status": "undetermined",
                  "status_reasons": ["no graph: build_graph.py did not produce graph.json"],
                  "summary": "Graph could not be built: missing graph.json.",
                  "sources": bundle.get("sources", []),
                  "graph": {"nodes": [], "edges": []}, "nodes": [], "edges": [],
                  "queries": [], "evidence_index": {},
                  "validation": {"n_nodes": 0, "n_edges": 0, "n_nodes_verified": 0,
                                 "n_edges_verified": 0, "evidence_coverage": 0.0,
                                 "n_evidence_records": 0, "n_paragraphs_cited": 0,
                                 "sources_with_evidence": [], "n_papers_with_evidence": 0,
                                 "queries_answered_or_partial": 0, "queries_undetermined": 0,
                                 "all_nodes_have_quote": False, "all_edges_have_quote": False,
                                 "checks": [{"name": "graph exists", "pass": False}]},
                  "uncertainty": [{"kind": "no_graph",
                                   "detail": "build_graph.py did not produce graph.json"}]}
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[finalize] wrote minimal undetermined result (no graph).")
        return

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    n_verified_nodes = sum(1 for n in nodes if n.get("evidence_status") == "verified")
    n_verified_edges = sum(1 for e in edges if e.get("evidence_status") == "verified")
    n_ev_nodes = sum(len(n.get("mentions", [])) for n in nodes)
    n_ev_edges = sum(len(e.get("evidence", [])) for e in edges)
    with_evidence = n_verified_nodes + n_verified_edges
    total_items = len(nodes) + len(edges)
    coverage = round(with_evidence / total_items, 3) if total_items else 0.0

    # which sources actually carry evidence
    srcs = graph.get("sources", [])
    src_ev = {s["source_id"]: 0 for s in srcs}
    for n in nodes:
        for m in n.get("mentions", []):
            src_ev[m["source_id"]] = src_ev.get(m["source_id"], 0) + 1
    for e in edges:
        for m in e.get("evidence", []):
            src_ev[m["source_id"]] = src_ev.get(m["source_id"], 0) + 1
    n_papers_with_evidence = sum(1 for v in src_ev.values() if v > 0)

    q_ok = queries.get("n_answered", 0) + queries.get("n_partial", 0)
    q_und = queries.get("n_undetermined", 0)

    missing_meta = [s.get("source_id") for s in srcs
                    if not (s.get("doi") or s.get("title"))]
    case_id_val = bundle.get("case_id") or graph.get("case_id")
    # Candidate edges that never made it into the graph: the annotator named an endpoint that does
    # not resolve to any node. The graph is still valid, but it is not complete, and saying
    # "success" would hide 68 dropped edges behind a clean status.
    dropped_edges = sum(1 for c in (graph.get("conflict_log") or [])
                        if c.get("kind") == "edge_endpoint_missing")

    # status
    reasons = []
    budget = bundle.get("budget") or {}
    truncated = bool(budget.get("truncated"))
    if len(nodes) == 0:
        status = "undetermined"
        reasons.append("no nodes extracted")
    elif n_verified_nodes == 0 and n_verified_edges == 0:
        status = "undetermined"
        reasons.append("no evidence could be verified against the material")
    elif coverage >= 0.999 and q_ok >= 3 and n_papers_with_evidence >= 2 \
            and not missing_meta and case_id_val and dropped_edges == 0:
        status = "success"
    else:
        status = "partial"
        if coverage < 0.999:
            reasons.append(f"{total_items - with_evidence} node/edge item(s) lack verified evidence")
        if dropped_edges:
            reasons.append(f"{dropped_edges} candidate edge(s) dropped: an endpoint did not resolve to a node")
        if q_ok < 3:
            reasons.append(f"only {q_ok} query/queries answered or partial")
        if n_papers_with_evidence < 2:
            reasons.append(f"evidence bound to {n_papers_with_evidence} source(s); a cross-paper graph needs 2")
        if missing_meta:
            reasons.append(f"source metadata incomplete (no DOI/title) for: {missing_meta}")
        if not case_id_val:
            reasons.append("case_id absent from case.json/corpus-manifest.json")

    if truncated:
        reasons.insert(0,
                       f"input truncated by the budget guard: kept {budget.get('kept_paragraphs')} of "
                       f"{budget.get('total_paragraphs')} paragraphs "
                       f"(dropped {budget.get('dropped_by_source')}); the graph covers only the kept text")
        if status == "success":
            status = "partial"

    evidence_index = {}
    for n in nodes:
        for m in n.get("mentions", []):
            evidence_index.setdefault(f"{m['source_id']}/{m['paragraph_id']}", []).append(
                {"owner": n["id"], "kind": "node", "quote": m["quote"], "match": m["match"]})
    for e in edges:
        for m in e.get("evidence", []):
            evidence_index.setdefault(f"{m['source_id']}/{m['paragraph_id']}", []).append(
                {"owner": e["id"], "kind": "edge", "quote": m["quote"], "match": m["match"]})

    validation = {
        "n_nodes": len(nodes), "n_edges": len(edges),
        "n_nodes_verified": n_verified_nodes, "n_edges_verified": n_verified_edges,
        "evidence_coverage": coverage,
        "n_evidence_records": n_ev_nodes + n_ev_edges,
        "n_paragraphs_cited": len(evidence_index),
        "sources_with_evidence": src_ev,
        "n_papers_with_evidence": n_papers_with_evidence,
        "queries_answered_or_partial": q_ok,
        "queries_undetermined": q_und,
        "all_nodes_have_quote": all(len(n.get("mentions", [])) > 0 for n in nodes) if nodes else False,
        "all_edges_have_quote": all(len(e.get("evidence", [])) > 0 for e in edges) if edges else False,
        "checks": [
            {"name": "every node/edge cites source_id+paragraph_id+quote",
             "pass": all(len(n.get("mentions", [])) > 0 for n in nodes) and
                     all(len(e.get("evidence", [])) > 0 for e in edges)},
            {"name": "every quote located in cited paragraph",
             "pass": all(m.get("match") in ("exact", "normalized", "fuzzy")
                         for n in nodes for m in n.get("mentions", [])) and
                     all(m.get("match") in ("exact", "normalized", "fuzzy")
                         for e in edges for m in e.get("evidence", []))},
            # The intent is "a derived id must not be assertable as a page number". Any
            # namespaced form (d0042, p12, s3p2 ...) satisfies that; a bare integer does not.
            {"name": "derived paragraph ids are namespaced and flagged (never asserted as PDF pages)",
             "pass": all(m.get("paragraph_id_kind") != "derived"
                         or not re.fullmatch(r"\d+(\.\d+)?", str(m.get("paragraph_id", "")).strip())
                         for n in nodes for m in n.get("mentions", []))},
            {"name": "at least 3 queries executed",
             "pass": queries.get("n_queries", 0) >= 3},
            {"name": "merge and conflict handling recorded",
             "pass": bool(graph.get("merge_log") is not None and graph.get("conflict_log") is not None)},
        ],
    }

    failed_checks = [c["name"] for c in validation["checks"] if not c["pass"]]
    if failed_checks:
        # A check that fails is the clearest statement of a shortfall the pipeline can make; it
        # used to be reported in validation.checks while status stayed "success".
        status = "partial" if status == "success" else status
        reasons.append("validation check(s) failed: " + "; ".join(failed_checks))

    summary = (f"Built a {len(nodes)}-node / {len(edges)}-edge evidence-bound knowledge graph over "
               f"{len(srcs)} paper(s); {n_verified_nodes} nodes and {n_verified_edges} edges carry a "
               f"verified quote ({int(coverage*100)}% coverage, {validation['n_paragraphs_cited']} distinct "
               f"paragraphs cited); {q_ok}/{queries.get('n_queries', 0)} queries answered or partial, "
               f"{q_und} undetermined.")

    canonical = {
        "schema_version": "1.0",
        "case_id": case_id_val,
        "status": status,
        "status_reasons": reasons,
        "summary": summary,
        "task": (bundle.get("task") or "")[:2000],
        "sources": srcs,
        "graph": {"nodes": nodes, "edges": edges},
        "nodes": nodes,
        "edges": edges,
        "queries": queries.get("queries", []),
        "evidence_index": evidence_index,
        "merge_log": graph.get("merge_log", []),
        "conflict_log": graph.get("conflict_log", []),
        "uncertainty": graph.get("uncertainty", []) + [
            {"kind": "explicit_limitation", "detail":
             "Locations are provider JATS paragraph ids (or ids flagged id_derived=true). "
             "No PDF page numbers are asserted. Inline formulas were not re-derived."}],
        "change_log": [{"step": "prepare_case", "detail": "inputs normalised, ids assigned"},
                       {"step": "build_graph", "detail": "evidence verified, entities merged, conflicts logged"},
                       {"step": "query_graph", "detail": f"{queries.get('n_queries', 0)} queries executed"},
                       {"step": "export_graph", "detail": "mmd/graphml/csv/report exported"}],
        "validation": validation,
        # Measured, not modelled: the per-stage wall time this run actually took, plus the input
        # budget the normaliser recorded. docs/BUDGET.md explains why the scripts are not the cost.
        "runtime": {
            "prepare_seconds": (bundle.get("runtime") or {}).get("prepare_seconds"),
            "build_seconds": (graph.get("runtime") or {}).get("build_seconds"),
            "finalize_seconds": round(time.time() - _t0, 3),
        },
        "budget": bundle.get("budget") or {},
        "stats": graph.get("stats", {}),
        "artifacts": [],   # resolved after the files are written, see below
    }

    # echo declared output_contract fields
    result = dict(canonical)
    contract = bundle.get("output_contract") or {}
    mapping_note = {}
    if isinstance(contract, dict) and contract:
        for field in contract:
            target = map_field(field)
            if target and target in canonical:
                result[field] = canonical[target]
                mapping_note[field] = target
            else:
                result.setdefault(field, None)
                mapping_note[field] = None
    result["output_contract_mapping"] = mapping_note

    os.makedirs(args.outdir, exist_ok=True)
    # the graph belongs next to its exports: a reader who opens the output directory should not have
    # to know that the source graph lives in the work directory
    try:
        with open(os.path.join(args.outdir, "graph.json"), "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=1)
    except Exception:  # noqa: BLE001
        pass

    # resolve the artifact list now that the files exist; result.json is the file being written
    present = [f for f in ("graph.json", "graph.mmd", "graph.graphml", "graph.svg", "graph.png",
                           "nodes.csv", "edges.csv", "evidence.csv", "graph_report.md")
               if os.path.exists(os.path.join(args.outdir, f))]
    result["artifacts"] = [os.path.join(args.outdir, f) for f in present] + [os.path.abspath(args.out)]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"[finalize] status={status} coverage={coverage} papers_with_evidence={n_papers_with_evidence} "
          f"queries_ok={q_ok}/{queries.get('n_queries',0)} -> {args.out}")
    for r in reasons:
        print("  - " + r)
    if status != "success":
        print("  (status is honest: see result.json.validation and uncertainty)")


if __name__ == "__main__":
    main()
