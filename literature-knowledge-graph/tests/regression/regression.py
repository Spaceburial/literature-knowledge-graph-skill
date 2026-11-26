#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regression.py — the thirteen cases a change must not break before a submission.

R1 full two-paper case         -> success, 35/34, >=3 queries answered
R2 one paper, no case.json     -> partial, says which evidence/identity is missing
R3 altered quote               -> that evidence is rejected, never counted as verified
R4 same label, two objects     -> two nodes with a kept_separate basis; a non-merge that
                                  cannot be applied is reported instead of being logged blindly
R5 paragraph without an id     -> derived d#### id, flagged, never presented as a source id
R6 budget guard truncation     -> bundle records the truncation, finalize reports partial
R7 silent-failure gates        -> an empty corpus, missing annotations, node-less annotations and a
                                  missing query file each exit non-zero with a reason (they used to
                                  report nothing and succeed)
R8 one digit edited in a quote -> rejected as a numeric mismatch even at 0.95 string similarity
R11 schema conformance       -> the shipped annotations, the shipped example graph and a freshly
                                built graph all satisfy schema/graph.schema.json, a corrupted graph
                                does not, and no stored quote exceeds the documented limit
R10 input shapes             -> JATS .xml is discovered, an aggregate material.json keeps its
                                metadata, a dict-of-dicts corpus is counted once, inline markup
                                does not split tokens, back matter stays out of the body, and a
                                nested record inherits its paper's source_id
R12 PDF paragraphs          -> a text PDF becomes several located blocks (not one blob), hyphenated
                                line breaks are joined, back matter is dropped, and `pdf_page` is
                                recorded as a reading aid while the id stays a derived d####
R13 task-driven queries     -> questions in the case task become queries that are answered from the
                                graph; a term that is not a node is still found through the quotes;
                                a question with no grounding comes back undetermined with a reason
R9 no silent empty results   -> annotations that match no paragraph stop the build; an answer
                                with no verified evidence is undetermined; a failed validation
                                check cannot sit beside status="success"

Run before every submission:

    python3 tests/regression/regression.py          # all thirteen
    python3 tests/regression/regression.py R4 R6    # a subset

