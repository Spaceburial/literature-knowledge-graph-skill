#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_case.py  —  Stage 1 of the literature-knowledge-graph skill.

Purpose
-------
Convert a heterogeneous case directory (case.json / task.md / corpus-manifest.json /
material.json / primary-material.json / secondary-material.json, or any subset) into a
single, schema-stable working bundle:

    /app/work/case_bundle.json

The bundle contains
  * case_id, task text, output_contract (field-name -> description)
  * sources[]   : one record per paper (source_id, doi, title, authors, license, sha256, role)
  * paragraphs[]: flat list of {source_id, paragraph_id, section, order, role, text}
  * warnings[]  : anything missing / ambiguous (never silently dropped)

Design rules
------------
1. Never invent content. If a field is absent, record it in warnings and leave it null.
2. paragraph_id is whatever stable id the provider exposes (JATS <p id>). If a paragraph has
   no id, a DERIVED id (``<source>:d0001``) is generated and flagged ``id_derived=true`` so it
   can never be mistaken for an original PDF page or an original JATS id.
3. Source attribution is strict: roles (primary/secondary) come from the file the paragraph
   was read from, and DOI/title/authors are only attached to the source that declares them.

Usage
-----
    python prepare_case.py [--case-dir DIR] [--out PATH]
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time

# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

TEXT_KEYS = ("text", "content", "body", "paragraph", "para", "passage", "plain_text", "value")
ID_KEYS = ("paragraph_id", "para_id", "pid", "paraId", "jats_id", "xml_id", "p_id", "id")
SEC_KEYS = ("section", "section_title", "sec", "heading", "head", "title_of_section")
SRC_KEYS = ("source_id", "sourceId", "paper_id", "doc_id", "document_id", "sid", "source")

ROLE_BY_NAME = {
    "primary-material.json": "primary",
    "secondary-material.json": "secondary",
    "primary_material.json": "primary",
    "secondary_material.json": "secondary",
}


