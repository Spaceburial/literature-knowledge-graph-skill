#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heuristic_extract.py — deterministic, topic-agnostic first-pass extractor (fallback path).

The high-quality path is the agent writing ``annotations.json`` from a close reading (see
SKILL.md). This script exists so the pipeline never returns an empty graph when that step is
skipped, and so a reviewer can see the deterministic baseline against which the agent's
extraction is compared.

Method
  1. sentence split (offset-preserving)
  2. cue-phrase patterns for entity type and relation type
  3. the *sentence itself* is used as the evidence quote, so every quote is exact by construction
  4. attribution tag: first-person / "this study" => self, else other
It deliberately does NOT invent numeric values; numbers stay inside the quoted sentence.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])|(?<=[;])\s+(?=[a-z])|(?<=[。！？；])")

CHEM = re.compile(r"\b(?:[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*){1,}|[A-Z][a-z]?[A-Z][a-z]?\d*|"
                  r"[A-Z][a-z]+(?:O|N|S|P|C)\d?)\b")

METRIC_LEX = ["power conversion efficiency", "PCE", "efficiency", "fill factor", "open-circuit voltage",
              "short-circuit current", "Voc", "Jsc", "stability", "lifetime", "accuracy", "F1",
              "BLEU", "yield", "conductivity", "mobility", "capacity", "retention", "precision",
              "recall", "AUC", "MAE", "RMSE", "R2", "bandgap", "transmittance"]

METHOD_LEX = ["spin-coating", "spin coating", "annealing", "thermal annealing", "CVD", "PVD", "ALD",
              "sputtering", "doctor blading", "inkjet printing", "XRD", "SEM", "TEM", "AFM", "XPS",
              "UV-vis", "PL", "NMR", "DFT", "molecular dynamics", "finite element", "sol-gel",
              "dip-coating", "electrospinning", "lithography", "etching", "doping", "passivation",
              "RAG", "retrieval-augmented generation", "fine-tuning", "pretraining", "masked language modeling",
              "self-attention", "attention mechanism", "transformer", "CNN", "LSTM", "GNN",
              "random forest", "gradient boosting", "SVM", "regression"]

TASK_LEX = ["photovoltaic", "solar cell", "electrocatalysis", "water splitting", "CO2 reduction",
            "machine translation", "text classification", "question answering", "summarization",
            "image classification", "object detection", "segmentation", "drug discovery",
            "battery", "supercapacitor", "sensing", "catalysis", "hydrogen evolution",
            "knowledge graph construction", "information extraction", "relation extraction"]

# Surface variants that denote the SAME metric concept (abbreviation <-> full form).
# Only metric synonyms are grouped by default; material/model names are NOT grouped because
# the same generic name can denote different physical samples (see SKILL.md merge rules).
ALIAS_GROUPS = [
    {"pce", "power conversion efficiency"},
    {"ff", "fill factor"},
    {"voc", "open-circuit voltage", "open circuit voltage"},
    {"jsc", "short-circuit current", "short circuit current"},
]


def group_label(surface):
    """Return (preferred_label, surface) if the surface belongs to a known synonym group."""
    c = canon(surface)
    for grp in ALIAS_GROUPS:
        if c in grp:
            preferred = max(sorted(grp), key=len)
            return preferred, surface
    return None, surface

USE_CUES = [r"\busing\b", r"\bvia\b", r"\bby means of\b", r"\bemploy(?:ing|s|ed)?\b",
            r"\bbased on\b", r"\bprepared (?:by|with)\b", r"\bthrough\b"]
COMPARE_CUES = [r"\bcompared (?:with|to)\b", r"\bversus\b", r"\bvs\.?\b", r"\bin contrast to\b"]
OUTPERF_CUES = [r"\boutperform", r"\bexceed", r"\bhigher than\b", r"\bbetter than\b",
                r"\bsuperior to\b", r"\bimprove[ds]?\b", r"\benhance[ds]?\b"]
SUPPORT_CUES = [r"\bsupport", r"\bconsistent with\b", r"\bconfirm", r"\bin agreement with\b",
                r"\bindicat"]
