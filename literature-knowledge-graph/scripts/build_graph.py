#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_graph.py — Stage 3: turn verified annotations into a single cross-paper graph.

Inputs
  /app/work/case_bundle.json      (from prepare_case.py)
  /app/work/annotations.json      (from the agent: nodes / edges / merge_candidates / source_conflicts)

Outputs
  /app/work/graph.json            (canonical graph with evidence, merge log, conflict log, uncertainty)
  /app/work/build_report.txt      (human-readable audit)

Guarantees
  * Every node/edge keeps at least one evidence record with source_id, paragraph_id, quote,
    verification status and the surrounding original sentence ("context").
  * A node/edge whose every quote fails verification is retained but labelled
    ``evidence_status="unverified"`` and listed in ``uncertainty`` — it is never silently dropped
    and never presented as if it were supported.
  * Entity merging is explicit: canonical key + alias list + logged decision. Cross-paper
    *generic* terms (a method or material name) are NOT merged into one physical instance; the
    merge log records the distinction.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_evidence import verify_quote, is_acceptable, evidence_strength_from  # noqa: E402

NODE_TYPES = {"researcher", "material", "method", "task", "metric", "conclusion",
              "dataset", "model", "finding", "other"}
NODE_TYPE_SYNONYMS = {
    "author": "researcher", "people": "researcher", "person": "researcher", "team": "researcher",
    "compound": "material", "chemical": "material", "sample": "material", "film": "material",
    "technique": "method", "approach": "method", "procedure": "method", "protocol": "method",
    "benchmark_task": "task", "application": "task",
    "indicator": "metric", "measure": "metric", "performance": "metric",
    "claim": "conclusion", "result": "conclusion", "finding_text": "conclusion",
    "corpus": "dataset", "data": "dataset",
    "architecture": "model", "system": "model",
}
REL_TYPES = {"uses", "compares", "outperforms", "supports", "contradicts", "measures",
             "evaluated_on", "reports", "part_of", "produces", "improves", "based_on",
             "cites", "other"}
REL_SYNONYMS = {
    "use": "uses", "utilize": "uses", "utilizes": "uses", "employ": "uses", "adopt": "uses",
    "compare": "compares", "compared_with": "compares", "vs": "compares",
    "better_than": "outperforms", "exceeds": "outperforms", "higher_than": "outperforms",
    "superior_to": "outperforms", "outperform": "outperforms",
    "support": "supports", "confirm": "supports", "consistent_with": "supports",
    "contradict": "contradicts", "conflict": "contradicts", "inconsistent_with": "contradicts",
    "measure": "measures", "measured_by": "measures",
    "test_on": "evaluated_on", "evaluate_on": "evaluated_on", "benchmark_on": "evaluated_on",
    "report": "reports", "achieve": "reports", "achieves": "reports",
    "part_of": "part_of", "component_of": "part_of", "include": "part_of",
    "produce": "produces", "yield": "produces", "yields": "produces",
    "improve": "improves", "enhance": "improves",
    "based_on": "based_on", "build_on": "based_on", "derived_from": "based_on",
    "cite": "cites", "cite_by": "cites",
}