Exit code 0 = all pass. Each case is independent and builds its own fixture in a temp dir.
"""
import json
import os
import re
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


def shx(args, cwd=None, timeout=300):
    """Run a command whose failure IS the assertion; does not echo the expected error."""
    return subprocess.run([PY] + args, capture_output=True, text=True, cwd=cwd, timeout=timeout)


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
    rt = r.get("runtime") or {}
    check("result.json records measured stage times",
          all(isinstance(rt.get(k), (int, float)) for k in
              ("prepare_seconds", "build_seconds", "finalize_seconds")), rt)
    check("result.json echoes the input budget",
          (r.get("budget") or {}).get("kept_paragraphs") == 141, r.get("budget"))


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


# ---------------------------------------------------------------- R7
def r7(work):
    print("[R7] empty corpus / missing annotations / missing query file fail loudly")
    ind = os.path.join(work, "input")
    os.makedirs(ind)
    jdump({"note": "not a paper"}, os.path.join(ind, "notes.json"))
    b = os.path.join(work, "bundle.json")
    r = shx([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", ind, "--out", b])
    check("empty corpus exits non-zero", r.returncode != 0, r.returncode)
    check("empty corpus names the accepted file names", "material.json" in (r.stderr or ""),
          (r.stderr or "")[:200])

    b2 = os.path.join(work, "bundle2.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"), "--out", b2])
    r = shx([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", b2,
            "--annotations", os.path.join(work, "absent.json"), "--out", os.path.join(work, "g.json")])
    check("missing annotations exits non-zero", r.returncode != 0, r.returncode)
    check("missing annotations points at the two routes",
          "run.sh all" in (r.stderr or ""), (r.stderr or "")[:300])

    empty = os.path.join(work, "ann_empty.json")
    jdump({"nodes": [], "edges": []}, empty)
    r = shx([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", b2,
            "--annotations", empty, "--out", os.path.join(work, "g2.json")])
    check("node-less annotations exits non-zero", r.returncode != 0, r.returncode)

    g = os.path.join(work, "g.json")
    sh([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", b2,
        "--annotations", os.path.join(DEMO, "annotations.example.json"), "--out", g])
    r = shx([os.path.join(SCRIPTS, "query_graph.py"), "--graph", g,
            "--queries", os.path.join(work, "nope.json"), "--out", os.path.join(work, "q.json")])
    check("missing query file exits non-zero", r.returncode != 0, r.returncode)
    check("missing query file does not fall back silently",
          "not found" in (r.stderr or ""), (r.stderr or "")[:200])

    r = shx([os.path.join(SCRIPTS, "run_all.py"), "--work", os.path.join(work, "w"),
            "--out", os.path.join(work, "o")])
    check("run_all without --case-dir exits non-zero", r.returncode != 0, r.returncode)


# ---------------------------------------------------------------- R8
def r8(work):
    print("[R8] one digit edited inside a verbatim-looking quote")
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"), "--out", b])
    ann = jload(os.path.join(DEMO, "annotations.example.json"))
    target = next(e for e in ann["edges"] if "14.7%" in json.dumps(e["evidence"]))
    ev = dict(target["evidence"][0])
    ev["quote"] = ev["quote"].replace("14.7%", "17.4%")
    target["evidence"] = [ev]
    bad = os.path.join(work, "ann_bad.json")
    jdump(ann, bad)
    g, _, _ = pipeline(b, bad, work, os.path.join(DEMO, "queries.example.json"))
    notes = [u.get("detail", "") for u in g.get("uncertainty", []) if u.get("kind") == "quote_not_found"]
    check("modified number rejected as quote_not_found", bool(notes), notes)
    check("rejection states the numeric mismatch",
          any("numeric mismatch" in n and "17.4" in n for n in notes), notes[:1])
    check("fewer verified edges than edges",
          g["stats"]["n_edges_verified"] < len(g["edges"]),
          (g["stats"].get("n_edges_verified"), len(g["edges"])))


# ---------------------------------------------------------------- R9
def r9(work):
    print("[R9] a result with no verified evidence is never reported as a result")
    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"), "--out", b])

    alien = {"nodes": [{"label": "Ghost material", "type": "material",
                        "mentions": [{"source_id": "P1", "paragraph_id": "d0063",
                                      "quote": "An invented sentence that appears in no paragraph of this corpus."}]}],
             "edges": []}
    ap = os.path.join(work, "alien.json")
    jdump(alien, ap)
    r = shx([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", b, "--annotations", ap,
             "--out", os.path.join(work, "g_alien.json")])
    check("annotations matching no paragraph stop the build", r.returncode != 0, r.returncode)
    check("message says the annotations do not match this bundle",
          "do not match" in (r.stderr or ""), (r.stderr or "")[:200])

    # one good node, one node whose only quote fails: the query for the failing node has nothing
    # verified to answer from and must not report "answered"
    demo_ann = jload(os.path.join(DEMO, "annotations.example.json"))
    good = next(n for n in demo_ann["nodes"] if n.get("mentions"))
    mixed = {"nodes": [good,
                       {"label": "Ghost material", "type": "material",
                        "mentions": [{"source_id": "P1", "paragraph_id": "d0063",
                                      "quote": "An invented sentence that appears in no paragraph of this corpus."}]}],
             "edges": []}
    mp = os.path.join(work, "mixed.json")
    jdump(mixed, mp)
    g = os.path.join(work, "g_mixed.json")
    sh([os.path.join(SCRIPTS, "build_graph.py"), "--bundle", b, "--annotations", mp, "--out", g])
    q = os.path.join(work, "q.json")
    sh([os.path.join(SCRIPTS, "query_graph.py"), "--graph", g, "--out", q,
        "--type", "entity", "--name", "Ghost material"])
    res = jload(q)["queries"][0]
    check("query on evidence-rejected node is not answered", res["status"] != "answered",
          res["status"])
    check("it carries no evidence records", res["n_evidence"] == 0, res["n_evidence"])

    # a failed validation check must move the status off success
    def run_check(pid):
        graph = jload(g)
        for n in graph["nodes"]:
            for m in n["mentions"]:
                m["paragraph_id_kind"] = "derived"
                m["paragraph_id"] = pid
        gp = os.path.join(work, f"g_check_{pid}.json")
        jdump(graph, gp)
        out = os.path.join(work, f"out_{pid}")
        os.makedirs(out, exist_ok=True)
        rp = os.path.join(out, "result.json")
        sh([os.path.join(SCRIPTS, "finalize.py"), "--bundle", b, "--graph", gp, "--queries", q,
            "--out", rp, "--outdir", out])
        rj = jload(rp)
        return rj["status"], " ".join(rj.get("status_reasons") or [])

    # a bare integer derived id could be read as a PDF page number: that must fail
    page_check = "never asserted as PDF pages"
    status, reasons = run_check("12")
    check("failed validation check is not success", status != "success", status)
    check("the failed check is named in status_reasons",
          "validation check(s) failed" in reasons and page_check in reasons, reasons)
    # a namespaced derived id is not a page number and must not be flagged
    _, reasons2 = run_check("p12")
    check("namespaced derived id is not flagged as a page number",
          page_check not in reasons2, reasons2)


# ---------------------------------------------------------------- R10
PA = ("Perovskite solar cells with a passivated absorber reached a power conversion efficiency of "
      "21.3% under AM1.5G illumination, with an open-circuit voltage of 1.12 V.")
PB = ("A control device without the passivation step reached 19.8% under the same measurement "
      "conditions and lost a third of its efficiency over 500 hours.")


def r10(work):
    print("[R10] input shapes: JATS xml, aggregate metadata, keyed dicts, nested records")

    # (1) JATS full text arrives as one .xml per paper and must be discovered
    d = os.path.join(work, "jats"); os.makedirs(d)
    for name, text in (("paper_one.xml", PA), ("paper_two.xml", PB)):
        open(os.path.join(d, name), "w", encoding="utf-8").write(
            f'<article><body><sec id="s1"><title>Results</title><p id="p1">{text}</p>'
            f'</sec></body></article>')
    b1 = os.path.join(work, "b1.json")
    r = shx([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", d, "--out", b1])
    bundle = jload(b1) if r.returncode == 0 else {"paragraphs": [], "sources": []}
    check("JATS .xml files are discovered", r.returncode == 0 and len(bundle["paragraphs"]) == 2,
          (r.returncode, len(bundle["paragraphs"])))

    # (2) an aggregate material.json carries doi/title per source, without a manifest
    d = os.path.join(work, "agg"); os.makedirs(d)
    jdump({"P1": {"doi": "10.1/a", "title": "Paper A",
                  "paragraphs": [{"source_id": "P1", "paragraph_id": "s1p1", "text": PA}]},
           "P2": {"doi": "10.1/b", "title": "Paper B",
                  "paragraphs": [{"source_id": "P2", "paragraph_id": "s1p1", "text": PB}]}},
          os.path.join(d, "material.json"))
    b2 = os.path.join(work, "b2.json")
    shx([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", d, "--out", b2])
    bundle = jload(b2)
    dois = {s["source_id"]: s.get("doi") for s in bundle["sources"]}
    check("aggregate material.json keeps its per-source metadata",
          dois.get("P1") == "10.1/a" and dois.get("P2") == "10.1/b", dois)

    # (3) {"p1": {"text": ...}} is read by two strategies and must be counted once
    d = os.path.join(work, "keyed"); os.makedirs(d)
    jdump({"p1": {"text": PA}, "p2": {"text": PB}},
          os.path.join(d, "primary-material.json"))
    b3 = os.path.join(work, "b3.json")
    shx([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", d, "--out", b3])
    bundle = jload(b3)
    check("a keyed dict corpus is not double-counted", len(bundle["paragraphs"]) == 2,
          [(p["source_id"], p["paragraph_id"]) for p in bundle["paragraphs"]])

    # (4) real JATS: inline markup must not split a token, and back matter is not body text
    d = os.path.join(work, "jats_inline"); os.makedirs(d)
    xml = ('<article><body>'
           '<sec id="s1"><title>Results</title>'
           f'<p id="p1">Films of MAPbI<sub>3</sub> passivated with PEAI reached 21.3% and the '
           'TiO<sub>2</sub> layer thickness was 120 nm.</p></sec>'
           '<sec id="notes1"><title>Author Contributions</title>'
           '<p>Conceptualization, A.B.; methodology, C.D.; supervision, E.F.; funding, G.H.</p></sec>'
           '<sec id="s2"><title>Funding Statement</title>'
           '<p>This work was supported by grant number 123456 from the example foundation.</p></sec>'
           '</body></article>')
    open(os.path.join(d, "paper.xml"), "w", encoding="utf-8").write(xml)
    b5 = os.path.join(work, "b5.json")
    shx([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", d, "--out", b5])
    bundle = jload(b5)
    texts = " ".join(p["text"] for p in bundle["paragraphs"])
    check("inline sub/sup markup does not split MAPbI3", "MAPbI3" in texts and "MAPbI 3" not in texts,
          texts[:120])
    check("back-matter sections are not body paragraphs",
          "Conceptualization" not in texts and "supported by grant" not in texts, texts[:200])
    check("the omission is reported, not silent",
          any("back-matter" in w for w in bundle["warnings"]), bundle["warnings"][:3])

    # (5) a record nested under a paper object inherits that paper's source_id
    d = os.path.join(work, "nested"); os.makedirs(d)
    jdump({"papers": [{"source_id": "P1", "abstract": {"text": PA}},
                      {"source_id": "P2", "abstract": {"text": PB}}]},
          os.path.join(d, "material.json"))
    b4 = os.path.join(work, "b4.json")
    shx([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", d, "--out", b4])
    bundle = jload(b4)
    sids = sorted({p["source_id"] for p in bundle["paragraphs"]})
    check("a nested record inherits its paper's source_id", sids == ["P1", "P2"], sids)
    check("both nested paragraphs survive", len(bundle["paragraphs"]) == 2,
          len(bundle["paragraphs"]))


# ---------------------------------------------------------------- R11
NODE_TYPES = {"researcher", "material", "method", "task", "metric", "conclusion", "dataset",
              "model", "other"}
EDGE_TYPES = {"uses", "compares", "outperforms", "supports", "contradicts", "measures",
              "evaluated_on", "reports", "improves", "increases", "decreases", "part_of", "produces",
              "based_on", "cites", "other"}
MERGE_DECISIONS = {"merged", "kept_separate", "not_applicable"}


def _evidence_problems(ev, where):
    out = []
    for k in ("source_id", "paragraph_id", "quote"):
        if not isinstance(ev.get(k), str) or not ev.get(k):
            out.append(f"{where}: missing {k}")
    q = ev.get("quote") or ""
    if len(q) < 8 or len(q) > 300:
        out.append(f"{where}: quote length {len(q)} outside 8..300")
    if ev.get("match") not in (None, "exact", "normalized", "fuzzy"):
        out.append(f"{where}: bad match {ev.get('match')!r}")
    return out


def mini_validate_graph(g):
    """The subset of schema/graph.schema.json that a stdlib-only run can check.

    The schema accepts either shape, so the required top-level keys depend on which one this is:
    an annotation set (nodes + edges) or a built graph (case_id, sources, logs).
    """
    problems = []
    is_graph = "merge_log" in g or "sources" in g
    required = (("case_id", "sources", "nodes", "edges", "merge_log", "conflict_log", "uncertainty")
                if is_graph else ("nodes", "edges"))
    for k in required:
        if k not in g:
            problems.append(f"missing top-level key {k}")
    for i, n in enumerate(g.get("nodes", [])):
        if not n.get("label"):
            problems.append(f"node[{i}]: empty label")
        if n.get("type") not in NODE_TYPES:
            problems.append(f"node[{i}]: type {n.get('type')!r} not in schema")
        if n.get("id") and not re.fullmatch(r"N\d{4}", str(n["id"])):
            problems.append(f"node[{i}]: id {n.get('id')!r}")
        for j, m in enumerate(n.get("mentions") or []):
            problems += _evidence_problems(m, f"node[{i}].mention[{j}]")
    for i, e in enumerate(g.get("edges", [])):
        for k in ("source_label", "target_label"):
            if not e.get(k):
                problems.append(f"edge[{i}]: missing {k}")
        if e.get("type") not in EDGE_TYPES:
            problems.append(f"edge[{i}]: type {e.get('type')!r} not in schema")
        for j, m in enumerate(e.get("evidence") or []):
            problems += _evidence_problems(m, f"edge[{i}].evidence[{j}]")
    for i, m in enumerate(g.get("merge_log", []) if is_graph else []):
        if not isinstance(m.get("surfaces"), list) or len(m["surfaces"]) < 2:
            problems.append(f"merge_log[{i}]: surfaces < 2")
        if m.get("decision") not in MERGE_DECISIONS:
            problems.append(f"merge_log[{i}]: decision {m.get('decision')!r}")
        if not isinstance(m.get("basis"), (str, type(None))):
            problems.append(f"merge_log[{i}]: basis not a string")
    for i, m in enumerate(g.get("merge_candidates", []) if not is_graph else []):
        if not isinstance(m.get("surfaces"), list) or len(m["surfaces"]) < 2:
            problems.append(f"merge_candidates[{i}]: surfaces < 2")
        if m.get("decision") not in MERGE_DECISIONS:
            problems.append(f"merge_candidates[{i}]: decision {m.get('decision')!r}")
    return problems


def schema_verdict(obj, schema):
    """(ok, detail). Uses jsonschema when installed, and always runs the stdlib subset."""
    problems = mini_validate_graph(obj) if isinstance(obj, dict) and "nodes" in obj else []
    detail = "; ".join(problems[:3])
    ok = not problems
    try:
        import jsonschema
        try:
            jsonschema.validate(obj, schema)
            return ok, detail or "jsonschema"
        except jsonschema.ValidationError as e:
            return False, f"jsonschema: {list(e.absolute_path)[:4]} {e.message[:120]}"
    except ImportError:
        return ok, (detail + " (stdlib subset only)").strip()


def r11(work):
    print("[R11] produced artifacts satisfy schema/graph.schema.json")
    schema = jload(os.path.join(ROOT, "schema", "graph.schema.json"))

    ann = jload(os.path.join(DEMO, "annotations.example.json"))
    ok, detail = schema_verdict(ann, schema)
    check("shipped annotations.example.json is valid", ok, detail)

    shipped = jload(os.path.join(DEMO, "output", "graph.json"))
    ok, detail = schema_verdict(shipped, schema)
    check("shipped example graph.json is valid", ok, detail)

    b = os.path.join(work, "bundle.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", os.path.join(DEMO, "input"), "--out", b])
    g, q, r = pipeline(b, os.path.join(DEMO, "annotations.example.json"), work,
                       os.path.join(DEMO, "queries.example.json"))
    ok, detail = schema_verdict(g, schema)
    check("a freshly built graph is valid", ok, detail)

    broken = json.loads(json.dumps(g))
    if broken["edges"]:
        broken["edges"][0]["type"] = "banana"
    ok, _ = schema_verdict(broken, schema)
    check("a graph with an out-of-schema relation type is rejected", not ok)

    # the vocabulary exists in three places (schema, extractor, this test); drift between them is
    # how a relation silently became "other" on a real run
    schema_rel = set(schema["$defs"]["edge"]["properties"]["type"]["enum"])
    schema_node = set(schema["$defs"]["node"]["properties"]["type"]["enum"])
    sys.path.insert(0, SCRIPTS)
    import build_graph as BG
    check("relation vocabulary agrees across schema, build_graph and the test",
          schema_rel == set(BG.REL_TYPES) == EDGE_TYPES,
          (sorted(schema_rel - set(BG.REL_TYPES)), sorted(EDGE_TYPES - schema_rel)))
    check("node vocabulary agrees across schema and build_graph",
          schema_node == set(BG.NODE_TYPES), (sorted(schema_node - set(BG.NODE_TYPES)),
                                              sorted(set(BG.NODE_TYPES) - schema_node)))

    longest = max([len(m["quote"]) for n in g["nodes"] for m in n.get("mentions", [])]
                  + [len(m["quote"]) for e in g["edges"] for m in e.get("evidence", [])] + [0])
    check("no stored quote exceeds the documented 300-character limit", longest <= 300, longest)
    check("result.json repeats the graph's nodes and edges",
          len(r["nodes"]) == len(g["nodes"]) and len(r["edges"]) == len(g["edges"]),
          (len(r["nodes"]), len(g["nodes"])))


def _make_pdf(path, paragraphs, heading=None):
    """A real PDF, so the test exercises pdftotext/pypdf rather than a mock."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return False
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        body = "\n\n".join(paragraphs)
        if heading:
            body += "\n" + heading + "\n" + "\n".join(
                "Doe A. et al. Journal of Tests 2024; 1: 1-10." for _ in range(3))
        fig.text(0.06, 0.95, body, fontsize=9, va="top", wrap=True)
        pdf.savefig(fig)
        plt.close(fig)
    return True