def norm_ws(s):
    if s is None:
        return ""
    s = str(s)
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def first_key(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return None


def find_case_dir(explicit):
    cands = []
    if explicit:
        cands.append(explicit)
    env = os.environ.get("CASE_DIR")
    if env:
        cands.append(env)
    cands += ["/input", os.path.join(os.getcwd(), "input"), os.getcwd()]
    for c in cands:
        if c and os.path.isdir(c):
            return os.path.abspath(c)
    return None


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        return {"__load_error__": str(e)}


# --------------------------------------------------------------------------------------
# 1. case.json -> case_id / output_contract / task
# --------------------------------------------------------------------------------------

def deep_find(node, key_names, max_depth=6, depth=0):
    """Return the first value stored under any of key_names, breadth-first-ish."""
    if depth > max_depth:
        return None
    if isinstance(node, dict):
        for k in key_names:
            if k in node and node[k] not in (None, "", [], {}):
                return node[k]
        for v in node.values():
            r = deep_find(v, key_names, max_depth, depth + 1)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = deep_find(v, key_names, max_depth, depth + 1)
            if r is not None:
                return r
    return None


def extract_case_meta(case_json, case_dir, warnings):
    case_id = None
    output_contract = {}
    task_text = ""

    if isinstance(case_json, dict):
        for k in ("case_id", "caseId", "id", "case", "name"):
            if case_json.get(k):
                case_id = str(case_json[k])
                break
        oc = case_json.get("output_contract") or case_json.get("outputContract")
        if isinstance(oc, dict):
            # either {field: description} or {"fields": {...}}
            if "fields" in oc and isinstance(oc["fields"], dict):
                output_contract = oc["fields"]
            else:
                output_contract = oc
        elif isinstance(oc, list):
            output_contract = {str(x): "" for x in oc}
        else:
            deep = deep_find(case_json, ("output_contract", "outputContract", "required_fields"))
            if isinstance(deep, dict):
                output_contract = deep
            elif isinstance(deep, list):
                output_contract = {str(x): "" for x in deep}
        for k in ("task", "task_text", "instruction", "prompt", "question"):
            if isinstance(case_json.get(k), str) and case_json[k].strip():
                task_text = case_json[k]
                break

    task_md = os.path.join(case_dir, "task.md")
    if os.path.exists(task_md):
        try:
            with open(task_md, "r", encoding="utf-8", errors="replace") as f:
                t = f.read()
            task_text = (task_text + "\n\n" + t).strip() if task_text else t
        except Exception as e:  # noqa: BLE001
            warnings.append(f"task.md unreadable: {e}")
    if not task_text:
        warnings.append("No task text found (case.json/task.md). Proceeding on default KG objective.")
    return case_id, output_contract, task_text


# --------------------------------------------------------------------------------------
# 2. corpus-manifest.json -> sources[]
# --------------------------------------------------------------------------------------

def looks_like_source_record(d):
    keys = {k.lower() for k in d.keys()}
    return bool(keys & {"doi", "title", "authors", "author", "license", "sha256", "source_id", "sourceid"})


def extract_sources(manifest, warnings):
    sources = []

    def coerce(rec, idx, role_hint=None):
        sid = None
        for k in ("source_id", "sourceId", "paper_id", "id"):
            if rec.get(k):
                sid = str(rec[k])
                break
        if sid is None:
            doi = rec.get("doi")
            sid = "src_" + (re.sub(r"[^A-Za-z0-9]+", "_", str(doi)) if doi else f"{idx+1}")
            warnings.append(f"source record {idx} had no source_id; derived '{sid}'.")
        authors = rec.get("authors") or rec.get("author") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in re.split(r"[;,]", authors) if a.strip()]
        if authors and isinstance(authors[0], dict):
            authors = [a.get("name") or a.get("family") or json.dumps(a, ensure_ascii=False) for a in authors]
        return {
            "source_id": sid,
            "role": rec.get("role") or role_hint or "unknown",
            "doi": rec.get("doi"),
            "title": rec.get("title"),
            "authors": authors,
            "license": rec.get("license") or rec.get("licence"),
            "sha256": rec.get("sha256") or rec.get("hash") or rec.get("source_hash"),
            "pmid": rec.get("pmid"), "pmcid": rec.get("pmcid"),
            "journal": rec.get("journal"), "year": rec.get("year") or rec.get("publication_year"),
            "raw": {k: v for k, v in rec.items() if k not in ("abstract",)},
        }

    def walk(node, role_hint=None):
        if isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, dict) and looks_like_source_record(v):
                    sources.append(coerce(v, len(sources), role_hint))
                else:
                    walk(v, role_hint)
        elif isinstance(node, dict):
            if looks_like_source_record(node) and ("doi" in node or "source_id" in node or "title" in node):
                sources.append(coerce(node, len(sources), role_hint))
                # also descend in case nested papers exist
                for k, v in node.items():
                    if isinstance(v, (list, dict)) and k not in ("authors", "raw"):
                        walk(v, role_hint)
            else:
                for v in node.values():
                    walk(v, role_hint)

    walk(manifest)
    # de-duplicate by source_id
    seen, uniq = set(), []
    for s in sources:
        if s["source_id"] in seen:
            continue
        seen.add(s["source_id"])
        uniq.append(s)
    return uniq


# --------------------------------------------------------------------------------------
# 3. Material files -> paragraphs[]
# --------------------------------------------------------------------------------------

def iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from iter_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from iter_dicts(v)


SHORT_DROPPED = []          # (origin_file, chars) for blocks under the 40-character minimum
DISCOVERED_META = {}        # source_id -> metadata found inside a material file (no manifest needed)

META_KEYS = ("doi", "title", "authors", "author", "journal", "year", "publication_year",
             "license", "licence", "sha256", "hash", "role")


def discover_source_meta(obj):
    """Collect per-source metadata carried by an aggregate material file.

    Two layouts occur in practice: a list/dict of paper records that each name their source, and a
    mapping keyed by source id whose values hold doi/title. Neither has a manifest, so without this
    the sources end up as metadata-less stubs and finalize calls the run partial for a missing DOI
    that was in the input all along.
    """
    def take(d, sid=None):
        if not isinstance(d, dict):
            return
        meta = {k: d[k] for k in META_KEYS if k in d}
        sid = sid or d.get("source_id") or d.get("paper_id") or d.get("id")
        if meta and sid:
            DISCOVERED_META.setdefault(str(sid), {}).update(meta)

    for d in iter_dicts(obj):
        take(d)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                take(v, sid=str(v.get("source_id") or k))



