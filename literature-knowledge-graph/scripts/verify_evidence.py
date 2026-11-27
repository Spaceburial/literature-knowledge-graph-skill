#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_evidence.py — the evidence-binding gate.

Every node and edge in the graph must point to a real paragraph and carry a short original
quote. This module is the only place allowed to declare a quote "verified". It is deliberately
conservative: a quote that cannot be located in the cited paragraph is reported as
``not_found`` and the build step downgrades or rejects it.

Match levels (returned as ``status``):
  exact      — quote is a substring of the paragraph as stored (whitespace folded)
  normalized — matches after Unicode/quote/dash folding, case folding, and after ignoring
               whitespace and thousands separators (``1,350`` = ``1350``, ``80.1%`` = ``80.1 %``)
  fuzzy      — >=0.90 token-sequence similarity against a sliding window (flagged, weaker)
  not_found  — no acceptable match

Whitespace and thousands separators are the two formatting differences a reader never counts as
a different quote: a model transcribing ``1,350 °C`` or ``88.1 %`` from a paper that prints
``1350 °C`` and ``88.1%`` is still quoting the paper. Both are dropped when building the
comparison key, on the quote and on the paragraph alike; digits themselves are never altered, so
a changed number still fails the numeric check below.

The ``span`` field gives character offsets in the paragraph text and the ``context`` field
returns the surrounding original sentence, which is what the reader actually needs to re-check.
"""
import difflib
import re
import unicodedata
from collections import Counter

NUM_RE = re.compile(r"\d+(?:\.\d+)?")

FOLD_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ",
    "\u2009": " ", "\u200a": " ", "\u200b": "", "\ufeff": "",
}


def fold(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    for a, b in FOLD_MAP.items():
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _find_span(hay, needle):
    i = hay.find(needle)
    if i < 0:
        return None
    return (i, i + len(needle))


def _key(text):
    """Comparison key: drop whitespace and thousands separators, keep every other character.

    Returns ``(key, src)`` where ``src[i]`` is the offset in ``text`` of ``key[i]``, so a match
    found in the key can still be reported as a span of the paragraph. A comma is a thousands
    separator only when a digit precedes it and exactly three digits follow it.
    """
    key, src = [], []
    n = len(text)
    for i, ch in enumerate(text):
        if ch == "," and key and key[-1].isdigit():
            group = text[i + 1:i + 4]
            after = text[i + 4:i + 5]
            if len(group) == 3 and group.isdigit() and not after.isdigit():
                continue
        if ch.isspace():
            continue
        key.append(ch)
        src.append(i)
    return "".join(key), src


def numbers(text):
    """Multiset of numeric tokens, with digit grouping ignored (``1,350`` counts as ``1350``)."""
    return Counter(NUM_RE.findall(_key(text)[0]))


def _sentence_bounds(text, span):
    if not span:
        return (0, min(len(text), 240))
    a, b = span
    left = max(text.rfind(". ", 0, a), text.rfind("; ", 0, a))
    left = 0 if left < 0 else left + 2
    right_candidates = [x for x in (text.find(". ", b), text.find("; ", b), text.find("\n", b)) if x >= 0]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    # keep context bounded
    if right - left > 400:
        right = min(len(text), left + 400)
    return (left, right)


def verify_quote(quote, paragraph_text, min_len=12, fuzzy_threshold=0.90):
    """Return dict(status, score, span, context, note)."""
    q = fold(quote)
    hay = fold(paragraph_text)
    if not q:
        return {"status": "not_found", "score": 0.0, "span": None, "context": "", "note": "empty quote"}
    if len(q) < min_len:
        # short quotes are common for names; accept exact but mark as short
        if q in hay:
            return {"status": "exact", "score": 1.0, "span": _find_span(hay, q),
                    "context": paragraph_text[:_sentence_bounds(paragraph_text, None)[1]], "note": "short quote"}
        return {"status": "not_found", "score": 0.0, "span": None, "context": "", "note": "short quote not found"}

    span = _find_span(hay, q)
    if span:
        status = "exact" if quote in paragraph_text else "normalized"
        ctx = paragraph_text[_sentence_bounds(paragraph_text, span)[0]:_sentence_bounds(paragraph_text, span)[1]]
        return {"status": status, "score": 1.0, "span": span, "context": ctx, "note": ""}

    # Same text, different formatting: whitespace and thousands separators are dropped from both
    # sides, every other character must still agree, so this stays a "normalized" match and never
    # becomes a semantic one. Without this tier a quote that only writes "1,350" for "1350" falls
    # through to the fuzzy window, where the numeric check rejects it — a correct quote lost.
    qkey, _ = _key(q)
    hkey, hsrc = _key(hay)
    pos = hkey.find(qkey) if qkey else -1
    if pos >= 0:
        span = (hsrc[pos], hsrc[pos + len(qkey) - 1] + 1)
        a, b = _sentence_bounds(paragraph_text, span)
        return {"status": "normalized", "score": 1.0, "span": span, "context": paragraph_text[a:b],
                "note": "formatting-insensitive: whitespace and thousands separators ignored"}

    # fuzzy: slide a window the length of the quote over sentences
    best = 0.0
    best_span = None
    win = max(len(q), 40)
    step = max(1, win // 4)
    for start in range(0, max(1, len(hay) - win + 1), step):
        cand = hay[start:start + win]
        r = difflib.SequenceMatcher(None, q, cand).ratio()
        if r > best:
            best = r
            best_span = (start, start + win)
    if best >= fuzzy_threshold:
        # A paraphrase may reorder words; it may not change a number. One edited digit in a
        # 200-character sentence still scores >0.90, so similarity alone would certify a quote
        # the paper never makes. Numbers must agree exactly, or the quote is rejected.
        window = hay[best_span[0]:best_span[1]]
        qn, wn = numbers(q), numbers(window)
        if qn != wn:
            changed = sorted((qn - wn).elements())
            found = sorted((wn - qn).elements())
            return {"status": "not_found", "score": round(best, 3), "span": None, "context": "",
                    "note": f"numeric mismatch in a {best:.2f}-similar window: "
                            f"quote has {changed or '-'}, paragraph has {found or '-'}"}
        a, b = _sentence_bounds(paragraph_text, best_span)
        # The submitted quote is not verbatim here, so hand back the paragraph's own words at the
        # matched span; a reviewer must be able to see the difference.
        return {"status": "fuzzy", "score": round(best, 3), "span": best_span,
                "matched": window, "context": paragraph_text[a:b],
                "note": "fuzzy match; treat as weak evidence, the quote is not verbatim"}
    return {"status": "not_found", "score": round(best, 3), "span": None, "context": "",
            "note": f"best fuzzy {best:.2f} < {fuzzy_threshold}"}


def is_acceptable(result):
    return result["status"] in ("exact", "normalized", "fuzzy")


def evidence_strength_from(verify_status, attribution):
    """Map verification + attribution onto a coarse, auditable strength label."""
    if verify_status == "fuzzy":
        return "weak"
    if attribution == "other":
        return "reported"          # author cites someone else's result
    return "direct" if verify_status in ("exact", "normalized") else "weak"


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 4:
        print('usage: verify_evidence.py "<quote>" "<paragraph text>" [json paragraphs file]')
        sys.exit(1)
    q, p = sys.argv[1], sys.argv[2]
    print(json.dumps(verify_quote(q, p), ensure_ascii=False, indent=1))
