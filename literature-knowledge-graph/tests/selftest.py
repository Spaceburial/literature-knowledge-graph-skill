#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — run this before submitting. It checks the parts that most often break:

  1. quote verification: exact / normalized accepted, paraphrase rejected
  2. merge safety: two surfaces that canonicalise identically must not delete the node
  3. type conflict: merging a material with a method is refused and logged
  4. end-to-end on the worked example: status, evidence coverage, queries, output_contract keys
  5. undetermined query: an unknown entity returns undetermined, never a fabricated answer

Exit code 0 = all pass.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
PY = sys.executable
sys.path.insert(0, SCRIPTS)

from verify_evidence import verify_quote  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  ->  {detail}"))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
    return r


def unit_tests():
    print("[1] quote verification")
    text = ("The archetypal absorber methylammonium lead iodide is widely used. "
            "We prepared films by spin-coating and achieved a PCE of 20.1%.")
    check("exact substring accepted", verify_quote("achieved a PCE of 20.1%", text)["status"] == "exact")
    check("curly-quote/space normalisation accepted",
          verify_quote("We  prepared films by spin-coating", text)["status"] == "normalized")
    check("paraphrase rejected",
          verify_quote("the authors obtained a power conversion efficiency of about twenty percent",
                       text)["status"] == "not_found")
    check("empty quote rejected", verify_quote("", text)["status"] == "not_found")


def example_case():
    src = os.path.join(ROOT, "examples", "demo_perovskite")
    tmp = tempfile.mkdtemp(prefix="lkg_selftest_")
    work, out = os.path.join(tmp, "work"), os.path.join(tmp, "out")
    os.makedirs(work); os.makedirs(out)
    run([PY, os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(src, "input"),
         "--out", os.path.join(work, "case_bundle.json")])
    run([PY, os.path.join(SCRIPTS, "build_graph.py"), "--bundle", os.path.join(work, "case_bundle.json"),
         "--annotations", os.path.join(src, "annotations.example.json"), "--out", os.path.join(work, "graph.json")])
    run([PY, os.path.join(SCRIPTS, "query_graph.py"), "--graph", os.path.join(work, "graph.json"),
         "--queries", os.path.join(src, "queries.example.json"), "--out", os.path.join(work, "q.json")])
    run([PY, os.path.join(SCRIPTS, "finalize.py"), "--bundle", os.path.join(work, "case_bundle.json"),
         "--graph", os.path.join(work, "graph.json"), "--queries", os.path.join(work, "q.json"),
         "--out", os.path.join(out, "result.json"), "--outdir", out])
    g = json.load(open(os.path.join(work, "graph.json")))
    q = json.load(open(os.path.join(work, "q.json")))
    r = json.load(open(os.path.join(out, "result.json")))
    return tmp, g, q, r


