---
name: literature-knowledge-graph
description: Build an evidence-bound, queryable knowledge graph from a small corpus of research papers (one or more PDFs/JATS/JSON paragraph sets). Extracts typed entities (researcher, material, method, task, metric, conclusion) and directed relations (uses, compares, outperforms, supports, contradicts, measures, evaluated_on, reports, improves, part_of, produces, based_on), binds every node and edge to a source_id + paragraph_id + verbatim quote, aligns aliases across papers, records merge/non-merge decisions and conflicts, answers at least three real queries with evidence, and writes a structured result.json. Use when a task asks to turn papers into nodes/edges, to trace claims back to text, to compare papers, or to build/query a literature knowledge graph.
---

# Literature knowledge graph construction

## What this skill produces

Given a case directory with papers and a task, it writes:

| Path | Content |
|---|---|
| `/app/work/case_bundle.json` | normalised papers: `sources[]` + `paragraphs[]` + `output_contract` |
| `/app/work/annotations.json` | the extraction (nodes, edges, merge decisions, conflicts) — written by you |
| `/app/work/graph.json` | validated graph: ids, verified evidence, merge log, conflict log, uncertainty |
| `/app/work/queries_result.json` | ≥3 executed queries with evidence |
| `/app/output/result.json` | deliverable: `case_id` + all `output_contract` fields + status/uncertainty |
| `/app/output/graph.{json,mmd,graphml,png}`, `nodes.csv`, `edges.csv`, `evidence.csv`, `graph_report.md` | exports, rendered preview and readable report |

All commands below use `$SKILL_DIR` = the directory that contains this `SKILL.md`
(the evaluator installs it at `/skills/weekly-skill`). Set it once per shell:

```bash
export SKILL_DIR="${SKILL_DIR:-/skills/weekly-skill}"   # adjust if installed elsewhere
```

The skill is **topic-agnostic**. It does not assume any domain label; it reads the actual files.
It never invents a quote, a number, a page, or a DOI.

## When to use / not use

Use when the task is: extract entities and relations from papers; bind claims to passages;
align the same concept across two papers; answer questions over a small corpus; audit which
claims are self-reported vs cited.

Do not use for: full-text PDF layout reproduction, figure digitisation, or judging scientific
correctness. It records what the text says and where; it does not adjudicate truth.

---

## Procedure (follow in order)

### Step 0 — Read before acting

1. `ls /input` and read `/input/task.md` in full.
2. Read `/input/case.json`: note `case_id` and every key of `output_contract`. Your `result.json`
   must contain those keys (the script maps them; see Step 5).
3. Read `/input/corpus-manifest.json`: record each paper's `source_id`, `doi`, `title`, `authors`,
   `license`. **Metadata belongs only to the paper that declares it.** Never copy paper A's
   DOI/title onto paper B.
4. Count the material files. At least two independent papers are expected
   (`primary-material.json`, `secondary-material.json`, optionally an aggregate `material.json`).
   If one is missing or unreadable, say so in `uncertainty` — do not fabricate a second paper.
5. Open enough paragraphs to know the topic, the methods, the metrics and the claims. Read at
   least the abstract, results and conclusions of each paper before extracting.

### Step 1 — Normalise inputs

```bash
python $SKILL_DIR/scripts/prepare_case.py --case-dir /input --out /app/work/case_bundle.json
```

This assigns stable ids and flags `id_derived=true` for paragraphs that had no provider id.
Read the printed warnings; they are part of your report.

**Budget guard.** If the material is large enough to threaten the run budget (64 model requests,
900 s), cap it instead of overrunning:

```bash
python $SKILL_DIR/scripts/prepare_case.py --case-dir /input --out /app/work/case_bundle.json \
       --max-paragraphs 120 --max-chars 400000
```

The bundle then carries `budget.truncated=true`, the dropped paragraphs per paper, and a warning;
`finalize.py` downgrades the status to `partial` and says so in `status_reasons`. Truncation is
visible, never silent — report the missing text as a limitation.

### Step 2 — Extract (your job, the LLM step)

Read the paragraphs in `case_bundle.json` in windows (by source, then by section). Produce
`/app/work/annotations.json` with this shape (full schema in `schema/graph.schema.json`):

```json
{
  "nodes": [
    {"label": "Spiro-OMeTAD", "type": "material", "aliases": ["spiro-OMeTAD"],
     "mentions": [{"source_id": "P1", "paragraph_id": "d0021",
                   "quote": "FTO/c-TiO2/m-TiO2/perovskite/Spiro-OMeTAD/Au", "attribution": "self"}]}
  ],
  "edges": [
    {"source_label": "DMTH-COF", "target_label": "power conversion efficiency",
     "type": "reports", "condition": "MAPbI3, mesoscopic, 0.50 cm2, champion 20.78% vs pristine 14.7%",
     "direction_note": "", "evidence": [{"source_id": "P1", "paragraph_id": "d0063",
                   "quote": "rise from 14.7% for pristine to 20.78% for the DMTH-COF device"}]}
  ],
  "merge_candidates": [
    {"surfaces": ["Spiro-OMeTAD", "spiro-OMeTAD"], "decision": "merged",
     "basis": "same chemical species, both used as HTL; differ only in capitalisation"},
    {"surfaces": ["MAPbI3", "FA0.9MA0.1PbI2.85Br0.15"], "decision": "kept_separate",
     "basis": "different absorber compositions; not the same physical sample"}
  ],
  "source_conflicts": [
    {"kind": "non_comparable_efficiency",
     "detail": "P1 PCE 20.78% (MAPbI3, 0.50 cm2) vs P2 15-device distribution (FAMA/CsFAMA, 0.14 cm2); P1 itself says cross-study efficiencies are not comparable",
     "items": ["P1/d0070", "P2/Par31"]}
  ],
  "uncertainty": [{"kind": "value_not_reported_in_text", "detail": "...", "items": ["P2/Par31"]}]
}
```

