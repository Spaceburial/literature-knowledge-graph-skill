#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_paper.py — incremental update: merge one new paper into an existing graph.

Why: re-running build_graph.py on the whole corpus renumbers everything and loses any manual
review. The rubric asks that adding a paper preserve existing nodes and ids, and record what
was added, merged and found in conflict.

Behaviour
  * existing node ids (N####) are never renumbered;
  * a new node whose canonical key (or alias) matches an existing node of the SAME type is
    merged into it: mentions/aliases/source_ids are unioned, id preserved, merge logged;
  * a type mismatch is NOT merged: a new node is created and the collision logged;
  * a new edge identical in (source, target, type) to an existing edge has its evidence merged
    instead of being duplicated;
  * new support/contradict pairs and reversed `outperforms` are appended to the conflict log;
  * a change record (added / merged / skipped-rejected) is written next to the graph.

Usage
  python add_paper.py --graph graph.json --bundle bundle_with_new_paper.json \
         --annotations new_paper_annotations.json --out graph_updated.json \
         --change-log change_log.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_evidence import verify_quote, is_acceptable, evidence_strength_from  # noqa: E402

NODE_TYPES = {"researcher", "material", "method", "task", "metric", "conclusion",
              "dataset", "model", "finding", "other"}
REL_TYPES = {"uses", "compares", "outperforms", "supports", "contradicts", "measures",
             "evaluated_on", "reports", "part_of", "produces", "improves", "based_on",
             "cites", "other"}


def canon(s):
    import re
    s = (s or "").strip().lower()
    s = re.sub(r"[\u2010-\u2015\-_/]+", " ", s)
    s = re.sub(r"[^\w\u4e00-\u9fff \+\.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def next_id(items, prefix):
    n = 0
    for it in items:
        i = str(it.get("id", ""))
        if i.startswith(prefix) and i[len(prefix):].isdigit():
            n = max(n, int(i[len(prefix):]))
    return n + 1


def verify_list(evs, para_index, para_meta):
    kept, rejected = [], []
    for ev in evs or []:
        sid = str(ev.get("source_id") or "")
        pid = str(ev.get("paragraph_id") or "")
        text = para_index.get((sid, pid))
        if text is None:
            rejected.append({"evidence": ev, "reason": f"paragraph {sid}/{pid} not in bundle"})
            continue
        res = verify_quote(ev.get("quote") or "", text)
        if not is_acceptable(res):
            rejected.append({"evidence": ev, "reason": res["note"], "best_score": res["score"]})
            continue
        attr = ev.get("attribution") or "self"
        meta = para_meta.get((sid, pid), {})
        kept.append({"source_id": sid, "paragraph_id": pid,
                     "paragraph_id_kind": "derived" if meta.get("id_derived") else "jats",
                     "quote": ev.get("quote"), "match": res["status"], "match_score": res["score"],
                     "context": res["context"], "attribution": attr,
                     "strength": evidence_strength_from(res["status"], attr),
                     "section": meta.get("section", "")})
    return kept, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    ap.add_argument("--bundle", required=True, help="prepare_case output that contains the new paragraphs")
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--change-log", default=None)
    args = ap.parse_args()

    g = json.load(open(args.graph, encoding="utf-8"))
    b = json.load(open(args.bundle, encoding="utf-8"))
    ann = json.load(open(args.annotations, encoding="utf-8"))
    if isinstance(ann.get("annotations"), dict):
        ann = ann["annotations"]

    para_index = {(p["source_id"], p["paragraph_id"]): p["text"] for p in b.get("paragraphs", [])}
    para_meta = {(p["source_id"], p["paragraph_id"]): p for p in b.get("paragraphs", [])}

    nodes = g.setdefault("nodes", [])
    edges = g.setdefault("edges", [])
    merge_log = g.setdefault("merge_log", [])
    conflict_log = g.setdefault("conflict_log", [])
    uncertainty = g.setdefault("uncertainty", [])

    by_key = {n.get("canonical_key") or canon(n["label"]): n for n in nodes}
    surface = {}
    for n in nodes:
        for s in [n["label"]] + n.get("aliases", []):
            surface.setdefault(canon(s), n)
    nid = next_id(nodes, "N")
    eid = next_id(edges, "E")

    change = {"added_nodes": [], "merged_nodes": [], "added_edges": [],
              "merged_edges": [], "conflicts_added": [], "rejected_evidence": [],
              "sources_added": []}

    # ---- sources ----
    known_src = {s["source_id"] for s in g.get("sources", [])}
    for s in b.get("sources", []):
        if s["source_id"] not in known_src:
            g.setdefault("sources", []).append(s)
            change["sources_added"].append(s["source_id"])

    # ---- nodes ----
    for raw in ann.get("nodes", []):
        label = (raw.get("label") or "").strip()
        if not label:
            continue
        ntype = (raw.get("type") or "other").lower()
        ntype = ntype if ntype in NODE_TYPES else "other"
        key = canon(raw.get("canonical_key") or label)
        kept, rejected = verify_list(raw.get("mentions") or raw.get("evidence") or [],
                                     para_index, para_meta)
        change["rejected_evidence"] += rejected
        hit = by_key.get(key) or surface.get(key)
        if hit is not None and hit.get("type") == ntype:
            before = len(hit.get("mentions", []))
            hit["mentions"] = hit.get("mentions", []) + kept
            hit["aliases"] = sorted(set(hit.get("aliases", [])) | set(raw.get("aliases") or [])
                                    | ({label} if canon(label) != canon(hit["label"]) else set()))
            hit["source_ids"] = sorted(set(hit.get("source_ids", [])) | {m["source_id"] for m in kept})
            hit["evidence_status"] = "verified" if hit["mentions"] else hit.get("evidence_status")
            for s in [hit["label"]] + hit.get("aliases", []):
                surface.setdefault(canon(s), hit)
            merge_log.append({"surfaces": [hit["label"], label], "decision": "merged",
                              "basis": "incremental: matched existing canonical key/alias",
                              "type": ntype})
            change["merged_nodes"].append({"id": hit["id"], "label": hit["label"],
                                           "new_mentions": len(hit["mentions"]) - before,
                                           "source_ids": hit["source_ids"]})
            continue
        if hit is not None and hit.get("type") != ntype:
            conflict_log.append({"kind": "merge_type_conflict", "surfaces": [hit["label"], label],
                                 "kept_separate": True,
                                 "reason": f"existing type {hit['type']} vs new type {ntype}"})
        rec = {"id": f"N{nid:04d}", "label": label, "type": ntype,
               "aliases": sorted({a for a in (raw.get("aliases") or []) if canon(a) != key}),
               "canonical_key": key, "mentions": kept,
               "evidence_status": "verified" if kept else "unverified",
               "source_ids": sorted({m["source_id"] for m in kept}),
               "confidence": raw.get("confidence", 0.8 if kept else 0.3),
               "notes": raw.get("notes", "")}
        nodes.append(rec)
        by_key[key] = rec
        for s in [label] + rec["aliases"]:
            surface.setdefault(canon(s), rec)
        nid += 1
        change["added_nodes"].append({"id": rec["id"], "label": label, "type": ntype})
        if not kept:
            uncertainty.append({"item": rec["id"], "kind": "node_without_verified_evidence",
                                "label": label})

    # ---- edges ----
    id_by_key = {n["id"]: n for n in nodes}
    existing = {}
    pair_rels = {}
    for e in edges:
        existing[(e["source"], e["target"], e["type"])] = e
        pair_rels.setdefault((e["source"], e["target"]), set()).add(e["type"])

    for raw in ann.get("edges", []):
        s_node = surface.get(canon(raw.get("source_label") or raw.get("source")))
        t_node = surface.get(canon(raw.get("target_label") or raw.get("target")))
        if not s_node or not t_node or s_node["id"] == t_node["id"]:
            conflict_log.append({"kind": "edge_endpoint_missing",
                                 "edge": {"source": raw.get("source_label"),
                                          "target": raw.get("target_label")},
                                 "reason": "endpoint not resolved in updated graph"})
            continue
        rtype = (raw.get("type") or "other").lower()
        rtype = rtype if rtype in REL_TYPES else "other"
        kept, rejected = verify_list(raw.get("evidence") or [], para_index, para_meta)
        change["rejected_evidence"] += rejected
        key = (s_node["id"], t_node["id"], rtype)
        if key in existing:
            existing[key]["evidence"] = existing[key].get("evidence", []) + kept
            existing[key]["source_ids"] = sorted(set(existing[key].get("source_ids", []))
                                                 | {m["source_id"] for m in kept})
            existing[key]["evidence_status"] = "verified" if existing[key]["evidence"] else "unverified"
            change["merged_edges"].append({"id": existing[key]["id"], "type": rtype})
            continue
        rec = {"id": f"E{eid:04d}", "source": s_node["id"], "target": t_node["id"], "type": rtype,
               "raw_type": raw.get("type"), "direction_note": raw.get("direction_note", ""),
               "condition": raw.get("condition", ""), "evidence": kept,
               "evidence_status": "verified" if kept else "unverified",
               "source_ids": sorted({m["source_id"] for m in kept}),
               "confidence": raw.get("confidence", 0.8 if kept else 0.3),
               "notes": raw.get("notes", "")}
        edges.append(rec)
        existing[key] = rec
        pair_rels.setdefault((rec["source"], rec["target"]), set()).add(rtype)
        eid += 1
        change["added_edges"].append({"id": rec["id"], "type": rtype,
                                      "from": s_node["label"], "to": t_node["label"]})
        if "outperforms" in pair_rels.get((rec["target"], rec["source"]), set()) and rtype == "outperforms":
            conflict_log.append({"kind": "bidirectional_outperforms",
                                 "pair": [rec["source"], rec["target"]],
                                 "reason": "incremental update created A>B and B>A"})
            change["conflicts_added"].append("bidirectional_outperforms")

    for (s, t), rels in pair_rels.items():
        if "supports" in rels and "contradicts" in rels:
            c = {"kind": "relation_conflict", "pair": [s, t], "relations": sorted(rels),
                 "reason": "same pair asserted both supporting and contradicting"}
            if c not in conflict_log:
                conflict_log.append(c)
                change["conflicts_added"].append("relation_conflict")

    for sc in ann.get("source_conflicts", []):
        conflict_log.append({"kind": "source_disagreement", **sc})
        change["conflicts_added"].append(sc.get("kind", "source_disagreement"))

    # ---- stats refresh ----
    def count(items, f):
        d = {}
        for it in items:
            d[it.get(f, "?")] = d.get(it.get(f, "?"), 0) + 1
        return dict(sorted(d.items(), key=lambda kv: -kv[1]))

    g["stats"] = {
        "n_nodes": len(nodes), "n_edges": len(edges),
        "n_nodes_verified": sum(1 for n in nodes if n.get("evidence_status") == "verified"),
        "n_edges_verified": sum(1 for e in edges if e.get("evidence_status") == "verified"),
        "n_rejected_evidence": len(change["rejected_evidence"]),
        "node_types": count(nodes, "type"), "edge_types": count(edges, "type"),
    }
    change["summary"] = (f"+{len(change['added_nodes'])} nodes, {len(change['merged_nodes'])} merged, "
                         f"+{len(change['added_edges'])} edges, {len(change['merged_edges'])} edges merged, "
                         f"{len(change['conflicts_added'])} conflicts added")

    out = args.out or args.graph.replace(".json", "_updated.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False, indent=1)
    clog = args.change_log or os.path.join(os.path.dirname(out), "change_log.json")
    with open(clog, "w", encoding="utf-8") as f:
        json.dump(change, f, ensure_ascii=False, indent=1)
    print(f"[add_paper] {change['summary']} -> {out}")
    for r in change["rejected_evidence"]:
        print("  ! rejected: " + str(r.get("reason")))


if __name__ == "__main__":
    main()