def e2e_tests():
    print("[2] end-to-end on the worked example")
    tmp, g, q, r = example_case()
    try:
        labels = [n["label"] for n in g["nodes"]]
        check("shared material survives merge", "Spiro-OMeTAD" in labels, labels[:5])
        check("no unresolved edge endpoints",
              not any(c["kind"] == "edge_endpoint_missing" for c in g["conflict_log"]))
        check("every edge has evidence", all(e["evidence"] for e in g["edges"]))
        check("every edge endpoint resolves to a node",
              all(e["source"] in {n["id"] for n in g["nodes"]} and e["target"] in {n["id"] for n in g["nodes"]}
                  for e in g["edges"]))
        check("status is success", r["status"] == "success", r.get("status_reasons"))
        check("evidence coverage is 100%", r["validation"]["evidence_coverage"] == 1.0)
        check("at least 3 queries answered", q["n_answered"] >= 3, q)
        check("all queries answered", q["n_undetermined"] == 0)
        check("output_contract keys present",
              all(k in r for k in ("entities", "relations", "queries", "evidence", "status")))
        check("merge decisions recorded", len(r["merge_log"]) >= 1)
        check("cross-paper conflicts recorded", len(r["conflict_log"]) >= 1)
        check("derived ids flagged, not pages",
              all(m.get("paragraph_id_kind") != "derived" or str(m["paragraph_id"]).startswith("d")
                  for n in g["nodes"] for m in n["mentions"]))
        check("no numeric cross-paper aggregation",
              any(u["kind"] == "value_not_reported_in_text" for u in r["uncertainty"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def incremental_test():
    """Adding paper P2 to a P1-only graph must reproduce the full build and keep P1 ids."""
    print("[3] incremental update equals full build")
    src = os.path.join(ROOT, "examples", "demo_perovskite")
    tmp = tempfile.mkdtemp(prefix="lkg_inc_")
    try:
        work = os.path.join(tmp, "w"); os.makedirs(work)
        bundle = os.path.join(work, "b.json")
        run([PY, os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(src, "input"),
             "--out", bundle])
        ann = json.load(open(os.path.join(src, "annotations.example.json"), encoding="utf-8"))

        def split(sid):
            nodes = [{**n, "mentions": [m for m in n["mentions"] if m["source_id"] == sid]}
                     for n in ann["nodes"] if any(m["source_id"] == sid for m in n["mentions"])]
            edges = [{**e, "evidence": [m for m in e["evidence"] if m["source_id"] == sid]}
                     for e in ann["edges"] if any(m["source_id"] == sid for m in e["evidence"])]
            return {"nodes": nodes, "edges": edges, "merge_candidates": [],
                    "source_conflicts": [], "uncertainty": []}

        p1 = os.path.join(work, "p1.json"); p2 = os.path.join(work, "p2.json")
        json.dump(split("P1"), open(p1, "w"), ensure_ascii=False)
        json.dump(split("P2"), open(p2, "w"), ensure_ascii=False)
        g1, g2, full = (os.path.join(work, f) for f in ("g1.json", "g2.json", "full.json"))
        run([PY, os.path.join(SCRIPTS, "build_graph.py"), "--bundle", bundle,
             "--annotations", p1, "--out", g1])
        run([PY, os.path.join(SCRIPTS, "add_paper.py"), "--graph", g1, "--bundle", bundle,
             "--annotations", p2, "--out", g2, "--change-log", os.path.join(work, "chg.json")])
        run([PY, os.path.join(SCRIPTS, "build_graph.py"), "--bundle", bundle,
             "--annotations", os.path.join(src, "annotations.example.json"), "--out", full])
        a, b, f = (json.load(open(x)) for x in (g1, g2, full))
        ids1 = {n["label"]: n["id"] for n in a["nodes"]}
        ids2 = {n["label"]: n["id"] for n in b["nodes"]}
        check("existing ids preserved", all(ids2.get(k) == v for k, v in ids1.items()))
        check("incremental node count equals full build", len(b["nodes"]) == len(f["nodes"]),
              f'{len(b["nodes"])} vs {len(f["nodes"])}')
        check("incremental edge count equals full build", len(b["edges"]) == len(f["edges"]),
              f'{len(b["edges"])} vs {len(f["edges"])}')
        spiro = [n for n in b["nodes"] if n["label"] == "Spiro-OMeTAD"][0]
        check("shared concept merged across papers", set(spiro["source_ids"]) == {"P1", "P2"})
        ch = json.load(open(os.path.join(work, "chg.json")))
        check("change record lists added+merged", bool(ch["added_nodes"]) and bool(ch["merged_nodes"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def negative_tests():
    print("[4] undetermined query and merge type conflict")
    tmp = tempfile.mkdtemp(prefix="lkg_neg_")
    try:
        gpath = os.path.join(tmp, "g.json")
        json.dump({"case_id": "t", "sources": [], "nodes": [], "edges": [],
                   "merge_log": [], "conflict_log": [], "uncertainty": []}, open(gpath, "w"))
        sys.path.insert(0, SCRIPTS)
        from query_graph import Graph, run_one
        G = Graph(json.load(open(gpath)))
        status, *_ = run_one(G, {"type": "entity", "name": "does-not-exist"})
        check("unknown entity -> undetermined", status == "undetermined", status)

        # type conflict merge must be refused
        bundle = os.path.join(tmp, "b.json")
        json.dump({"case_id": "t", "sources": [], "warnings": [],
                   "paragraphs": [{"source_id": "P1", "paragraph_id": "p1",
                                   "text": "Alpha material and Beta method are reported together in this long sentence.",
                                   "section": "", "order_in_source": 1, "id_derived": False}]},
                  open(bundle, "w"))
        ann = os.path.join(tmp, "a.json")
        json.dump({"nodes": [
            {"label": "Alpha", "type": "material", "aliases": [],
             "mentions": [{"source_id": "P1", "paragraph_id": "p1",
                           "quote": "Alpha material and Beta method are reported together"}]},
            {"label": "Beta", "type": "method", "aliases": [],
             "mentions": [{"source_id": "P1", "paragraph_id": "p1",
                           "quote": "Beta method are reported together in this long sentence"}]}],
            "edges": [], "merge_candidates": [{"surfaces": ["Alpha", "Beta"], "decision": "merged",
                                               "basis": "should be refused"}],
            "source_conflicts": [], "uncertainty": []}, open(ann, "w"))
        out = os.path.join(tmp, "g2.json")
        run([PY, os.path.join(SCRIPTS, "build_graph.py"), "--bundle", bundle,
             "--annotations", ann, "--out", out])
        g = json.load(open(out))
        check("type-mismatched merge refused",
              any(n["label"] == "Alpha" for n in g["nodes"]) and any(n["label"] == "Beta" for n in g["nodes"]))
        check("type conflict logged", any(c.get("kind") == "merge_type_conflict" for c in g["conflict_log"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unit_tests()
    e2e_tests()
    incremental_test()
    negative_tests()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