Extraction rules that determine the score:

- **Entity types**: `researcher`, `material`, `method`, `task`, `metric`, `conclusion` (plus
  `dataset`, `model`, `other`). A conclusion is one atomic claim, phrased as a sentence.
- **Relation types**: `uses`, `compares`, `outperforms`, `supports`, `contradicts`, `measures`,
  `evaluated_on`, `reports`, `improves`, `part_of`, `produces`, `based_on`. Direction is
  source→target; state it in `direction_note` when it could be read either way.
- **Only assert what the sentence asserts.** Co-occurrence is not a relation. A review sentence
  that summarises someone else's result is `attribution: "other"`, not the authors' own result.
- **One relation per supported claim, with its condition.** `outperforms` requires a comparison
  in the text plus the metric; put the metric, sample and condition in `condition`.
- **`quote` must be verbatim from the cited paragraph**, 8–300 characters. Copy it; never paraphrase.

### Step 3 — Align entities (this is where cross-paper graphs usually fail)

Apply these rules and record each decision in `merge_candidates`:

1. Merge true synonyms: abbreviation ↔ full form (`PCE`↔`power conversion efficiency`),
   hyphenation/case variants (`non-radiative`↔`nonradiative`), the same chemical with different
   naming (trivial name ↔ IUPAC), explicit “also called” statements. Give the `basis`.
2. **Do not merge** a generic class with a specific instance (`COFs` vs `DMTH-COF`), or the same
   generic term when the papers study different physical samples (`perovskite` = MAPbI3 in P1 vs
   FA/MA/Cs mixed-cation in P2). Mark `kept_separate` and say why.
   A `kept_separate` decision only holds if the two objects can be apart: nodes are keyed by
   `canonical_key` (default: the label). When two objects share a display label, give each its own
   key — `"label": "perovskite"` with `"canonical_key": "perovskite|MAPbI3"` and
   `"perovskite|CsFAMA"`. If the surfaces collapse to one key, the build reports
   `kept_separate_single_key` rather than logging a decision that was never applied.
3. Do **not** merge two papers' conditions, samples or numeric results into one conclusion.
   “Same method name” never means “same experiment”.
4. Same-name different-entity (e.g. two different “P1” devices, or a person and a material with
   the same acronym): keep separate nodes and note the collision in `uncertainty`.

### Step 4 — Build, query, export

```bash
python $SKILL_DIR/scripts/build_graph.py  --bundle /app/work/case_bundle.json \
       --annotations /app/work/annotations.json --out /app/work/graph.json
python $SKILL_DIR/scripts/query_graph.py  --graph /app/work/graph.json \
       --out /app/work/queries_result.json
python $SKILL_DIR/scripts/export_graph.py --graph /app/work/graph.json \
       --queries /app/work/queries_result.json --outdir /app/output
python $SKILL_DIR/scripts/render_png.py --graph /app/work/graph.json --out /app/output/graph.png
python $SKILL_DIR/scripts/finalize.py     --bundle /app/work/case_bundle.json \
       --graph /app/work/graph.json --queries /app/work/queries_result.json \
       --out /app/output/result.json --outdir /app/output
```

If the case states specific query questions, put them in a `queries.json`
(`{"queries":[{"qid":"Q1","type":"entity","name":"..."}]}`) and pass `--queries`.
Otherwise `query_graph.py` auto-generates at least four. Query types: `entity`, `neighbors`,
`path`, `relation_search`, `cross_paper`, `evidence_trace`, `metric_compare`.

`build_graph.py` verifies every quote against the cited paragraph. A quote that cannot be found
is rejected and listed; the node/edge is kept but labelled `evidence_status="unverified"` and
added to `uncertainty`. Fix rejections by re-reading the paragraph — do not loosen the check.

### Adding a paper later (incremental update)

When a new paper arrives, do **not** rebuild from scratch: rebuild renumbers ids and loses
review. Instead, extract the new paper into its own `annotations.json` (same rules), then merge:

```bash
python $SKILL_DIR/scripts/prepare_case.py --case-dir /input --out /app/work/new_bundle.json
python $SKILL_DIR/scripts/add_paper.py --graph /app/work/graph.json \
       --bundle /app/work/new_bundle.json --annotations /app/work/new_annotations.json \
       --out /app/work/graph_v2.json --change-log /app/work/change_log.json
```