def r12(work):
    print("[R12] a PDF becomes located paragraph blocks")
    case = os.path.join(work, "case")
    os.makedirs(case)
    paras = [
        "Perovskite solar cells with a passivated absorber reached a power conversion efficiency of "
        "21.3% under AM1.5G illumination in this work, as reported by the authors.",
        "The hole transport layer was Spiro-OMeTAD, deposited by spin coating at 3000 rpm for 30 "
        "seconds and annealed at 100 degrees for ten minutes in air.",
        "Stability was tracked for 1000 hours under continuous one-sun illumination in a nitrogen "
        "atmosphere, with minimal degradation observed over the whole period.",
    ]
    if not _make_pdf(os.path.join(case, "paper_one.pdf"), paras, heading="References"):
        print("    (matplotlib unavailable: PDF case skipped, not failed)")
        return
    b = os.path.join(work, "b.json")
    r = subprocess.run([PY, os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", case, "--out", b],
                       capture_output=True, text=True)
    if r.returncode != 0:
        check("PDF corpus normalises", False, (r.stdout + r.stderr)[-400:])
        return
    bundle = jload(b)
    ps = bundle["paragraphs"]
    check("a multi-paragraph PDF yields more than one block", len(ps) >= 3, len(ps))
    check("every block keeps a derived d#### id",
          all(re.fullmatch(r"d\d{4}", p["paragraph_id"]) and p.get("id_derived") for p in ps))
    check("a PDF page is recorded as an aid, never as the id",
          all(isinstance(p.get("pdf_page"), int) and re.fullmatch(r"d\d{4}", p["paragraph_id"])
              and p["paragraph_id"] != str(p["pdf_page"]) for p in ps),
          [(p.get("pdf_page"), p["paragraph_id"]) for p in ps])
    check("the reference list does not become body text",
          not any("Journal of Tests" in p["text"] for p in ps))
    blob = " ".join(p["text"] for p in ps)
    check("each paragraph stays one block, not a fragment per line",
          all(len(p["text"]) > 80 for p in ps), [len(p["text"]) for p in ps])


def r13(work):
    print("[R13] questions in the case task are answered from the graph")
    case = os.path.join(work, "case")
    os.makedirs(case)
    with open(os.path.join(case, "case.json"), "w", encoding="utf-8") as f:
        json.dump({"case_id": "task-questions",
                   "task": "1. Which material appears in both papers?\n"
                           "2. What does the second paper report about stability?\n"
                           "3. 两篇论文里 Spiro-OMeTAD 的效率是多少？"}, f, ensure_ascii=False)
    with open(os.path.join(case, "material.json"), "w", encoding="utf-8") as f:
        json.dump({"paragraphs": [
            {"source_id": "P1", "paragraph_id": "p1",
             "text": "Spiro-OMeTAD was used as the hole transport layer and the device reached 21.3%."},
            {"source_id": "P2", "paragraph_id": "q1",
             "text": "The same Spiro-OMeTAD layer gave 22.1%, while stability was not measured here."}]}, f)
    with open(os.path.join(case, "ann.json"), "w", encoding="utf-8") as f:
        json.dump({"nodes": [
            {"label": "Spiro-OMeTAD", "type": "material",
             "mentions": [{"source_id": "P1", "paragraph_id": "p1", "quote": "hole transport layer"}]},
            {"label": "power conversion efficiency", "type": "metric",
             "mentions": [{"source_id": "P2", "paragraph_id": "q1", "quote": "gave 22.1%"}]}],
            "edges": [{"source_label": "Spiro-OMeTAD", "target_label": "power conversion efficiency",
                       "type": "measures",
                       "evidence": [{"source_id": "P2", "paragraph_id": "q1",
                                     "quote": "The same Spiro-OMeTAD layer gave 22.1%, while "
                                               "stability was not measured here"}]}]}, f)
    b = os.path.join(work, "b.json")
    sh([os.path.join(SCRIPTS, "prepare_case.py"), "--case-dir", case, "--out", b])
    g, q, r = pipeline(b, os.path.join(case, "ann.json"), work)
    if q is None:
        check("task queries run", False)
        return
    qs = q["queries"]
    derived = [x for x in qs if (x.get("query") or {}).get("derived_from") == "task"]
    check("the task's questions become queries", len(derived) >= 2, len(derived))
    check("each derived query quotes the question it came from",
          all((x["query"].get("task_question") or "") for x in derived))
    types = {x["query"]["type"] for x in derived}
    check("a 'both papers' question routes to the alignment query", "cross_paper" in types, types)
    st = {x["qid"]: x["status"] for x in derived}
    check("at least one task question is answered from the graph",
          any(v == "answered" for v in st.values()), st)
    check("an ungrounded question is undetermined with a reason, not an error",
          all(v in ("answered", "undetermined") for v in st.values()), st)
    # keyword lookup reaches the quotes, not only the node labels
    kw = os.path.join(work, "kw.json")
    with open(kw, "w", encoding="utf-8") as f:
        json.dump({"queries": [{"qid": "K1", "type": "keyword", "keyword": "stability"}]}, f)
    qout = os.path.join(work, "kw_result.json")
    sh([os.path.join(SCRIPTS, "query_graph.py"), "--graph", os.path.join(work, "graph.json"),
        "--queries", kw, "--out", qout])
    res = jload(qout)["queries"][0]
    check("a term that never became a node is found in the quoted text",
          res["status"] == "answered" and res["n_evidence"] >= 1, res["status"])


CASES = {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6, "R7": r7, "R8": r8,
         "R9": r9, "R10": r10, "R11": r11, "R12": r12, "R13": r13}


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