CONTRA_CUES = [r"\bcontradict", r"\binconsistent with\b", r"\bconflict", r"\bdisagree"]
REPORT_CUES = [r"\bachiev", r"\breach", r"\breport", r"\bdemonstrat", r"\bshow", r"\byield"]
SELF_CUES = [r"\bwe\b", r"\bour\b", r"\bthis (?:study|work|paper)\b", r"\bherein\b", r"\bhere\b"]
OTHER_CUES = [r"\bet al\b", r"\bprevious(?:ly)?\b", r"\bprior\b", r"\breported by\b", r"\bref\.", r"\b文献"]


def norm_ws(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def canon(s):
    s = (s or "").lower().replace("-", " ")
    s = re.sub(r"[^\w\u4e00-\u9fff \+\.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sentences(text):
    out, start = [], 0
    for m in SENT_SPLIT.finditer(text):
        seg = text[start:m.start()]
        if norm_ws(seg):
            out.append((start, m.start(), norm_ws(seg)))
        start = m.end()
    if start < len(text):
        seg = text[start:]
        if norm_ws(seg):
            out.append((start, len(text), norm_ws(seg)))
    return out


def attribution(sent):
    s = sent.lower()
    if any(re.search(c, s) for c in OTHER_CUES):
        # "we ... reported by others" -> other only if no first person
        if not any(re.search(c, s) for c in SELF_CUES):
            return "other"
    if any(re.search(c, s) for c in SELF_CUES):
        return "self"
    return "other"


def find_lexicon(sent, lex):
    s = sent.lower()
    hits = []
    for term in lex:
        for m in re.finditer(r"\b" + re.escape(term.lower()) + r"\b", s):
            hits.append(sent[m.start():m.end()])
    # longest unique, preserve case from source
    uniq = {}
    for h in hits:
        uniq[canon(h)] = h
    return list(uniq.values())


def find_chem(sent):
    return [m.group(0) for m in CHEM.finditer(sent)
            if len(m.group(0)) >= 3 and re.search(r"\d", m.group(0))]


CJK = re.compile(r"[\u4e00-\u9fff]")
CJK_CAND = re.compile(r"[\u4e00-\u9fff]{2,12}")
CJK_STOP = ("的", "了", "和", "与", "在", "是", "为", "对", "从", "将", "并", "而", "其", "这", "那",
            "我们", "本文", "表明", "显示", "结果", "可以", "进行", "通过", "以及", "其中")


def has_cjk(text):
    return bool(CJK.search(text or ""))


def find_cjk_np(sent):
    """Punctuation-delimited CJK runs, filtered to content-looking phrases."""
    out, seen = [], set()
    for chunk in re.split(r"[，,。.;；:：、（）()《》\s]+", sent):
        for m in CJK_CAND.finditer(chunk):
            t = m.group(0)
            if any(t.startswith(w) or t == w for w in CJK_STOP):
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
    return out[:6]


# Suffix-based typing for candidates that no lexicon matched. A capitalised phrase with no type is
# not an entity of unknown kind, it is usually noise (a sentence-initial word, a verb phrase, a
# heading). Typing them, and dropping the ones that stay untyped and occur once, is what keeps the
# deterministic fallback from producing a graph of anonymous `other` nodes.
TYPE_RULES = [
    ("metric", r"efficienc|stabilit|voltage|current|\bfactor\b|density|mobilit|conductivit|lifetime|"
               r"retention|accura|precision|recall|\berror\b|\byield\b|bandgap|transmittance|"
               r"capacity|\bpce\b|\bff\b|\bvoc\b|\bjsc\b|\brmse\b|\bmae\b|\br2\b"),
    ("material", r"layer|film\b|oxide|perovskite|polym|organic framework|\bcofs?\b|crystal|nanoparticle|"
                 r"-based\b|pb-i|"
                 r"electrode|absorber|molecule|\bsalt\b|solvent|cation|anion|additive|\bmapbi|\bfama\b|"
                 r"\bcspbi|\bpbi\b|polymer|composite|\bgraphene\b|\bmo\w*\b(?=\s)"),
    ("method", r"method|model|framework|algorithm|network|approach|technique|analysis|spectroscop|"
               r"microscop|diffraction|inference|learning|regression|classifier|\bcvd\b|\bald\b|"
               r"coating|annealing|sputtering|passivation|simulation"),
    ("researcher", r"et al\.|^[A-Z][a-z]+ (and|&) [A-Z][a-z]+$"),
    ("metric", r"效率|稳定性|电压|电流|因子|寿命|迁移率|电导率|精度|产率|容量"),
    ("material", r"膜|层$|氧化物|钙钛矿|材料|分子|电极|晶体|聚合物|添加剂|溶剂|复合"),
    ("method", r"方法|模型|算法|网络|光谱|衍射|显微|退火|旋涂|钝化|沉积|模拟|学习"),
]


DISCOURSE = {"among", "importantly", "under", "such", "however", "therefore", "here", "this",
             "these", "those", "both", "each", "recent", "finally", "moreover", "thus", "hence",
             "since", "while", "when", "after", "before", "because", "although", "notably",
             "overall", "consequently", "furthermore", "additionally", "typically", "generally",
             "interestingly", "first", "second", "third", "next", "then", "also", "yet", "still",
             "their", "despite", "even", "similarly", "accordingly", "report", "reports", "figure",
             "fig", "table", "scheme", "section", "result", "results", "study", "studies", "work",
             "paper", "papers", "article", "articles", "herein", "thereby", "whereas", "whose",
             "which", "what", "when", "where", "why", "how", "our", "its", "his", "her"}
ACRONYM = {
    "task": {"psc", "pscs", "pv", "opv", "ds sc", "dssc"},
    "metric": {"pce", "pces", "ff", "voc", "jsc", "eqe", "iqe", "plqy", "rmse", "mae", "r2",
               "t80", "vbi", "jv"},
}


def infer_type(label):
    """Type a candidate from its surface. Cheap, deterministic, and right more often than 'other'."""
    raw = (label or "").strip()
    low = raw.lower()
    bare = low.rstrip("s") if len(low) > 3 else low
    if bare in ACRONYM["task"] or low in ACRONYM["task"]:
        return "task"
    if bare in ACRONYM["metric"] or low in ACRONYM["metric"]:
        return "metric"
    if low in {m.lower() for m in METRIC_LEX}:
        return "metric"
    if low in {m.lower() for m in METHOD_LEX}:
        return "method"
    if low in {m.lower() for m in TASK_LEX}:
        return "task"
    for ntype, pattern in TYPE_RULES:
        if re.search(pattern, low):
            return ntype
    return "other"


def find_np(sent):
    """Capitalised multi-word noun phrases (2-4 tokens), not sentence-initial single words."""
    out = []
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+){0,2})\b", sent):
        t = m.group(1)
        if any(ch.isdigit() for ch in t) and not re.match(r"^[A-Z][a-z]?\d", t):
            continue
        if " " not in t and t.lower() in DISCOURSE:
            continue
        if t.lower() in ("the", "this", "these", "we", "however", "therefore"):
            continue
        if len(t) >= 4:
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="/app/work/case_bundle.json")
    ap.add_argument("--out", default="/app/work/annotations.json")
    ap.add_argument("--max-nodes", type=int, default=140)
    ap.add_argument("--max-edges", type=int, default=160)
    args = ap.parse_args()

    b = json.load(open(args.bundle, encoding="utf-8"))
    paras = b.get("paragraphs", [])
    nodes = {}
    edges = []
    edge_seen = set()

    def add_node(label, ntype, sid, pid, quote, attr):
        preferred, surface = group_label(label)
        if preferred:
            label = preferred
        k = canon(label)
        if not k or len(k) < 2:
            return None
        if k not in nodes:
            if len(nodes) >= args.max_nodes:
                return None
            nodes[k] = {"label": label, "type": ntype, "aliases": [], "mentions": []}
        if surface and canon(surface) != k:
            nodes[k]["aliases"] = sorted(set(nodes[k]["aliases"]) | {surface})
        nodes[k]["mentions"].append({"source_id": sid, "paragraph_id": pid, "quote": quote,
                                     "attribution": attr})
        return k

    def add_edge(sl, tl, rtype, sid, pid, quote, attr):
        sk, tk = canon(sl), canon(tl)
        if not sk or not tk or sk == tk:
            return
        key = (sk, tk, rtype, pid, sid)
        if key in edge_seen or len(edges) >= args.max_edges:
            return
        edge_seen.add(key)
        edges.append({"source_label": sl, "target_label": tl, "type": rtype,
                      "condition": "", "evidence": [{"source_id": sid, "paragraph_id": pid,
                                                     "quote": quote, "attribution": attr}]})

    for p in paras:
        sid, pid, text = p["source_id"], p["paragraph_id"], p["text"]
        for _a, _b, sent in sentences(text):
            attr = attribution(sent)
            # --- entities in this sentence ---
            ents = []  # (label, type)
            for c in find_chem(sent):
                ents.append((c, "material"))
            for m in find_lexicon(sent, METRIC_LEX):
                ents.append((m, "metric"))
            for m in find_lexicon(sent, METHOD_LEX):
                ents.append((m, "method"))
            for m in find_lexicon(sent, TASK_LEX):
                ents.append((m, "task"))
            for m in re.finditer(r"\b([A-Z][a-z]+ et al\.)", sent):
                ents.append((m.group(1), "researcher"))
            for np in find_np(sent)[:4]:
                if re.search(r"\d", np):
                    continue
                ents.append((np, infer_type(np)))
            if has_cjk(sent):
                for np in find_cjk_np(sent)[:4]:
                    ents.append((np, infer_type(np)))
            # dedup by canonical
            ded, seen = [], set()
            for lbl, t in ents:
                if canon(lbl) in seen:
                    continue
                seen.add(canon(lbl))
                ded.append((lbl, t))
                add_node(lbl, t, sid, pid, sent, attr)

            labels = [d[0] for d in ded]
            if len(labels) < 2:
                continue
            a, bb = labels[0], labels[1]

            # An edge between two untyped phrases is a co-occurrence, not a relation. Requiring one
            # typed endpoint keeps the fallback's edge set honest about what it actually knows.
            if all(t == "other" for _, t in ded[:2]):
                continue
            s = sent.lower()
            if any(re.search(c, s) for c in CONTRA_CUES):
                add_edge(a, bb, "contradicts", sid, pid, sent, attr)
            elif any(re.search(c, s) for c in OUTPERF_CUES):
                add_edge(a, bb, "outperforms", sid, pid, sent, attr)
            elif any(re.search(c, s) for c in COMPARE_CUES):
                add_edge(a, bb, "compares", sid, pid, sent, attr)
            elif any(re.search(c, s) for c in SUPPORT_CUES):
                add_edge(a, bb, "supports", sid, pid, sent, attr)
            elif any(re.search(c, s) for c in USE_CUES):
                add_edge(a, bb, "uses", sid, pid, sent, attr)
            elif any(re.search(c, s) for c in REPORT_CUES):
                add_edge(a, bb, "reports", sid, pid, sent, attr)

    # drop untyped candidates seen once: kept, they would dominate the graph with anonymous nodes
    keep = {k for k, v in nodes.items() if v["type"] != "other" or len(v["mentions"]) >= 2}
    dropped_other = len(nodes) - len(keep)
    nodes = {k: v for k, v in nodes.items() if k in keep}
    edges = [e for e in edges
             if canon(e["source_label"]) in keep and canon(e["target_label"]) in keep]

    ann = {"nodes": list(nodes.values()), "edges": edges,
           "merge_candidates": [], "source_conflicts": [],
           "extractor": "heuristic_extract.py (deterministic fallback)",
           "dropped_untyped_singletons": dropped_other,
           "note": "First-pass baseline. The agent-quality path is a close reading that writes "
                   "this file directly; see SKILL.md."}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(ann, f, ensure_ascii=False, indent=1)
    print(f"[heuristic_extract] {len(ann['nodes'])} candidate nodes, {len(edges)} candidate edges -> {args.out}")


if __name__ == "__main__":
    main()
