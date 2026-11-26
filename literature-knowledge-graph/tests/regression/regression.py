#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regression.py — the six cases a change must not break before a submission.

R1 full two-paper case         -> success, 35/34, >=3 queries answered
R2 one paper, no case.json     -> partial, says which evidence/identity is missing
R3 altered quote               -> that evidence is rejected, never counted as verified
R4 same label, two objects     -> two nodes with a kept_separate basis; a non-merge that
                                  cannot be applied is reported instead of being logged blindly
R5 paragraph without an id     -> derived d#### id, flagged, never presented as a source id
R6 budget guard truncation     -> bundle records the truncation, finalize reports partial

Run before every submission:

    python3 tests/regression/regression.py          # all six
    python3 tests/regression/regression.py R4 R6    # a subset

Exit code 0 = all pass. Each case is independent and builds its own fixture in a temp dir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "scripts")
DEMO = os.path.join(ROOT, "examples", "demo_perovskite")
PY = sys.executable

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  ->  {detail}"))


def sh(args, cwd=None, timeout=300):
    r = subprocess.run([PY] + args, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    if r.returncode != 0:
        print("    $ " + " ".join(args[1:]))
        print("    " + (r.stdout or r.stderr).strip()[-1200:])
    return r


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, p):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def pipeline(bundle, annotations, work, queries=None):
    """prepare is done by the caller; run build -> query -> finalize."""
    g = os.path.join(work, "graph.json")
    q = os.path.join(work, "queries_result.json")
    out = os.path.join(work, "out")
    os.makedirs(out, exist_ok=True)
    sh([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", bundle,
        "--annotations", annotations, "--out", g])
    qargs = [os.path.join(SCRIPTS, "query_graph.py"), "--graph", g, "--out", q]
    if queries:
        qargs += ["--queries", queries]
    sh(qargs)
    r = os.path.join(out, "result.json")
    sh([os.path.join(SCRIPTS, "finalize.py"), "--bundle", bundle, "--graph", g,
        "--queries", q, "--out", r, "--outdir", out])
    return jload(g), jload(q), jload(r)


# ---------------------------------------------------------------- R1
def r1(work):
    print("[R1] full two-paper case")
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"), "--out", b])
    g, q, r = pipeline(b, os.path.join(DEMO, "annotations.example.json"), work,
                       os.path.join(DEMO, "queries.example.json"))
    check("status is success", r["status"] == "success", r.get("status_reasons"))
    check("35 nodes / 34 edges", (len(g["nodes"]), len(g["edges"])) == (35, 34),
          (len(g["nodes"]), len(g["edges"])))
    check("evidence coverage 100%", r["validation"]["evidence_coverage"] == 1.0)
    check(">=3 queries answered", q["n_answered"] >= 3, q.get("n_answered"))
    check("no undetermined queries", q["n_undetermined"] == 0)


# ---------------------------------------------------------------- R2
def r2(work):
    print("[R2] one paper, no case.json / task.md")
    ind = os.path.join(work, "input")
    os.makedirs(ind)
    for f in ("corpus-manifest.json", "primary-material.json"):
        shutil.copy(os.path.join(DEMO, "input", f), ind)
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", ind, "--out", b])
    ann = os.path.join(work, "ann.json")
    sh([os.path.join(SCRIPTS, "heuristic_extract.py"), "--bundle", b, "--out", ann])
    g, q, r = pipeline(b, ann, work)
    reasons = " ".join(r.get("status_reasons") or [])
    check("degrades to partial, not success", r["status"] == "partial", r["status"])
    check("names the missing second source", "source(s)" in reasons, reasons)
    check("names the missing case_id", "case_id" in reasons, reasons)
    check("graph still built", len(g["nodes"]) > 0, len(g["nodes"]))


# ---------------------------------------------------------------- R3
def r3(work):
    print("[R3] quote altered — must be rejected, not silently kept")
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"), "--out", b])
    ann = jload(os.path.join(DEMO, "annotations.example.json"))
    target = ann["edges"][0]
    target["evidence"] = [{"source_id": target["evidence"][0]["source_id"],
                           "paragraph_id": target["evidence"][0]["paragraph_id"],
                           "quote": "This sentence was paraphrased and appears nowhere in the corpus."}]
    bad = os.path.join(work, "ann_bad.json")
    jdump(ann, bad)
    g, q, r = pipeline(b, bad, work, os.path.join(DEMO, "queries.example.json"))
    kinds = {u.get("kind") for u in g.get("uncertainty", [])}
    check("rejected quote recorded as quote_not_found", "quote_not_found" in kinds, kinds)
    check("altered evidence not counted as verified",
          g["stats"]["n_edges_verified"] < len(g["edges"]),
          (g["stats"].get("n_edges_verified"), len(g["edges"])))
    check("status no longer success", r["status"] != "success", r["status"])