`add_paper.py` keeps every existing `N####/E####`, merges a new surface into an existing node
only when the canonical key/alias matches **and** the type matches, unions evidence instead of
duplicating an identical `(source, target, type)` edge, and appends `bidirectional_outperforms`
or `relation_conflict` entries it creates. `change_log.json` records added nodes/edges, merged
nodes/edges, conflicts added and rejected quotes. The self-test asserts that adding P2 to a
P1-only graph yields exactly the same node and edge counts as a full build.

### Step 5 — Check, then report

`finalize.py` sets an honest status:

- `success`: every node/edge has a verified quote, ≥3 queries answered/partial, evidence from
  both papers.
- `partial`: graph built but something is missing (listed in `status_reasons`).
- `undetermined`: no usable graph (listed reason).

It maps each declared `output_contract` field to the canonical block
(`entities→nodes`, `relations→edges`, `evidence→evidence_index`, …) and records the mapping in
`output_contract_mapping`. Review `/app/output/result.json`, then answer the user with the
summary, the 3+ query results and the uncertainty items.

---

## Evidence and location rules (non-negotiable)

- Every node and edge cites `source_id`, `paragraph_id`, `quote`; the build step adds the
  surrounding `context` sentence and the `match` level (`exact`/`normalized`/`fuzzy`).
- `paragraph_id` is the provider's JATS paragraph id. If the provider gave none, the id is
  derived (`d0001…`) and flagged `paragraph_id_kind="derived"`.
- **Never call a location a PDF page.** There is no PDF page in this contract. Do not write
  “page 1”; cite `P1/Par12` or `P1/d0012`.
- Inline formulas may be linearised in the source. Do not re-derive or “correct” them; quote as given.
- No images, supplementary attachments or underlying clinical/experimental data are available.
  Do not infer numeric values from figures. If a value appears only in a plot, record
  `value_not_reported_in_text` in `uncertainty`.

## Error handling

| Situation | Action |
|---|---|
| `case.json` / `task.md` missing | continue with `corpus-manifest.json`; add a warning to `uncertainty` |
| one paper unreadable / PDF unparseable | build a single-paper graph, `status="partial"`, state which paper failed |
| `corpus-manifest.json` missing | infer sources from material files; `doi/title/authors` stay null; say so |
| paragraph has no id | derived id `d####`, flagged; never presented as original |
| entity name ambiguous | keep candidates separate, list them in the query answer's `candidates` |
| relation evidence conflicts between papers | keep both edges, log `source_disagreement` with both quotes; do not pick one |
| query returns nothing | return `status="undetermined"` with the reason; never invent a path |
| two papers disagree on a number | report both per source; never average, never merge into one claim |

## Self-check before finishing

1. `python $SKILL_DIR/tests/regression/regression.py` passes: six cases covering the full run,
   a single paper with no `case.json`, an altered quote, same-label different objects, missing
   paragraph ids, and budget truncation.
2. `python $SKILL_DIR/tests/selftest.py` passes (checks schema, evidence, merge, query).
3. `result.json.validation.checks` are all `true`.
4. Every `output_contract` key is present in `result.json` (see `output_contract_mapping`).
5. `evidence.csv` rows all have non-empty `quote` and a `match` in {exact, normalized, fuzzy}.
6. `uncertainty` names every unreported value and every undetermined relation you met.

## Minimal example (illustrative, not a graded answer)

Input: two paragraphs, one per paper, both mentioning a shared HTL and different absorbers.

```bash
python $SKILL_DIR/scripts/prepare_case.py --case-dir $SKILL_DIR/examples/demo_perovskite/input \
       --out /tmp/work/case_bundle.json
python $SKILL_DIR/scripts/build_graph.py --bundle /tmp/work/case_bundle.json \
       --annotations $SKILL_DIR/examples/demo_perovskite/annotations.example.json --out /tmp/work/graph.json
python $SKILL_DIR/scripts/query_graph.py --graph /tmp/work/graph.json \
       --queries $SKILL_DIR/examples/demo_perovskite/queries.example.json --out /tmp/work/q.json
```

Abridged output (`$SKILL_DIR/examples/demo_perovskite/output/result.json` is the full worked example):
`status="success"`, 35 nodes, 34 edges, 100% evidenced, 4 merge decisions, 4 recorded
cross-paper conflicts, 6/6 queries answered. One query answer:

```
Q5 metric_compare "power conversion efficiency"
  P1/d0063 14.7%, 20.78%, 41.36%  (MAPbI3, DMTH-COF device)
  P1/d0056 15.88%, 18.88%, 76.46%, 20.78%
  P2/Par31 (no numeric value; PCE shown only as a 15-device box plot)
  note: values are per source/paragraph and are NOT aggregated
```

## Limitations

- Extraction quality depends on the reading step; the deterministic fallback
  (`heuristic_extract.py`) is a baseline only and produces many untyped nodes.
- Quote verification is lexical; a paraphrase is rejected even when semantically right — copy quotes.
- Very long paragraphs are not split; a quote longer than the paragraph fails.
- The graph is only as complete as the supplied paragraphs (no figure/supplement mining).