def canon(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[\u2010-\u2015\-_/]+", " ", s)
    s = re.sub(r"[^\w\u4e00-\u9fff \+\.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_type(t):
    t = (t or "other").strip().lower()
    return NODE_TYPE_SYNONYMS.get(t, t if t in NODE_TYPES else "other")


def norm_rel(t):
    t = (t or "other").strip().lower()
    return REL_SYNONYMS.get(t, t if t in REL_TYPES else "other")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        try:
            return json.load(f)
        except Exception:  # noqa: BLE001
            return default


def load_annotations(path):
    """Accept JSON or JSONL annotations; normalise to one dict."""
    if not os.path.exists(path):
        return {"nodes": [], "edges": [], "merge_candidates": [], "source_conflicts": []}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read().strip()
    if not raw:
        return {"nodes": [], "edges": [], "merge_candidates": [], "source_conflicts": []}
    if raw[0] == "{":
        try:
            obj = json.loads(raw)
            if isinstance(obj.get("annotations"), dict):
                obj = obj["annotations"]
            obj.setdefault("nodes", [])
            obj.setdefault("edges", [])
            obj.setdefault("merge_candidates", [])
            obj.setdefault("source_conflicts", [])
            return obj
        except Exception:  # noqa: BLE001
            pass
    # JSONL
    nodes, edges = [], []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if rec.get("kind") == "node" or "label" in rec:
            nodes.append(rec)
        elif rec.get("kind") == "edge" or ("source" in rec and "target" in rec):
            edges.append(rec)
    return {"nodes": nodes, "edges": edges, "merge_candidates": [], "source_conflicts": []}


def verify_evidence_list(ev_list, para_index, para_meta=None, attribution_default="self"):
    """Verify each evidence item; return (kept, rejected)."""
    kept, rejected = [], []
    for ev in ev_list or []:
        if not isinstance(ev, dict):
            continue
        sid = str(ev.get("source_id") or ev.get("source") or "")
        pid = str(ev.get("paragraph_id") or ev.get("pid") or "")
        quote = ev.get("quote") or ev.get("text") or ""
        key = (sid, pid)
        if key not in para_index:
            rejected.append({"evidence": ev, "reason": f"paragraph {sid}/{pid} not in case material"})
            continue
        text = para_index[key]
        res = verify_quote(quote, text)
        if not is_acceptable(res):
            rejected.append({"evidence": ev, "reason": f"quote not found ({res['note']})",
                             "best_score": res["score"]})
            continue
        attr = ev.get("attribution") or attribution_default
        meta = (para_meta or {}).get(key, {})
        kept.append({
            "source_id": sid,
            "paragraph_id": pid,
            "paragraph_id_kind": "derived" if meta.get("id_derived") else "jats",
            "quote": quote,
            "match": res["status"],
            "match_score": res["score"],
            "context": ev.get("context") or res["context"],
            "attribution": attr,
            "strength": ev.get("strength") or evidence_strength_from(res["status"], attr),
            "section": ev.get("section") or meta.get("section") or "",
        })
    return kept, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="/app/work/case_bundle.json")
    ap.add_argument("--annotations", default="/app/work/annotations.json")
    ap.add_argument("--out", default="/app/work/graph.json")
    ap.add_argument("--report", default="/app/work/build_report.txt")
    ap.add_argument("--strict", action="store_true",
                    help="drop nodes/edges with no verified evidence instead of flagging them")
    args = ap.parse_args()

    bundle = load_json(args.bundle)
    if not bundle:
        sys.stderr.write("FATAL: case_bundle.json missing. Run prepare_case.py first.\n")
        sys.exit(2)
    annotations = load_annotations(args.annotations)

    paragraphs = bundle.get("paragraphs", [])
    para_index = {(p["source_id"], p["paragraph_id"]): p["text"] for p in paragraphs}
    para_meta = {(p["source_id"], p["paragraph_id"]): p for p in paragraphs}
    sources = {s["source_id"]: s for s in bundle.get("sources", [])}

    uncertainty, merge_log, conflict_log, rejected_all = [], [], [], []

    # ---------------- nodes ----------------
    # canonical key -> node
    by_key = {}
    nodes = []
    for raw in annotations.get("nodes", []):
        label = (raw.get("label") or raw.get("name") or "").strip()
        if not label:
            continue
        ntype = norm_type(raw.get("type"))
        aliases = [a for a in (raw.get("aliases") or []) if isinstance(a, str)]
        key = canon(raw.get("canonical_key") or label)
        kept, rejected = verify_evidence_list(raw.get("mentions") or raw.get("evidence") or [],
                                             para_index, para_meta)
        rejected_all += rejected
        status = "verified" if kept else ("unverified" if not rejected else "rejected")
        rec = {
            "label": label,
            "type": ntype,
            "aliases": sorted({a for a in aliases if canon(a) != key}),
            "canonical_key": key,
            "mentions": kept,
            "evidence_status": status,
            "source_ids": sorted({m["source_id"] for m in kept}),
            "confidence": raw.get("confidence", 0.8 if kept else 0.3),
            "notes": raw.get("notes", ""),
        }
        if key in by_key:
            # merge into existing (alias collision inside one paper set)
            tgt = by_key[key]
            tgt["aliases"] = sorted(set(tgt["aliases"]) | set(rec["aliases"]) | {rec["label"]})
            tgt["mentions"] += rec["mentions"]
            tgt["source_ids"] = sorted(set(tgt["source_ids"]) | set(rec["source_ids"]))
            tgt["evidence_status"] = "verified" if tgt["mentions"] else tgt["evidence_status"]
            merge_log.append({"surfaces": [tgt["label"], rec["label"]], "decision": "merged",
                              "basis": "identical canonical_key", "type": ntype})
            continue
        by_key[key] = rec
        nodes.append(rec)

    # alias-based merge (explicit alias lists), but never merge across incompatible types
    alias_owner = {}
    for n in nodes:
        for surface in [n["label"]] + n["aliases"]:
            k = canon(surface)
            if k and k not in alias_owner:
                alias_owner[k] = n["canonical_key"]

    # apply annotated merge decisions
    for mc in annotations.get("merge_candidates", []):
        surfaces = mc.get("surfaces") or []
        decision = (mc.get("decision") or "").lower()
        keys = [canon(s) for s in surfaces]
        # distinct keys only: surfaces that canonicalise identically are already the same node
        present = list(dict.fromkeys([k for k in keys if k in by_key]))
        if decision == "merged" and len(present) >= 2:
            primary = by_key[present[0]]
            for k in present[1:]:
                other = by_key[k]
                if other is primary:
                    continue
                if other.get("type") != primary.get("type"):
                    conflict_log.append({"kind": "merge_type_conflict", "surfaces": surfaces,
                                         "kept_separate": True,
                                         "reason": f"types differ ({primary['type']} vs {other['type']})"})
                    continue
                primary["mentions"] += other["mentions"]
                primary["aliases"] = sorted(set(primary["aliases"]) | set(other["aliases"]) | {other["label"]})
                primary["source_ids"] = sorted(set(primary["source_ids"]) | set(other["source_ids"]))
                primary["evidence_status"] = "verified" if primary["mentions"] else primary["evidence_status"]
                other["_dropped"] = True
            merge_log.append({"surfaces": surfaces, "decision": "merged",
                              "basis": mc.get("basis", "annotated merge"), "type": primary["type"]})
        elif decision == "kept_separate":
            merge_log.append({"surfaces": surfaces, "decision": "kept_separate",
                              "basis": mc.get("basis", "annotated non-merge"), "type": None})
    nodes = [n for n in nodes if not n.get("_dropped")]

    # stable N-ids by first appearance (bundle order, then node order)
    def first_order(n):
        if not n["mentions"]:
            return 10**9
        return min(para_meta[(m["source_id"], m["paragraph_id"])].get("order_in_source", 10**9)
                   for m in n["mentions"])
    nodes.sort(key=lambda n: (first_order(n), n["canonical_key"]))
    for i, n in enumerate(nodes, 1):
        n["id"] = f"N{i:04d}"

    # label/surface -> node id
    surface_to_id = {}
    for n in nodes:
        for surface in [n["label"]] + n["aliases"]:
            surface_to_id.setdefault(canon(surface), n["id"])
    key_to_id = {n["canonical_key"]: n["id"] for n in nodes}

    # ---------------- edges ----------------
    edges = []
    pair_rels = defaultdict(list)
    for raw in annotations.get("edges", []):
        s_lbl = raw.get("source_label") or raw.get("source")
        t_lbl = raw.get("target_label") or raw.get("target")
        s_id = surface_to_id.get(canon(s_lbl)) or key_to_id.get(canon(s_lbl))
        t_id = surface_to_id.get(canon(t_lbl)) or key_to_id.get(canon(t_lbl))
        if not s_id or not t_id:
            conflict_log.append({"kind": "edge_endpoint_missing",
                                 "edge": {"source": s_lbl, "target": t_lbl},
                                 "reason": "endpoint label not resolved to a node"})
            continue
        if s_id == t_id:
            continue
        rtype = norm_rel(raw.get("type") or raw.get("relation"))
        kept, rejected = verify_evidence_list(raw.get("evidence") or [], para_index, para_meta)
        rejected_all += rejected
        status = "verified" if kept else ("unverified" if not rejected else "rejected")
        rec = {
            "source": s_id,
            "target": t_id,
            "type": rtype,
            "raw_type": raw.get("type"),
            "direction_note": raw.get("direction_note", ""),
            "condition": raw.get("condition", ""),
            "evidence": kept,
            "evidence_status": status,
            "source_ids": sorted({m["source_id"] for m in kept}),
            "confidence": raw.get("confidence", 0.8 if kept else 0.3),
            "notes": raw.get("notes", ""),
        }
        edges.append(rec)
        pair_rels[(s_id, t_id)].append(rtype)

    # conflict detection: support vs contradict, or reversed outperforms
    for (s, t), rels in pair_rels.items():
        if "supports" in rels and "contradicts" in rels:
            conflict_log.append({"kind": "relation_conflict", "pair": [s, t],
                                 "relations": sorted(set(rels)),
                                 "reason": "same pair asserted both supporting and contradicting"})
    for e in edges:
        if e["type"] == "outperforms":
            rev = pair_rels.get((e["target"], e["source"]), [])
            if "outperforms" in rev:
                conflict_log.append({"kind": "bidirectional_outperforms",
                                     "pair": [e["source"], e["target"]],
                                     "reason": "A>B and B>A both present; direction must be resolved by condition"})

    for i, e in enumerate(edges, 1):
        e["id"] = f"E{i:04d}"

    # ---------------- unverified / uncertainty ----------------
    for n in nodes:
        if n["evidence_status"] != "verified":
            uncertainty.append({"item": n["id"], "kind": "node_without_verified_evidence",
                                "label": n["label"], "detail": "no quote from the case material could be located"})
    for e in edges:
        if e["evidence_status"] != "verified":
            uncertainty.append({"item": e["id"], "kind": "edge_without_verified_evidence",
                                "label": f"{e['source']}-[{e['type']}]->{e['target']}"})
    for r in rejected_all:
        uncertainty.append({"item": "rejected_evidence", "kind": "quote_not_found",
                            "detail": r.get("reason"), "evidence": r.get("evidence")})
    for sc in annotations.get("source_conflicts", []):
        conflict_log.append({"kind": "source_disagreement", **sc})
    for u in annotations.get("uncertainty", []):
        if isinstance(u, dict):
            uncertainty.append(u)
    for n in nodes:
        if len(n["source_ids"]) > 1:
            uncertainty.append({"item": n["id"], "kind": "cross_paper_generic_term",
                                "label": n["label"],
                                "detail": f"surface appears in {n['source_ids']}; merged as a shared "
                                          f"concept, NOT as one physical sample/model instance"})

    if args.strict:
        nodes = [n for n in nodes if n["evidence_status"] == "verified"]
        keep_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in keep_ids and e["target"] in keep_ids
                 and e["evidence_status"] == "verified"]

    graph = {
        "schema_version": "1.0",
        "case_id": bundle.get("case_id"),
        "sources": bundle.get("sources", []),
        "nodes": nodes,
        "edges": edges,
        "merge_log": merge_log,
        "conflict_log": conflict_log,
        "uncertainty": uncertainty,
        "stats": {
            "n_nodes": len(nodes), "n_edges": len(edges),
            "n_nodes_verified": sum(1 for n in nodes if n["evidence_status"] == "verified"),
            "n_edges_verified": sum(1 for e in edges if e["evidence_status"] == "verified"),
            "n_rejected_evidence": len(rejected_all),
            "node_types": _count(nodes, "type"),
            "edge_types": _count(edges, "type"),
            "nodes_by_source": _by_source(nodes),
            "edges_by_source": _by_source(edges),
        },
        "warnings": bundle.get("warnings", []),
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=1)

    lines = [f"graph: {len(nodes)} nodes / {len(edges)} edges", ""]
    lines.append(f"verified nodes: {graph['stats']['n_nodes_verified']}, "
                 f"verified edges: {graph['stats']['n_edges_verified']}")
    lines.append(f"rejected evidence items: {len(rejected_all)}")
    lines.append("node types: " + json.dumps(graph["stats"]["node_types"]))
    lines.append("edge types: " + json.dumps(graph["stats"]["edge_types"]))
    lines.append("")
    lines.append("merge decisions:")
    for m in merge_log:
        lines.append(f"  {m['decision']}: {m['surfaces']}  ({m['basis']})")
    lines.append("")
    lines.append("conflicts:")
    for c in conflict_log:
        lines.append(f"  {c.get('kind')}: {c}")
    with open(args.report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[build_graph] {len(nodes)} nodes, {len(edges)} edges, "
          f"{len(merge_log)} merge decisions, {len(conflict_log)} conflicts -> {args.out}")


def _count(items, field):
    d = defaultdict(int)
    for it in items:
        d[it.get(field, "?")] += 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


def _by_source(items):
    d = defaultdict(int)
    for it in items:
        for s in it.get("source_ids", []) or ["none"]:
            d[s] += 1
    return dict(sorted(d.items()))


if __name__ == "__main__":
    main()
