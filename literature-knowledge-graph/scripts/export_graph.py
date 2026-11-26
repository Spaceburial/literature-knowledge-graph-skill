#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_graph.py — Stage 5: export the graph in reusable, human-inspectable formats.

Writes under --outdir:
  graph.mmd        Mermaid flowchart (opens on GitHub / in editors)
  graph.graphml    GraphML for Gephi / NetworkX / Cytoscape
  nodes.csv        one row per node (+ evidence counts)
  edges.csv        one row per edge (+ condition, evidence count, source ids)
  evidence.csv     one row per (node|edge, source, paragraph, quote, match level)
  graph_report.md  readable summary with merge/conflict/uncertainty sections

All formats are plain text and deterministic, so diffs between runs are meaningful.
"""
import argparse
import csv
import json
import os
import re
import xml.sax.saxutils as su


def esc(s):
    return su.escape(str(s if s is not None else ""))


def mermaid_id(x):
    return re.sub(r"[^A-Za-z0-9_]", "_", x)


def export_mermaid(g, path):
    """Uniform, escape-safe node shape; type is shown in the label to avoid shape syntax risk."""
    def esc_label(t):
        return str(t).replace('"', "'").replace("\n", " ")
    lines = ["flowchart LR"]
    for n in g.get("nodes", []):
        label = esc_label(f"{n['id']}: {n['label']} [{n['type']}]")
        lines.append(f'    {mermaid_id(n["id"])}["{label}"]')
    for e in g.get("edges", []):
        label = e["type"] + (f"<br/>{esc_label(e['condition'])}" if e.get("condition") else "")
        lines.append(f'    {mermaid_id(e["source"])} -->|"{label}"| {mermaid_id(e["target"])}')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def export_graphml(g, path):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
           '<key id="label" for="node" attr.name="label" attr.type="string"/>',
           '<key id="type" for="node" attr.name="type" attr.type="string"/>',
           '<key id="src" for="node" attr.name="source_ids" attr.type="string"/>',
           '<key id="ev" for="edge" attr.name="evidence_status" attr.type="string"/>',
           '<key id="rel" for="edge" attr.name="relation" attr.type="string"/>',
           '<key id="cond" for="edge" attr.name="condition" attr.type="string"/>',
           '<graph id="G" edgedefault="directed">']
    for n in g.get("nodes", []):
        out.append(f'<node id="{esc(n["id"])}">'
                   f'<data key="label">{esc(n["label"])}</data>'
                   f'<data key="type">{esc(n["type"])}</data>'
                   f'<data key="src">{esc(",".join(n.get("source_ids", [])))}</data></node>')
    for e in g.get("edges", []):
        out.append(f'<edge id="{esc(e["id"])}" source="{esc(e["source"])}" target="{esc(e["target"])}">'
                   f'<data key="rel">{esc(e["type"])}</data>'
                   f'<data key="ev">{esc(e.get("evidence_status"))}</data>'
                   f'<data key="cond">{esc(e.get("condition", ""))}</data></edge>')
    out += ["</graph>", "</graphml>"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def export_csv(g, outdir):
    with open(os.path.join(outdir, "nodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "type", "aliases", "source_ids", "evidence_status", "n_evidence"])
        for n in g.get("nodes", []):
            w.writerow([n["id"], n["label"], n["type"], "|".join(n.get("aliases", [])),
                        "|".join(n.get("source_ids", [])), n.get("evidence_status"),
                        len(n.get("mentions", []))])
    with open(os.path.join(outdir, "edges.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "target", "type", "condition", "direction_note",
                    "source_ids", "evidence_status", "n_evidence"])
        for e in g.get("edges", []):
            w.writerow([e["id"], e["source"], e["target"], e["type"], e.get("condition", ""),
                        e.get("direction_note", ""), "|".join(e.get("source_ids", [])),
                        e.get("evidence_status"), len(e.get("evidence", []))])
    with open(os.path.join(outdir, "evidence.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["owner_kind", "owner_id", "source_id", "paragraph_id", "match", "strength",
                    "attribution", "quote", "context"])
        for n in g.get("nodes", []):
            for m in n.get("mentions", []):
                w.writerow(["node", n["id"], m["source_id"], m["paragraph_id"], m["match"],
                            m.get("strength"), m.get("attribution"), m.get("quote"), m.get("context")])
        for e in g.get("edges", []):
            for m in e.get("evidence", []):
                w.writerow(["edge", e["id"], m["source_id"], m["paragraph_id"], m["match"],
                            m.get("strength"), m.get("attribution"), m.get("quote"), m.get("context")])


def export_report(g, queries, path):
    st = g.get("stats", {})
    L = [f"# Knowledge graph report — case `{g.get('case_id')}`", "",
         f"- nodes: **{st.get('n_nodes')}** (verified {st.get('n_nodes_verified')})",
         f"- edges: **{st.get('n_edges')}** (verified {st.get('n_edges_verified')})",
         f"- rejected evidence items: {st.get('n_rejected_evidence')}", "",
         "## Sources", ""]
    for s in g.get("sources", []):
        L.append(f"- `{s['source_id']}` ({s.get('role')}): {s.get('title') or 'title unknown'}"
                 f" — DOI {s.get('doi') or 'n/a'}")
    L += ["", "## Node types", "", "```", json.dumps(st.get("node_types", {})), "```",
          "", "## Edge types", "", "```", json.dumps(st.get("edge_types", {})), "```",
          "", "## Entities", ""]
    L.append("| id | label | type | sources | evidence |")
    L.append("|---|---|---|---|---|")
    for n in g.get("nodes", []):
        L.append(f"| {n['id']} | {n['label']} | {n['type']} | {', '.join(n.get('source_ids', []))} | "
                 f"{len(n.get('mentions', []))} |")
    L += ["", "## Relations", ""]
    L.append("| id | source → target | type | condition | evidence |")
    L.append("|---|---|---|---|---|")
    for e in g.get("edges", []):
        L.append(f"| {e['id']} | {e['source']} → {e['target']} | {e['type']} | "
                 f"{e.get('condition', '')} | {len(e.get('evidence', []))} |")
    L += ["", "## Merge decisions", ""]
    if g.get("merge_log"):
        L.append("| surfaces | decision | basis |")
        L.append("|---|---|---|")
        for m in g["merge_log"]:
            L.append(f"| {' / '.join(m['surfaces'])} | {m['decision']} | {m['basis']} |")
    else:
        L.append("_none_")
    L += ["", "## Conflicts", ""]
    if g.get("conflict_log"):
        for c in g["conflict_log"]:
            L.append(f"- `{c.get('kind')}`: {json.dumps(c, ensure_ascii=False)}")
    else:
        L.append("_none reported_")
    L += ["", "## Uncertainty", ""]
    if g.get("uncertainty"):
        for u in g["uncertainty"][:80]:
            L.append(f"- `{u.get('kind')}` {u.get('label', u.get('item', ''))}: {u.get('detail', '')}")
    else:
        L.append("_none_")
    if queries:
        L += ["", "## Queries", ""]
        for q in queries.get("queries", []):
            L.append(f"### {q['qid']} — {q['query'].get('type')} ({q['status']})")
            L.append(f"```json\n{json.dumps(q['query'], ensure_ascii=False)}\n```")
            L.append(f"nodes: {[n['id'] for n in q['answer']['nodes']]}, "
                     f"edges: {[e['id'] for e in q['answer']['edges']]}, evidence: {q['n_evidence']}")
            for m in q["evidence"][:5]:
                L.append(f"> [{m['source_id']}/{m['paragraph_id']}] {m['quote']}")
            L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="/app/work/graph.json")
    ap.add_argument("--queries", default="/app/work/queries_result.json")
    ap.add_argument("--outdir", default="/app/output")
    args = ap.parse_args()

    with open(args.graph, "r", encoding="utf-8") as f:
        g = json.load(f)
    queries = None
    if args.queries and os.path.exists(args.queries):
        with open(args.queries, "r", encoding="utf-8") as f:
            queries = json.load(f)

    os.makedirs(args.outdir, exist_ok=True)
    export_mermaid(g, os.path.join(args.outdir, "graph.mmd"))
    export_graphml(g, os.path.join(args.outdir, "graph.graphml"))
    export_csv(g, args.outdir)
    export_report(g, queries, os.path.join(args.outdir, "graph_report.md"))
    print(f"[export_graph] wrote graph.mmd, graph.graphml, nodes.csv, edges.csv, evidence.csv, "
          f"graph_report.md -> {args.outdir}")


if __name__ == "__main__":
    main()
