#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
query_graph.py — Stage 4: run real queries against the built graph.

Supported query types
  entity            name=...                         -> node + incident edges + evidence
  neighbors         name=..., relation=..., direction=in|out|both
  path              from=..., to=..., max_hops=3     -> evidence-bearing paths
  relation_search   relation=..., keyword=...
  cross_paper       (no params)                      -> shared vs source-exclusive entities,
                                                        and cross-source conflicts
  evidence_trace    id=N0001|E0001                   -> original paragraph + quote + context
  metric_compare    name=<metric or entity>          -> per-source reported values, never summed

Every answer separates:
  * ``answered``    — nodes/edges with at least one verified quote
  * ``partial``     — some requested relation exists only as unverified/inferred
  * ``undetermined``— nothing in the material supports an answer (explicitly listed, never faked)

Usage
  python query_graph.py --graph /app/work/graph.json --queries queries.json --out /app/work/queries_result.json
  python query_graph.py --graph /app/work/graph.json --type entity --name "spiro-OMeTAD"
"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def canon(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[\u2010-\u2015\-_/]+", " ", s)
    s = re.sub(r"[^\w\u4e00-\u9fff \+\.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Graph:
    def __init__(self, g):
        self.g = g
        self.nodes = {n["id"]: n for n in g.get("nodes", [])}
        self.edges = {e["id"]: e for e in g.get("edges", [])}
        self.sources = {s["source_id"]: s for s in g.get("sources", [])}
        self.incident = defaultdict(list)
        for e in self.edges.values():
            self.incident[e["source"]].append((e["id"], "out"))
            self.incident[e["target"]].append((e["id"], "in"))
        self.surface = {}
        for n in self.nodes.values():
            for s in [n["label"]] + n.get("aliases", []):
                self.surface.setdefault(canon(s), n["id"])

    # ---------- resolution ----------
    def resolve(self, name, limit=5):
        c = canon(name)
        if c in self.surface:
            return [self.surface[c]], []
        # prefix / token-subset
        toks = set(c.split())
        cands = []
        for key, nid in self.surface.items():
            kt = set(key.split())
            if not kt:
                continue
            overlap = len(toks & kt) / max(1, len(toks | kt))
            ratio = difflib.SequenceMatcher(None, c, key).ratio()
            score = max(overlap, ratio)
            if score >= 0.62:
                cands.append((score, nid, key))
        cands.sort(reverse=True)
        ids, info = [], []
        for score, nid, key in cands[:limit]:
            if nid in ids:
                continue
            ids.append(nid)
            info.append({"id": nid, "matched_surface": key, "score": round(score, 2),
                         "label": self.nodes[nid]["label"], "type": self.nodes[nid]["type"]})
        return ids, info

    def node_brief(self, nid):
        n = self.nodes[nid]
        return {"id": nid, "label": n["label"], "type": n["type"],
                "aliases": n.get("aliases", []), "source_ids": n.get("source_ids", []),
                "evidence_status": n.get("evidence_status")}

    def edge_brief(self, eid):
        e = self.edges[eid]
        return {"id": eid, "source": e["source"], "target": e["target"], "type": e["type"],
                "condition": e.get("condition", ""), "direction_note": e.get("direction_note", ""),
                "evidence_status": e.get("evidence_status"),
                "source_ids": e.get("source_ids", []),
                "evidence": e.get("evidence", [])}

    # ---------- query implementations ----------
    def q_entity(self, name):
        ids, cands = self.resolve(name)
        if not ids:
            return "undetermined", [], [], [], [f"entity '{name}' not found in graph"], cands
        out_nodes, out_edges, ev = [self.node_brief(i) for i in ids], [], []
        for nid in ids:
            for eid, _d in self.incident[nid]:
                out_edges.append(self.edge_brief(eid))
        seen = set()
        for e in out_edges:
            for m in e["evidence"]:
                k = (e["id"], m["paragraph_id"])
                if k not in seen:
                    seen.add(k)
                    ev.append({"edge_id": e["id"], **m})
        status = "answered" if any(e["evidence_status"] == "verified" for e in out_edges) else "partial"
        notes = ["multiple surfaces matched; results are for all candidates"] if len(ids) > 1 else []
        return status, out_nodes, out_edges, ev, notes, cands

    def q_neighbors(self, name, relation=None, direction="both"):
        ids, cands = self.resolve(name)
        if not ids:
            return "undetermined", [], [], [], [f"entity '{name}' not found"], cands
        nodes, edges, ev = [], [], []
        for nid in ids:
            nodes.append(self.node_brief(nid))
            for eid, d in self.incident[nid]:
                e = self.edges[eid]
                if relation and canon(relation) not in canon(e["type"]):
                    continue
                if direction == "out" and d != "out":
                    continue
                if direction == "in" and d != "in":
                    continue
                edges.append(self.edge_brief(eid))
                other = e["target"] if d == "out" else e["source"]
                nodes.append(self.node_brief(other))
                for m in e["evidence"]:
                    ev.append({"edge_id": eid, **m})
        status = "answered" if edges else "undetermined"
        return status, _uniq(nodes), edges, ev, [] if edges else [f"no {relation or ''} relations"], cands

    def q_path(self, a, b, max_hops=3):
        ia, ca = self.resolve(a)
        ib, cb = self.resolve(b)
        if not ia or not ib:
            return "undetermined", [], [], [], [f"endpoint not found: {a if not ia else b}"], ca + cb
        start, goals = ia[0], set(ib)
        # BFS
        prev = {start: None}
        q = deque([(start, 0)])
        found = None
        while q and found is None:
            cur, d = q.popleft()
            if d >= max_hops:
                continue
            for eid, _dir in self.incident[cur]:
                e = self.edges[eid]
                nxt = e["target"] if e["source"] == cur else e["source"]
                if nxt not in prev:
                    prev[nxt] = (cur, eid)
                    if nxt in goals:
                        found = nxt
                        break
                    q.append((nxt, d + 1))
        if found is None:
            return "undetermined", [], [], [], [f"no path within {max_hops} hops"], ca + cb
        # reconstruct
        chain, cur = [], found
        while prev[cur] is not None:
            p, eid = prev[cur]
            chain.append((p, eid, cur))
            cur = p
        chain.reverse()
        nodes, edges, ev = [self.node_brief(start)], [], []
        for p, eid, nxt in chain:
            edges.append(self.edge_brief(eid))
            nodes.append(self.node_brief(nxt))
            for m in self.edges[eid]["evidence"]:
                ev.append({"edge_id": eid, **m})
        return "answered", _uniq(nodes), edges, ev, [f"path length {len(chain)}"], ca + cb

    def q_relation_search(self, relation, keyword=""):
        rel = canon(relation)
        kw = canon(keyword)
        edges, ev = [], []
        for e in self.edges.values():
            if rel and rel not in canon(e["type"]):
                continue
            blob = canon(" ".join([self.nodes[e["source"]]["label"], self.nodes[e["target"]]["label"],
                                   e.get("condition", "")]))
            if kw and kw not in blob:
                continue
            edges.append(self.edge_brief(e["id"]))
            for m in e["evidence"]:
                ev.append({"edge_id": e["id"], **m})
        nodes = _uniq([self.node_brief(x) for e in edges for x in (e["source"], e["target"])])
        status = "answered" if edges else "undetermined"
        return status, nodes, edges, ev, [] if edges else [f"no '{relation}' relations"], []

    def q_cross_paper(self):
        srcs = [s for s in self.sources.values()]
        sid_list = [s["source_id"] for s in srcs]
        shared, exclusive = [], defaultdict(list)
        for n in self.nodes.values():
            present = set(n.get("source_ids", []))
            if len(present) > 1:
                shared.append(self.node_brief(n["id"]))
            elif len(present) == 1:
                exclusive[next(iter(present))].append(self.node_brief(n["id"]))
        conflicts = self.g.get("conflict_log", [])
        nodes = shared + [x for v in exclusive.values() for x in v[:50]]
        notes = [f"library has {len(sid_list)} sources: {sid_list}"]
        if len(sid_list) < 2:
            notes.append("fewer than two sources: cross-paper comparison is not possible")
        status = "answered" if len(sid_list) >= 2 else "partial"
        return (status, _uniq(nodes), [], [],
                {"shared_entities": shared,
                 "exclusive_entities": dict(exclusive),
                 "conflicts": conflicts}, notes, [])

    def q_evidence_trace(self, ident):
        if ident in self.nodes:
            n = self.nodes[ident]
            ev = [dict(m) for m in n.get("mentions", [])]
            return "answered" if ev else "partial", [self.node_brief(ident)], [], ev, [], []
        if ident in self.edges:
            e = self.edges[ident]
            return "answered" if e["evidence"] else "partial", [], [self.edge_brief(ident)], e["evidence"], [], []
        return "undetermined", [], [], [], [f"id '{ident}' not found"], []

    def q_metric_compare(self, name):
        ids, cands = self.resolve(name)
        if not ids:
            return "undetermined", [], [], [], [f"'{name}' not found"], cands
        edges, ev, values = [], [], []
        metric_words = [canon(n) for n in [self.nodes[i]["label"] for i in ids] + ["PCE"]]
        seen_e, seen_v = set(), set()
        for nid in ids:
            for eid, _d in self.incident[nid]:
                e = self.edges[eid]
                if e["type"] not in ("reports", "measures", "evaluated_on", "improves", "compares"):
                    continue
                if eid not in seen_e:
                    seen_e.add(eid)
                    edges.append(self.edge_brief(eid))
                for m in e["evidence"]:
                    ev.append({"edge_id": eid, **m})
                    q = m["quote"]
                    qc = canon(q)
                    # only trust numbers from a quote that actually states the metric (or a %)
                    states_metric = ("%" in q) or any(w and w in qc for w in metric_words)
                    if not states_metric:
                        continue
                    nums = re.findall(r"-?\d+(?:\.\d+)?\s*%", q)
                    if not nums:
                        nums = re.findall(r"-?\d+(?:\.\d+)?", q)
                    key = (m["source_id"], m["paragraph_id"], q)
                    if key not in seen_v:
                        seen_v.add(key)
                        percent = [x for x in nums if x.endswith("%")]
                        values.append({"source_id": m["source_id"], "paragraph_id": m["paragraph_id"],
                                       "percent_values": percent,
                                       "other_numbers": [x for x in nums if not x.endswith("%")],
                                       "quote": q,
                                       "note": "" if percent else
                                       "no numeric value in this quote; metric may be shown only graphically"})
        notes = ["Values are listed per source/paragraph and are NOT aggregated or averaged; "
                 "different conditions/samples make a single cross-paper number invalid."]
        status = "answered" if edges else "undetermined"
        return status, _uniq([self.node_brief(x) for e in edges for x in (e["source"], e["target"])]), \
            edges, ev, {"reported_values": values}, notes, cands


def _uniq(items):
    seen, out = set(), []
    for it in items:
        k = it.get("id") if isinstance(it, dict) else str(it)
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def _normalize_result(res):
    """All query methods may return 6- or 7-tuples; normalise to
    (status, nodes, edges, evidence, extra_dict, notes_list, candidates)."""
    if len(res) == 7:
        status, nodes, edges, ev, extra, notes, cands = res
    else:
        status, nodes, edges, ev, notes, cands = res
        extra = {}
    if not isinstance(extra, dict):
        extra = {}
    if not isinstance(notes, list):
        notes = [str(notes)] if notes else []
    return status, nodes, edges, ev, extra, notes, cands or []


def run_one(G, q):
    t = (q.get("type") or "entity").lower()
    if t == "entity":
        res = G.q_entity(q.get("name", ""))
    elif t == "neighbors":
        res = G.q_neighbors(q.get("name", ""), q.get("relation"), q.get("direction", "both"))
    elif t == "path":
        res = G.q_path(q.get("from", ""), q.get("to", ""), int(q.get("max_hops", 3)))
    elif t == "relation_search":
        res = G.q_relation_search(q.get("relation", ""), q.get("keyword", ""))
    elif t == "cross_paper":
        res = G.q_cross_paper()
    elif t == "evidence_trace":
        res = G.q_evidence_trace(q.get("id", ""))
    elif t == "metric_compare":
        res = G.q_metric_compare(q.get("name", ""))
    else:
        res = ("undetermined", [], [], [], {}, [f"unknown query type '{t}'"], [])
    return _normalize_result(res)


def default_queries(G):
    """Generate a sensible 3+ query set when the case does not specify any."""
    qs = []
    # 1. highest-degree verified entity
    deg = defaultdict(int)
    for e in G.edges.values():
        if e["evidence_status"] == "verified":
            deg[e["source"]] += 1
            deg[e["target"]] += 1
    if deg:
        top = max(deg, key=deg.get)
        qs.append({"qid": "Q1", "type": "entity", "name": G.nodes[top]["label"],
                   "purpose": "neighbourhood of the most connected entity"})
    # 2. relation search on outperforms
    qs.append({"qid": "Q2", "type": "relation_search", "relation": "outperforms",
               "purpose": "which items are claimed to outperform others"})
    # 3. cross-paper alignment
    qs.append({"qid": "Q3", "type": "cross_paper",
               "purpose": "shared vs source-exclusive entities and conflicts"})
    # 4. evidence trace on one edge
    for e in G.edges.values():
        if e["evidence"]:
            qs.append({"qid": "Q4", "type": "evidence_trace", "id": e["id"],
                       "purpose": "trace one relation back to its original passage"})
            break
    return qs


def _short(s, n=110):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def format_answer(r, max_nodes=8):
    """Human-readable answer for one query record; the JSON output stays the source of truth."""
    lines = [f"{r['qid']} {r['query'].get('type')} -> {r['status']}"]
    a = r["answer"]
    nodes = a.get("nodes") or []
    for n in nodes[:max_nodes]:
        if not isinstance(n, dict):
            lines.append(f"  node {n}")
            continue
        srcs = ",".join(n.get("source_ids") or [])
        lines.append(f"  node {n.get('label')} [{n.get('type')}] {srcs}")
    if len(nodes) > max_nodes:
        lines.append(f"  … {len(nodes) - max_nodes} more nodes")
    seen_values = set()
    for rv in (a.get("extra") or {}).get("reported_values") or []:
        where = f"{rv.get('source_id')}/{rv.get('paragraph_id')}"
        if where in seen_values:      # two edges can cite the same paragraph
            continue
        seen_values.add(where)
        pct = rv.get("percent_values") or []
        other = rv.get("other_numbers") or []
        if pct:
            lines.append(f"  value {where}: {', '.join(pct)}")
        else:
            lines.append(f"  value {where}: no % value in the text"
                         + (f" (other numbers: {', '.join(map(str, other))})" if other else ""))
    for note in a.get("notes") or []:
        lines.append(f"  note {_short(note)}")
    if r.get("n_evidence"):
        lines.append(f"  evidence {r['n_evidence']} quote(s)")
        for ev in r["evidence"][:2]:
            if isinstance(ev, dict):
                lines.append(f"    {ev.get('source_id')}/{ev.get('paragraph_id')}: "
                             f"“{_short(ev.get('quote'), 90)}”")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="/app/work/graph.json")
    ap.add_argument("--queries", default=None, help="JSON file with a list of query objects")
    ap.add_argument("--out", default="/app/work/queries_result.json")
    ap.add_argument("--type", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print each answer's nodes, reported values, notes and evidence")
    args = ap.parse_args()

    with open(args.graph, "r", encoding="utf-8") as f:
        g = json.load(f)
    G = Graph(g)

    if args.queries and not os.path.exists(args.queries):
        sys.stderr.write(
            f"FATAL: query file not found: {args.queries}\n"
            "  Omit --queries to run the built-in default set (entity, relation_search,\n"
            "  cross_paper, evidence_trace), or use --type/--name for a single query.\n")
        sys.exit(2)
    if args.queries:
        with open(args.queries, "r", encoding="utf-8") as f:
            qs = json.load(f)
        if isinstance(qs, dict):
            qs = qs.get("queries", [])
    elif args.type:
        qs = [{"qid": "Q1", "type": args.type, "name": args.name, "id": args.name}]
    else:
        qs = default_queries(G)

    results = []
    for q in qs:
        status, nodes, edges, ev, extra, notes, cands = run_one(G, q)
        # An answer whose every node is rejected evidence, and which quotes nothing, is not an
        # answer: it used to come back "answered" with n_evidence=0.
        if status == "answered" and not ev and nodes and \
                all(isinstance(n, dict) and n.get("evidence_status") == "rejected" for n in nodes):
            status = "undetermined"
            notes = list(notes) + ["every matching node has rejected evidence; nothing to answer from"]
        rec = {
            "qid": q.get("qid"),
            "query": q,
            "status": status,
            "answer": {
                "nodes": nodes, "edges": edges,
                "extra": extra,
                "notes": notes,
                "candidates": cands,
            },
            "evidence": ev,
            "n_evidence": len(ev),
            "undetermined": notes if status == "undetermined" else [],
        }
        results.append(rec)

    out = {
        "case_id": g.get("case_id"),
        "n_queries": len(results),
        "n_answered": sum(1 for r in results if r["status"] == "answered"),
        "n_partial": sum(1 for r in results if r["status"] == "partial"),
        "n_undetermined": sum(1 for r in results if r["status"] == "undetermined"),
        "queries": results,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[query_graph] {len(results)} queries: {out['n_answered']} answered, "
          f"{out['n_partial']} partial, {out['n_undetermined']} undetermined -> {args.out}")
    verbose = args.verbose or bool(args.type)
    for r in results:
        print(f"  {r['qid']} {r['query'].get('type')}: {r['status']} "
              f"({len(r['answer']['nodes'])} nodes, {len(r['answer']['edges'])} edges, "
              f"{r['n_evidence']} evidence)")
        if verbose:
            print("\n" + format_answer(r))


if __name__ == "__main__":
    main()
