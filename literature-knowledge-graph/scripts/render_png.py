#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_png.py — optional rendered preview of the graph (PNG), so a diagram deliverable can be
inspected without a Mermaid/GraphML viewer.

Uses matplotlib only (no networkx). If matplotlib is unavailable, it prints a warning and
exits 0: the pipeline must not fail because a preview could not be drawn.

Layout: one column per provenance group — primary-only (left), shared (middle), secondary-only
(right) — which makes cross-paper alignment and non-merged samples visible at a glance.
"""
import argparse
import json
import os
import sys

COLORS = {"material": "#4C72B0", "method": "#55A868", "metric": "#C44E52", "task": "#8172B2",
          "conclusion": "#D9A441", "model": "#5FA8C7", "other": "#8C8C8C",
          "researcher": "#DD8452", "dataset": "#937860"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="/app/work/graph.json")
    ap.add_argument("--out", default="/app/output/graph.png")
    args = ap.parse_args()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except Exception as e:  # noqa: BLE001
        print(f"[render_png] matplotlib unavailable ({e}); skipping PNG preview.")
        return 0
    if not os.path.exists(args.graph):
        print(f"[render_png] no graph at {args.graph}; skipping.")
        return 0
    g = json.load(open(args.graph, encoding="utf-8"))
    nodes = g.get("nodes", [])
    if not nodes:
        print("[render_png] empty graph; skipping.")
        return 0
    by_id = {n["id"]: n for n in nodes}
    src_order = [s["source_id"] for s in g.get("sources", [])]
    prim = next((s["source_id"] for s in g.get("sources", []) if s.get("role") == "primary"),
                src_order[0] if src_order else None)
    cols = {"left": [], "mid": [], "right": []}
    for n in nodes:
        ss = set(n.get("source_ids", []))
        if len(ss) > 1:
            cols["mid"].append(n["id"])
        elif prim and prim in ss:
            cols["left"].append(n["id"])
        else:
            cols["right"].append(n["id"])
    pos = {}
    for key, x in (("left", -1.0), ("mid", 0.0), ("right", 1.0)):
        ids = sorted(cols[key], key=lambda i: (by_id[i].get("type", ""), by_id[i]["label"]))
        k = len(ids)
        for j, i in enumerate(ids):
            y = (j - (k - 1) / 2) / max(1, k - 1) * 2.0 if k > 1 else 0.0
            xo = (0.07 if j % 2 else -0.07) if key == "mid" else 0.0
            pos[i] = (x + xo, y)
    if not pos:
        return 0
    ys = [p[1] for p in pos.values()]
    y0, y1 = min(ys) - 0.6, max(ys) + 0.7
    fig, ax = plt.subplots(figsize=(13, max(6, min(16, (y1 - y0) * 1.6))))
    for e in g.get("edges", []):
        if e["source"] not in pos or e["target"] not in pos:
            continue
        (x1, y1_), (x2, y2_) = pos[e["source"]], pos[e["target"]]
        ax.annotate("", xy=(x2, y2_), xytext=(x1, y1_),
                    arrowprops=dict(arrowstyle="-|>", color="#8f8f8f", lw=1.0, alpha=0.8,
                                    connectionstyle="arc3,rad=0.08", shrinkA=10, shrinkB=10))
    for n in nodes:
        if n["id"] not in pos:
            continue
        x, y = pos[n["id"]]
        ax.scatter(x, y, s=420, c=COLORS.get(n.get("type"), "#999"),
                   edgecolors="white", linewidths=1.3, zorder=3)
        ha = "right" if x < 0 else ("left" if x > 0 else "center")
        ax.text(x + (0.03 if x > 0 else -0.03 if x < 0 else 0), y + (0.04 if x == 0 else 0),
                n["label"], fontsize=7, ha=ha, va="bottom" if x == 0 else "center", zorder=4)
    for x, t in ((-1.0, "primary only"), (0.0, "shared concepts"), (1.0, "secondary only")):
        ax.text(x, y1 - 0.15, t, ha="center", fontsize=9, fontweight="bold", color="#333")
    present = {n.get("type") for n in nodes}
    handles = [mpatches.Patch(color=c, label=t) for t, c in COLORS.items() if t in present]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=7,
              fontsize=7, frameon=False)
    ax.set_title(f"Knowledge graph — {len(nodes)} nodes / {len(g.get('edges', []))} edges "
                 f"({len(g.get('sources', []))} sources)", fontsize=11, pad=22)
    ax.set_xlim(-1.5, 1.8)
    ax.set_ylim(y0, y1 + 0.2)
    ax.axis("off")
    plt.tight_layout()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    plt.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"[render_png] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