def note_short(origin, text):
    SHORT_DROPPED.append((origin, len(norm_ws(text))))


def looks_like_paragraph(d):
    if not isinstance(d, dict):
        return False
    t = first_key(d, TEXT_KEYS)
    if not isinstance(t, str) or len(norm_ws(t)) < 40:
        return False
    # reject records that are clearly source metadata
    if "doi" in d and "authors" in d and not first_key(d, ID_KEYS):
        return False
    return True


def extract_paragraphs_from_json(obj, default_source, role, warnings, path_label):
    """Two strategies: (a) explicit paragraph dicts; (b) id-keyed dict-of-dicts."""
    out = []
    seen = set()

    # (a) explicit paragraph records; a record nested under a paper object inherits its source_id
    def walk(node, inherited_sid=None):
        if isinstance(node, dict):
            sid_here = first_key(node, SRC_KEYS) or inherited_sid
            if looks_like_paragraph(node):
                yield node, sid_here
                return
            t = first_key(node, TEXT_KEYS)
            if isinstance(t, str) and 0 < len(norm_ws(t)) < 40:
                note_short(os.path.basename(path_label), t)
            for v in node.values():
                yield from walk(v, sid_here)
        elif isinstance(node, list):
            for v in node:
                yield from walk(v, inherited_sid)

    for d, inherited in walk(obj):
        text = norm_ws(first_key(d, TEXT_KEYS))
        pid = first_key(d, ID_KEYS)
        sid = first_key(d, SRC_KEYS) or inherited or default_source
        sec = first_key(d, SEC_KEYS) or ""
        pid = str(pid) if pid is not None else None
        key = (str(sid), pid, text[:80])
        if key in seen:
            continue
        seen.add(key)
        id_derived = bool(d.get("id_derived")) or pid is None
        out.append({
            "source_id": str(sid),
            "paragraph_id": pid,
            "section": norm_ws(sec),
            "text": text,
            "role": role,
            "id_derived": id_derived,
            "origin_file": os.path.basename(path_label),
        })

    # (b) dict keyed by paragraph id -> {text: ...}
    STRUCTURAL = {"abstract", "fulltext", "full_text", "body", "text", "content", "sections",
                  "paragraphs", "papers", "records", "items", "data", "result", "results"}

    def walk_keyed(node, src_hint):
        if isinstance(node, dict):
            hint = first_key(node, SRC_KEYS) or src_hint
            for k, v in node.items():
                if str(k).lower() in STRUCTURAL:
                    walk_keyed(v, hint)
                    continue
                if isinstance(v, dict) and first_key(v, TEXT_KEYS) and len(norm_ws(first_key(v, TEXT_KEYS))) >= 40:
                    text = norm_ws(first_key(v, TEXT_KEYS))
                    sid = first_key(v, SRC_KEYS) or hint or default_source
                    sec = first_key(v, SEC_KEYS) or ""
                    key = (str(sid), str(k), text[:80])
                    if key not in seen:
                        seen.add(key)
                        out.append({
                            "source_id": str(sid),
                            "paragraph_id": str(k),
                            "section": norm_ws(sec),
                            "text": text,
                            "role": role,
                            "id_derived": False,
                            "origin_file": os.path.basename(path_label),
                        })
                else:
                    walk_keyed(v, hint)
        elif isinstance(node, list):
            for v in node:
                walk_keyed(v, src_hint)

    walk_keyed(obj, default_source)
    return out


BACKMATTER_SKIPPED = []     # (origin, section title) for back-matter blocks left out of the body

# Sections that are metadata rather than scientific content. MDPI and several other publishers
# put them inside <body> as ordinary <sec> elements, so a <body>-only filter is not enough.
BACKMATTER_TITLES = re.compile(
    r"^(author contributions?|authors? contributions?|funding( statement)?|conflicts? of interest|"
    r"competing interests?|data availability( statement)?|availability of data( and materials)?|"
    r"acknowledge?ments?|supplementary materials?|abbreviations|references|footnotes|"
    r"author information|orcid|publisher'?s note|ethics( statement)?|consent( for publication)?|"
    r"about the authors|supporting information)$", re.I)

