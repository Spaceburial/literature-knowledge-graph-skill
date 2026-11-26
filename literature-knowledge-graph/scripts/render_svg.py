#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_svg.py — draw a preview of the graph with no third-party import.

Why: the deliverable asks for a rendered preview of the diagram next to the data files, and
matplotlib is not guaranteed to be installed in the evaluation image. An SVG needs nothing but the
standard library, is text (so it survives the text-only packaging rule), and stays deterministic:
the same graph.json produces the same bytes, which is what makes it diffable.

The layout is schematic, not a claim about the science: nodes are parked on a grid by type in id
order, and the drawing is meant for a human scanning for shape and density. Every id, label and
quote lives in graph.json, which remains the source of truth.

Usage
  python3 render_svg.py --graph /app/work/graph.json --out /app/output/graph.svg
  python3 render_svg.py --graph graph.json --out g.svg --max-nodes 200
"""
import argparse
import json
import os
import sys
from collections import defaultdict

TYPE_ORDER = ["material", "method", "task", "metric", "conclusion", "researcher",
              "dataset", "model", "other"]
TYPE_FILL = {
    "material": "#e8f1fb", "method": "#eaf6ea", "task": "#fdf3e3", "metric": "#f6e9f7",
    "conclusion": "#f2f2f2", "researcher": "#e6f7f5", "dataset": "#f7f0e6", "model": "#eef0fb",
    "other": "#f4f4f4",
}
BOX_W, BOX_H, GAP_X, GAP_Y = 196, 40, 64, 26
COLS = 4
MARGIN = 32


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def clip(s, n=26):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def layout(nodes):
    by_type = defaultdict(list)
    for n in sorted(nodes, key=lambda x: str(x.get("id", ""))):
        by_type[n.get("type") or "other"].append(n)
    ordered = []
    for t in TYPE_ORDER:
        ordered += by_type.get(t, [])
    for t in sorted(by_type):
        if t not in TYPE_ORDER:
            ordered += by_type[t]
    pos = {}
    for i, n in enumerate(ordered):
        col, row = i % COLS, i // COLS
        pos[n["id"]] = (MARGIN + col * (BOX_W + GAP_X), MARGIN + 56 + row * (BOX_H + GAP_Y))
    return pos, ordered


def render(graph, max_nodes=200):
    nodes = [n for n in graph.get("nodes", []) if n.get("id")]
    dropped = max(0, len(nodes) - max_nodes)
    nodes = nodes[:max_nodes]
    keep = {n["id"] for n in nodes}
    edges = [e for e in graph.get("edges", []) if e.get("source") in keep and e.get("target") in keep]
    pos, ordered = layout(nodes)

    height = max([y for _, y in pos.values()] or [0]) + BOX_H + 96
    width = MARGIN * 2 + COLS * BOX_W + (COLS - 1) * GAP_X
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica,Arial,sans-serif">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" '
        'fill="#6b7280"/></marker></defs>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]
    case_id = graph.get("case_id") or "(no case_id)"
    out.append(f'<text x="{MARGIN}" y="30" font-size="16" fill="#111827">'
               f'{esc(clip(case_id, 70))}</text>')
    out.append(f'<text x="{MARGIN}" y="48" font-size="11" fill="#6b7280">'
               f'{len(nodes)} nodes, {len(edges)} edges shown; extraction='
               f'{esc(graph.get("extraction_mode", "unknown"))}; layout is schematic, '
               f'graph.json is the source of truth</text>')

    for e in edges:
        x1, y1 = pos[e["source"]]
        x2, y2 = pos[e["target"]]
        sx, sy = x1 + BOX_W, y1 + BOX_H // 2
        tx, ty = x2, y2 + BOX_H // 2
        if abs(y2 - y1) < 1:
            sx, tx = x1 + BOX_W // 2, x2 + BOX_W // 2
        mx = (sx + tx) / 2
        dash = "" if e.get("evidence_status") == "verified" else ' stroke-dasharray="4 3"'
        colour = "#9ca3af" if e.get("evidence_status") == "verified" else "#d1a3a3"
        out.append(f'<path d="M {sx:.0f} {sy:.0f} C {mx:.0f} {sy:.0f}, {mx:.0f} {ty:.0f}, '
                   f'{tx:.0f} {ty:.0f}" fill="none" stroke="{colour}" stroke-width="1.2"'
                   f'{dash} marker-end="url(#arrow)"><title>{esc(e.get("id", ""))} '
                   f'{esc(e.get("type", ""))}</title></path>')

    for n in ordered:
        x, y = pos[n["id"]]
        fill = TYPE_FILL.get(n.get("type") or "other", "#f4f4f4")
        stroke = "#9ca3af" if n.get("evidence_status", "verified") == "verified" else "#c98b8b"
        out.append(f'<g><title>{esc(n.get("id", ""))} {esc(n.get("label", ""))} '
                   f'({esc(n.get("type", ""))})</title>'
                   f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="6" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
                   f'<text x="{x + 8}" y="{y + 16}" font-size="10" fill="#6b7280">'
                   f'{esc(n.get("id", ""))} \u00b7 {esc(n.get("type", ""))}</text>'
                   f'<text x="{x + 8}" y="{y + 31}" font-size="12" fill="#111827">'
                   f'{esc(clip(n.get("label", "")))}</text></g>')

    legend = (f'types: ' + ", ".join(f'{t} ({sum(1 for n in nodes if (n.get("type") or "other") == t)})'
                                    for t in TYPE_ORDER
                                    if any((n.get("type") or "other") == t for n in nodes)))
    out.append(f'<text x="{MARGIN}" y="{height - 28}" font-size="10" fill="#6b7280">'
               f'{esc(legend)}</text>')
    note = "solid edge = verified evidence, dashed = unverified/rejected"
    if dropped:
        note += f"; {dropped} further node(s) not drawn (--max-nodes {max_nodes})"
    out.append(f'<text x="{MARGIN}" y="{height - 12}" font-size="10" fill="#6b7280">'
               f'{esc(note)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="/app/work/graph.json")
    ap.add_argument("--out", default="/app/output/graph.svg")
    ap.add_argument("--max-nodes", type=int, default=200)
    args = ap.parse_args()

    if not os.path.exists(args.graph):
        sys.stderr.write(f"FATAL: graph not found: {args.graph}\n")
        sys.exit(2)
    with open(args.graph, "r", encoding="utf-8") as f:
        graph = json.load(f)
    svg = render(graph, args.max_nodes)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    n = graph.get("nodes") or []
    print(f"[render_svg] {len(n)} nodes -> {args.out} ({len(svg)} bytes, no third-party import)")


if __name__ == "__main__":
    main()