# ---------------------------------------------------------------- R4
def r4(work):
    print("[R4] same label, two different objects")
    ind = os.path.join(work, "input")
    os.makedirs(ind)
    jdump({"case_id": "r4", "sources": [
        {"source_id": "P1", "role": "primary", "doi": "10.1/p1", "title": "Paper one", "authors": ["A"]},
        {"source_id": "P2", "role": "secondary", "doi": "10.1/p2", "title": "Paper two", "authors": ["B"]}]},
        os.path.join(ind, "corpus-manifest.json"))
    t1 = "The perovskite absorber in this study is methylammonium lead iodide, measured in a mesoscopic device."
    t2 = "The perovskite absorber in this study is a caesium-containing triple cation mixed halide, measured in a planar device."
    jdump({"paragraphs": [
        {"source_id": "P1", "id": "p1", "text": t1},
        {"source_id": "P2", "id": "p2", "text": t2}]}, os.path.join(ind, "material.json"))
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", ind, "--out", b])

    def ann_for(separate):
        nodes = []
        for sid, pid, key, quote, label in (
                ("P1", "p1", "perovskite|MAPbI3" if separate else "perovskite", "methylammonium lead iodide", "perovskite"),
                ("P2", "p2", "perovskite|CsFAMA" if separate else "perovskite", "caesium-containing triple cation", "perovskite")):
            nodes.append({"label": label, "type": "material", "canonical_key": key,
                          "mentions": [{"source_id": sid, "paragraph_id": pid, "quote": quote}]})
        return {"nodes": nodes, "edges": [], "uncertainty": [],
                "merge_candidates": [{"surfaces": ["perovskite|MAPbI3", "perovskite|CsFAMA"] if separate
                                      else ["perovskite", "Perovskite"],
                                      "decision": "kept_separate",
                                      "basis": "different absorber compositions, different devices"}],
                "source_conflicts": []}

    a = os.path.join(work, "ann_ok.json")
    jdump(ann_for(True), a)
    g, _, _ = pipeline(b, a, os.path.join(work, "ok"))
    mats = [n for n in g["nodes"] if n["type"] == "material"]
    check("two material nodes kept apart", len(mats) == 2, [n["label"] for n in mats])
    check("each node cites its own paper only",
          sorted(tuple(n["source_ids"]) for n in mats) == [("P1",), ("P2",)],
          [n["source_ids"] for n in mats])
    check("kept_separate decision recorded with basis",
          any(m["decision"] == "kept_separate" and m.get("basis") for m in g["merge_log"]),
          g["merge_log"])

    a2 = os.path.join(work, "ann_bad.json")
    jdump(ann_for(False), a2)
    g2, _, _ = pipeline(b, a2, os.path.join(work, "bad"))
    check("unappliable non-merge is reported",
          any(c.get("kind") == "kept_separate_single_key" for c in g2["conflict_log"]),
          g2["conflict_log"])


# ---------------------------------------------------------------- R5
def r5(work):
    print("[R5] paragraph without an id")
    ind = os.path.join(work, "input")
    os.makedirs(ind)
    jdump({"case_id": "r5", "sources": [{"source_id": "P1", "role": "primary",
                                         "doi": "10.1/p1", "title": "Paper one", "authors": ["A"]}]},
          os.path.join(ind, "corpus-manifest.json"))
    t = "Films were annealed at 100 degrees Celsius for ten minutes in a nitrogen glovebox."
    jdump({"paragraphs": [{"source_id": "P1", "text": t}]}, os.path.join(ind, "material.json"))
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", ind, "--out", b])
    bundle = jload(b)
    ok = all(p["paragraph_id"].startswith("d") and p.get("id_derived") for p in bundle["paragraphs"])
    check("derived id assigned and flagged in the bundle", ok,
          [(p["paragraph_id"], p.get("id_derived")) for p in bundle["paragraphs"]])
    pid = bundle["paragraphs"][0]["paragraph_id"]
    ann = os.path.join(work, "ann.json")
    jdump({"nodes": [{"label": "annealing", "type": "method", "aliases": [],
                      "mentions": [{"source_id": "P1", "paragraph_id": pid,
                                    "quote": "annealed at 100 degrees Celsius"}]}],
           "edges": [], "merge_candidates": [], "source_conflicts": [], "uncertainty": []}, ann)
    gpath = os.path.join(work, "g.json")
    sh([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", b, "--annotations", ann, "--out", gpath])
    g = jload(gpath)
    kinds = [m.get("paragraph_id_kind") for n in g["nodes"] for m in n["mentions"]]
    check("mention marks the id as derived", kinds and all(k == "derived" for k in kinds), kinds)


# ---------------------------------------------------------------- R6
def r6(work):
    print("[R6] budget guard truncation")
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"),
        "--out", b, "--max-paragraphs", "8"])
    bundle = jload(b)
    bud = bundle.get("budget") or {}
    check("bundle records the truncation", bud.get("truncated") is True, bud)
    check("kept <= cap", bud.get("kept_paragraphs", 99) <= 8, bud.get("kept_paragraphs"))
    check("truncation is warned, not silent",
          any("budget guard" in w for w in bundle.get("warnings", [])), bundle.get("warnings"))
    ann = os.path.join(work, "ann.json")
    sh([os.path.join(SCRIPTS, "heuristic_extract.py"), "--bundle", b, "--out", ann])
    _, _, r = pipeline(b, ann, work)
    reasons = " ".join(r.get("status_reasons") or [])
    check("finalize refuses to call it complete", r["status"] == "partial", r["status"])
    check("budget reason surfaced", "budget guard" in reasons, reasons)


CASES = {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6}


def main(argv):
    wanted = [a.upper() for a in argv[1:]] or list(CASES)
    unknown = [w for w in wanted if w not in CASES]
    if unknown:
        print(f"unknown case(s): {unknown}; choose from {list(CASES)}")
        return 2
    for name in wanted:
        tmp = tempfile.mkdtemp(prefix=f"lkg_{name.lower()}_")
        try:
            CASES[name](tmp)
        except Exception as e:  # noqa: BLE001 — a crashed case is a failed case
            check(f"{name} completed without crashing", False, f"{type(e).__name__}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