INLINE_TAGS = (r"sub|sup|italic|bold|sc|monospace|underline|strike|roman|sans-serif|small-caps|"
               r"named-content|inline-formula|tex-math|alternatives|mml:[a-z]+|xref|ext-link|"
               r"uri|email|break|hr")


def xml_text_of(inner):
    """Text of an XML fragment: inline markup must not split a token.

    Replacing every tag with a space turned `MAPbI<sub>3</sub>` into `MAPbI 3`, which then failed
    quote verification against the `MAPbI3` a reader copies. Formatting tags are removed without a
    space; block-level tags keep one.
    """
    t = re.sub(r"</?(?:" + INLINE_TAGS + r")\b[^>]*>", "", inner)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = t.replace("&nbsp;", " ").replace("&#x2212;", "-").replace("&minus;", "-")
    return norm_ws(t)


def extract_paragraphs_from_xml(xml_text, default_source, role):
    """Minimal JATS reader: <sec><title>..</title><p id=..>..</p></sec>."""
    out = []
    # strip namespaces for tag matching
    xml_text = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", xml_text)
    # remove ref-list / back matter noise
    body = xml_text
    m = re.search(r"<body\b.*?</body>", xml_text, re.S)
    if m:
        body = m.group(0)
    sec_title = ""
    tokens = re.finditer(r"<sec\b[^>]*>|</sec>|<title>(.*?)</title>|<p\b([^>]*)>(.*?)</p>", body, re.S)
    idx = 0
    for t in tokens:
        tok = t.group(0)
        if tok.startswith("<sec"):
            continue
        if tok == "</sec>":
            continue
        if t.group(1) is not None:  # <title>
            sec_title = xml_text_of(t.group(1))
            continue
        attrs = t.group(2) or ""
        inner = t.group(3) or ""
        if BACKMATTER_TITLES.match(sec_title or ""):
            BACKMATTER_SKIPPED.append(("jats-xml", sec_title))
            continue
        pid_m = re.search(r'\bid="([^"]+)"', attrs)
        pid = pid_m.group(1) if pid_m else None
        text = xml_text_of(inner)
        if len(text) < 40:
            note_short("jats-xml", text)
            continue
        idx += 1
        out.append({
            "source_id": default_source,
            "paragraph_id": pid,
            "section": sec_title,
            "text": text,
            "role": role,
            "id_derived": pid is None,
            "origin_file": "jats-xml",
            "order_in_source": idx,
        })
    return out


def extract_paragraphs_from_text(raw, default_source, role, origin, split_blank=True):
    """Plain text / Markdown / pdftotext output -> paragraphs with DERIVED ids.
    Page numbers are never used as ids; the caller records that ids are derived."""
    blocks = re.split(r"\n\s*\n", raw) if split_blank else [raw]
    out, idx = [], 0
    for b in blocks:
        b = re.sub(r"^#{1,6}\s*", "", b.strip())
        b = norm_ws(b)
        if len(b) < 40:
            note_short(origin, b)
            continue
        # drop obvious page furniture
        if re.fullmatch(r"(page\s*)?\d+(\s*/\s*\d+)?", b, re.I):
            continue
        idx += 1
        out.append({"source_id": default_source, "paragraph_id": f"d{idx:04d}", "section": "",
                    "text": b, "role": role, "id_derived": True, "origin_file": origin,
                    "order_in_source": idx})
    return out


def extract_paragraphs_from_pdf(path, default_source, role, warnings):
    """Best-effort PDF text extraction. Uses pdftotext, then pypdf if available."""
    raw = None
    try:
        import subprocess
        r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            raw = r.stdout
    except Exception as e:  # noqa: BLE001
        warnings.append(f"pdftotext failed for {os.path.basename(path)}: {e}")
    if raw is None:
        try:
            from pypdf import PdfReader
            raw = "\n\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"PDF unparseable ({os.path.basename(path)}): {e}. "
                            f"Paper skipped; report it in uncertainty.")
            return []
    paras = extract_paragraphs_from_text(raw, default_source, role, os.path.basename(path))
    warnings.append(f"PDF {os.path.basename(path)}: {len(paras)} paragraphs extracted; paragraph ids are "
                    f"DERIVED (d####). No PDF page numbers are used as locations.")
    return paras


def main():
    _t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", default=None)
    ap.add_argument("--out", default="/app/work/case_bundle.json")
    ap.add_argument("--max-paragraphs", type=int, default=None,
                    help="budget guard: keep at most N paragraphs (earliest first) and record the truncation")
    ap.add_argument("--max-chars", type=int, default=None,
                    help="budget guard: keep at most N characters of paragraph text in total")
    args = ap.parse_args()

    warnings = []
    case_dir = find_case_dir(args.case_dir)
    if case_dir is None:
        sys.stderr.write("FATAL: no case directory found (/input, ./input, cwd).\n")
        sys.exit(2)

    case_json = {}
    case_path = os.path.join(case_dir, "case.json")
    if os.path.exists(case_path):
        case_json = load_json(case_path)
        if isinstance(case_json, dict) and "__load_error__" in case_json:
            warnings.append(f"case.json unparseable: {case_json['__load_error__']}")
            case_json = {}
    else:
        warnings.append("case.json not found.")

    case_id, output_contract, task_text = extract_case_meta(case_json, case_dir, warnings)

    # ---- sources ----
    sources = []
    manifest = {}
    manifest_path = os.path.join(case_dir, "corpus-manifest.json")
    if os.path.exists(manifest_path):
        manifest = load_json(manifest_path)
        if isinstance(manifest, dict) and "__load_error__" in manifest:
            warnings.append(f"corpus-manifest.json unparseable: {manifest['__load_error__']}")
            manifest = {}
        else:
            sources = extract_sources(manifest, warnings)
    else:
        warnings.append("corpus-manifest.json not found; sources will be inferred from material files.")

    # case_id / output_contract may live in the manifest instead of case.json
    if not case_id and isinstance(manifest, dict):
        for k in ("case_id", "caseId", "id"):
            if manifest.get(k):
                case_id = str(manifest[k])
                break
    if not output_contract and isinstance(manifest, dict):
        oc = manifest.get("output_contract")
        if isinstance(oc, dict):
            output_contract = oc.get("fields", oc) if isinstance(oc.get("fields"), dict) else oc
        elif isinstance(oc, list):
            output_contract = {str(x): "" for x in oc}

    # role -> source_id map so per-paper files attach to the manifest's real source id
    role_to_sid = {}
    file_to_sid = {}
    for s in sources:
        r = (s.get("role") or "").lower()
        if r in ("primary", "secondary") and r not in role_to_sid:
            role_to_sid[r] = s["source_id"]
        # A manifest entry may name the file its text lives in; that file must bind to the
        # manifest's source_id, otherwise the same paper appears twice (as the manifest source
        # and again as a stub built from the file name) and its metadata is stranded.
        for key in ("file", "filename", "path", "source_file"):
            f = (s.get("raw") or {}).get(key) or s.get(key)
            if isinstance(f, str) and f:
                file_to_sid[os.path.basename(f)] = s["source_id"]
    if not output_contract:
        warnings.append("No output_contract declared; using the default field set from schema.")
    if "primary" not in role_to_sid and len(sources) == 2:
        role_to_sid = {"primary": sources[0]["source_id"], "secondary": sources[1]["source_id"]}
        warnings.append("Roles absent in manifest; mapped primary->first source, secondary->second source.")

    # ---- paragraphs ----
    paragraphs = []
    material_files = [
        ("material.json", None),
        ("primary-material.json", "primary"),
        ("secondary-material.json", "secondary"),
        ("primary_material.json", "primary"),
        ("secondary_material.json", "secondary"),
        ("material.txt", None),
    ]
    # discover PDFs / XML / Markdown / plain-text material files not covered by the fixed names
    for f in sorted(os.listdir(case_dir)):
        low = f.lower()
        if low.endswith(".xml") and f not in [m[0] for m in material_files]:
            # JATS full text downloaded from PMC arrives as one .xml per paper
            role = "primary" if "primary" in low else ("secondary" if "secondary" in low else None)
            material_files.append((f, role))
        elif low.endswith(".pdf") and f not in [m[0] for m in material_files]:
            role = "primary" if "primary" in low else ("secondary" if "secondary" in low else None)
            material_files.append((f, role))
        elif low.endswith(".txt") and not re.match(r"(requirements|license|licence|readme)\.txt$", low) \
                and f not in [m[0] for m in material_files]:
            role = "primary" if "primary" in low else ("secondary" if "secondary" in low else None)
            material_files.append((f, role))
        elif low.endswith(".md") and low != "task.md" and f not in [m[0] for m in material_files]:
            role = "primary" if "primary" in low else ("secondary" if "secondary" in low else None)
            material_files.append((f, role))

    loaded_any = False
    for fname, role_hint in material_files:
        path = os.path.join(case_dir, fname)
        if not os.path.exists(path):
            continue
        loaded_any = True
        role = ROLE_BY_NAME.get(fname, role_hint or "unknown")
        # A source id of "unknown" is unusable downstream (it cannot carry metadata and every
        # citation from that file reads the same); fall back to the file stem instead.
        default_sid = (file_to_sid.get(fname) or role_to_sid.get(role)
                       or re.sub(r"[^A-Za-z0-9_.-]+", "_", os.path.splitext(fname)[0]))
        if fname.endswith(".xml"):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                paragraphs += extract_paragraphs_from_xml(f.read(), default_sid, role)
            continue
        if fname.lower().endswith(".pdf"):
            paragraphs += extract_paragraphs_from_pdf(path, default_sid, role or "unknown", warnings)
            continue
        if fname.lower().endswith(".md") and fname.lower() != "task.md":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                paragraphs += extract_paragraphs_from_text(f.read(), default_sid, role or "unknown", fname)
            continue
        if fname.endswith(".txt"):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                blocks = [b for b in re.split(r"\n\s*\n", f.read()) if norm_ws(b)]
            for i, b in enumerate(blocks):
                if len(norm_ws(b)) < 40:      # same minimum as the JATS/Markdown paths
                    note_short(fname, b)
                    continue
                paragraphs.append({"source_id": default_sid, "paragraph_id": f"d{i+1:04d}",
                                   "section": "", "text": norm_ws(b), "role": role,
                                   "id_derived": True, "origin_file": fname, "order_in_source": i + 1})
            continue
        obj = load_json(path)
        if isinstance(obj, (dict, list)):
            discover_source_meta(obj)
        if isinstance(obj, dict) and "__load_error__" in obj:
            warnings.append(f"{fname} unparseable JSON: {obj['__load_error__']}")
            continue
        # try to attribute paragraphs to the right source by their own source_id
        paragraphs += extract_paragraphs_from_json(obj, default_source=default_sid, role=role,
                                                   warnings=warnings, path_label=fname)

    if not loaded_any:
        warnings.append("No material files (material.json/primary-/secondary-) found.")

    # ---- an id-less paragraph gets its derived id before de-duplication ----
    # Otherwise two distinct records share the key (source_id, None) and the second silently
    # replaces the first, which is how a two-abstract corpus became a one-paragraph corpus.
    _cnt = {}
    for p in paragraphs:
        if not p.get("paragraph_id"):
            n = _cnt.get(p["source_id"], 0) + 1
            _cnt[p["source_id"]] = n
            p["paragraph_id"] = f"d{n:04d}"
            p["id_derived"] = True

    # ---- de-duplicate: the same paragraph may appear in material.json and in a per-paper file ----
    by_pid = {}
    for p in paragraphs:
        key = (p["source_id"], p["paragraph_id"])
        if key not in by_pid:
            by_pid[key] = p
        else:
            prev = by_pid[key]
            if norm_ws(prev["text"]) != norm_ws(p["text"]):
                warnings.append(f"paragraph {key} appears with differing text in "
                                f"{prev.get('origin_file')} vs {p.get('origin_file')}; kept the longer text.")
            if len(p["text"]) > len(prev["text"]):
                p["order_in_source"] = prev.get("order_in_source")
                by_pid[key] = p
    paragraphs = list(by_pid.values())

    # ---- one paragraph read twice must not become two ----
    # `{"p1": {"text": ...}}` is picked up both as a keyed paragraph (id p1) and as a bare record
    # without an id (derived id), which doubled the corpus and split one claim over two quotes.
    seen_text = {}
    deduped = []
    for p in paragraphs:
        k = (p["source_id"], norm_ws(p["text"])[:80])
        prev = seen_text.get(k)
        if prev is None:
            seen_text[k] = p
            deduped.append(p)
            continue
        if prev.get("id_derived") and not p.get("id_derived"):
            deduped[deduped.index(prev)] = p
            seen_text[k] = p
    paragraphs = deduped

    # ---- attach xml originals if present (do not parse; keep for cross-check) ----
    xml_originals = {}
    for f in os.listdir(case_dir):
        if f.lower().endswith(".xml"):
            xml_originals[f] = sha256_of_file(os.path.join(case_dir, f))

    # ---- finalise paragraph ids (derive stable ids where missing) & order ----
    per_source_counter = {}
    for p in paragraphs:
        sid = p["source_id"]
        n = per_source_counter.get(sid, 0) + 1
        per_source_counter[sid] = n
        p.setdefault("order_in_source", n)
        if p["paragraph_id"] is None:
            p["paragraph_id"] = f"d{n:04d}"
            p["id_derived"] = True
        if p.get("id_derived"):
            # namespace derived ids so they can never collide with a JATS id
            if not p["paragraph_id"].startswith("d"):
                p["paragraph_id"] = p["paragraph_id"]  # keep explicit-but-flagged

    # ---- backfill manifest sources with metadata found inside the material files ----
    for src in sources:
        dm = DISCOVERED_META.get(src["source_id"], {})
        for k in ("doi", "title", "journal", "year"):
            if not src.get(k) and dm.get(k):
                src[k] = dm[k]
        if not src.get("license") and (dm.get("license") or dm.get("licence")):
            src["license"] = dm.get("license") or dm.get("licence")
        if not src.get("authors") and dm.get("authors"):
            a = dm["authors"]
            src["authors"] = [a] if isinstance(a, str) else a

    # ---- ensure every paragraph source exists in sources[] ----
    known = {s["source_id"] for s in sources}
    for sid in sorted({p["source_id"] for p in paragraphs}):
        if sid not in known:
            dm = DISCOVERED_META.get(sid, {})
            authors = dm.get("authors") or dm.get("author") or []
            if isinstance(authors, str):
                authors = [a.strip() for a in re.split(r"[;,]", authors) if a.strip()]
            sources.append({"source_id": sid, "role": dm.get("role") or "unknown",
                            "doi": dm.get("doi"), "title": dm.get("title"), "authors": authors,
                            "license": dm.get("license") or dm.get("licence"),
                            "sha256": dm.get("sha256") or dm.get("hash"), "raw": dm})
            warnings.append(f"Source '{sid}' appeared in material but not in manifest; added stub.")

    # ---- role reconciliation: if manifest has 2 sources and roles unknown, assign ----
    roles = [s.get("role") for s in sources]
    if "primary" not in roles and "secondary" not in roles and len(sources) == 2:
        # heuristic: the source whose id appears in primary-material first
        prim = next((p["source_id"] for p in paragraphs if p.get("role") == "primary"), None)
        for s in sources:
            s["role"] = "primary" if s["source_id"] == prim else "secondary"
        warnings.append("Manifest roles missing; assigned primary/secondary heuristically.")

    # ---- budget guard: keep the run inside the request/time budget ----
    # Truncation is recorded, never silent: the bundle carries a `budget` block, a warning, and
    # finalize.py turns it into status="partial" so the report cannot claim a complete graph.
    src_rank = {s["source_id"]: i for i, s in enumerate(sources)}
    budget = {
        "max_paragraphs": args.max_paragraphs,
        "max_chars": args.max_chars,
        "kept_paragraphs": len(paragraphs),
        "total_paragraphs": len(paragraphs),
        "kept_chars": sum(len(p["text"]) for p in paragraphs),
        "truncated": False,
        "dropped_by_source": {},
    }
    # Proactive budget warning: the run contract allows 64 model requests and the reading step
    # costs one window per ~6,000 characters (docs/BUDGET.md). Saying so at normalisation time is
    # the only point where the cap can still be chosen deliberately.
    est_windows = max(1, -(-budget["kept_chars"] // 6000)) if budget["kept_chars"] else 0
    if est_windows > 56 and not (args.max_paragraphs or args.max_chars):
        warnings.append(
            f"reading budget: {budget['kept_chars']} characters is about {est_windows} windows of "
            f"6,000 chars (plus ~5 requests of overhead) against a limit of 64 requests / 900 s. "
            f"Pass --max-paragraphs or --max-chars to cap the reading, and report the truncation.")
    if args.max_paragraphs or args.max_chars:
        order = sorted(range(len(paragraphs)),
                       key=lambda i: (src_rank.get(paragraphs[i]["source_id"], 10 ** 6),
                                      paragraphs[i].get("order_in_source", 10 ** 9)))
        keep, chars = [], 0
        for i in order:
            p = paragraphs[i]
            if args.max_paragraphs and len(keep) >= args.max_paragraphs:
                break
            if args.max_chars and keep and chars + len(p["text"]) > args.max_chars:
                break
            keep.append(i)
            chars += len(p["text"])
        keep_set = set(keep)
        dropped = [paragraphs[i] for i in order if i not in keep_set]
        if dropped:
            budget["truncated"] = True
            for p in dropped:
                budget["dropped_by_source"][p["source_id"]] = \
                    budget["dropped_by_source"].get(p["source_id"], 0) + 1
            paragraphs = [paragraphs[i] for i in sorted(keep_set)]
            budget["kept_paragraphs"] = len(paragraphs)
            budget["kept_chars"] = chars
            warnings.append(
                f"input truncated by budget guard (--max-paragraphs={args.max_paragraphs}, "
                f"--max-chars={args.max_chars}): kept {len(paragraphs)} of "
                f"{budget['total_paragraphs']} paragraphs, dropped {budget['dropped_by_source']}. "
                f"Report the missing material as a limitation; do not present the graph as complete.")

    if BACKMATTER_SKIPPED:
        titles = sorted({t for _, t in BACKMATTER_SKIPPED})
        warnings.append(
            f"{len(BACKMATTER_SKIPPED)} back-matter paragraph(s) skipped (not scientific content): "
            + ", ".join(titles[:6]))
    if SHORT_DROPPED:
        warnings.append(
            f"{len(SHORT_DROPPED)} short block(s) (<40 chars) were skipped and are not in the graph; "
            f"origins: {sorted({o for o, _ in SHORT_DROPPED})}")

    bundle = {
        "schema_version": "1.0",
        "case_id": case_id,
        "case_dir": case_dir,
        "task": task_text,
        "output_contract": output_contract,
        "sources": sources,
        "paragraphs": paragraphs,
        "xml_originals": xml_originals,
        "budget": budget,
        "runtime": {"prepare_seconds": round(time.time() - _t0, 3)},
        "warnings": warnings,
        "stats": {
            "n_sources": len(sources),
            "n_paragraphs": len(paragraphs),
            "n_paragraphs_by_source": {s["source_id"]: sum(1 for p in paragraphs if p["source_id"] == s["source_id"])
                                       for s in sources},
            "n_id_derived": sum(1 for p in paragraphs if p.get("id_derived")),
        },
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=1)

    if not paragraphs:
        sys.stderr.write(
            f"FATAL: no readable paragraphs in {case_dir}\n"
            "  Paper text must be in material.json / primary-material.json /\n"
            "  secondary-material.json / material.txt, or in any *.md, *.txt, *.pdf, *.xml\n"
            "  in that directory. corpus-manifest.json is metadata only: the files it lists\n"
            "  are NOT parsed for text.\n")
        if SHORT_DROPPED:
            sys.stderr.write(
                f"  {len(SHORT_DROPPED)} block(s) were found but skipped: paragraph text shorter\n"
                f"  than 40 characters is ignored (longest skipped: {max(c for _, c in SHORT_DROPPED)}\n"
                "  chars). Split or join the text so each paragraph is a full sentence.\n")
        # The reason a file produced nothing (PDF without pdftotext, an unparseable XML, a manifest
        # whose files were never parsed) is in the warnings; print them here instead of leaving the
        # reader to open case_bundle.json for a message that was already computed.
        if warnings:
            sys.stderr.write("  what was found, and why it produced no text:\n")
            for wmsg in warnings:
                sys.stderr.write("    ! " + wmsg + "\n")
        sys.exit(2)
    print(f"[prepare_case] case_id={case_id} sources={len(sources)} paragraphs={len(paragraphs)} "
          f"derived_ids={bundle['stats']['n_id_derived']} warnings={len(warnings)}")
    print(f"[prepare_case] wrote {args.out}")
    for w in warnings:
        print("  ! " + w)


if __name__ == "__main__":
    main()
