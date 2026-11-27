# literature-knowledge-graph

A Bohrium Skill that turns a small corpus of research papers into an **evidence-bound,
queryable knowledge graph**: typed entities and directed relations, each bound to
`source_id` + `paragraph_id` + a verbatim quote, aligned across papers, with merge,
conflict and uncertainty records, plus ≥3 executed queries.

Runs offline on the bundled two-paper example: Python 3.9+, standard library only, no network.

## Quickstart — three commands, then one query

From this directory, on the bundled example (two real open-access papers):

```bash
# 1 · the whole pipeline: prepare -> build -> query -> export -> finalize
bash run.sh all --case-dir examples/demo_perovskite/input \
     --annotations examples/demo_perovskite/annotations.example.json \
     --queries examples/demo_perovskite/queries.example.json --work work --out out

# 2 · check the installation (31 self-test checks)
bash run.sh test

# 3 · ask the graph one question, with its evidence printed
bash run.sh query --graph work/graph.json --type metric_compare \
       --name "power conversion efficiency" --out work/q.json
```

```
[query_graph] 1 queries: 1 answered, 0 partial, 0 undetermined -> work/q.json
  Q1 metric_compare: answered (8 nodes, 7 edges, 7 evidence)

Q1 metric_compare -> answered
  node DMTH-COF [material] P1
  node power conversion efficiency [metric] P1,P2
  node Boc-PDA-COF [material] P1
  node Tp-COF [material] P1
  node mesoscopic device architecture [model] P1
  node FA0.9MA0.1PbI2.85Br0.15 [material] P2
  node Cs0.05FA0.90MA0.05PbI2.85Br0.15 [material] P2
  node passivation [method] P1,P2
  value P1/d0063: 14.7%, 20.78%, 41.36%
  value P1/d0056: 15.88%, 18.88%, 76.46%, 20.78%
  value P2/Par31: no % value in the text (other numbers: 15)
  note Values are listed per source/paragraph and are NOT aggregated or averaged; different conditions/samples make …
  evidence 7 quote(s)
    P1/d0063: “The increase in PCE is even more significant, with a rise from 14.7% for pristine to 20.7…”
    P1/d0056: “The Tp-modified device reaches 15.88% PCE, Boc-PDA-COF-modified devices reach 18.88%, and…”
```

`out/graph_report.md` opens with the run's own state (`status`, the reasons when it is not
`success`, extraction mode, paragraphs kept, stage times), then the entities, relations, merge
decisions, conflicts and queries — it is meant to be readable on its own.

Command 1 writes `out/result.json` (the graded deliverable: `status`, `summary`,
`evidence_index`, `uncertainty`, `validation`) plus `nodes.csv`, `edges.csv`, `evidence.csv`,
`graph.mmd`, `graph.graphml` and `graph.svg`. The single-query form prints the answer; a whole query file
stays in `queries_result.json`, the source of truth (`-v` prints every answer).

The same pipeline stage by stage, when you need to inspect the intermediates:

```bash
bash run.sh prepare  --case-dir examples/demo_perovskite/input --out work/case_bundle.json
bash run.sh build    --bundle work/case_bundle.json \
       --annotations examples/demo_perovskite/annotations.example.json --out work/graph.json
bash run.sh query    --graph work/graph.json --queries examples/demo_perovskite/queries.example.json \
                     --out work/queries_result.json
bash run.sh export   --graph work/graph.json --queries work/queries_result.json --outdir out
bash run.sh finalize --bundle work/case_bundle.json --graph work/graph.json \
                     --queries work/queries_result.json --out out/result.json --outdir out
```

Query types (`--type`, or the `type` field of a query object):

| type | key arguments | answers |
|---|---|---|
| `entity` | `name` | one entity, its aliases, sources and incident relations |
| `neighbors` | `name`, `relation`, `direction` | what one entity is linked to, filtered by relation |
| `path` | `from`, `to`, `max_hops` | a chain of relations between two entities (or `undetermined`) |
| `relation_search` | `relation`, `keyword` | all relations of a type, optionally keyword-filtered |
| `keyword` | `keyword` | anything the graph's names, conditions or verified quotes say about a term |
| `cross_paper` | — | shared vs source-exclusive entities, plus recorded conflicts |
| `evidence_trace` | `id` (node or edge) | the paragraph and quote behind one item |
| `metric_compare` | `name` | per-source/per-paragraph values, never aggregated |

With no `--queries`, the questions in the case's task text are answered first (each record quotes
the question it came from), then a built-in set of four runs (`entity`, `relation_search`, `cross_paper`,
`evidence_trace`); a `--queries` path that does not exist is an error, not a silent fallback.
A single query of any type works from the command line — `--name`, `--id`, `--relation`,
`--keyword`, `--direction in|out|both`, `--from`, `--to`, `--max-hops` — and a missing required
field is an error rather than an unasked question:

```bash
bash run.sh query --graph work/graph.json --type path \
       --from "MAPbI3" --to "power conversion efficiency" --max-hops 3 --out work/path.json
```

For several queries at once use a file:
`{"queries":[{"qid":"Q1","type":"path","from":"A","to":"B","max_hops":3}]}`.

Evidence is labelled by what verification actually achieved: a node or edge is `verified` when a
quote was located, `unverified` when it carries no quote at all, and `rejected` when the quotes it
did carry were not found in the cited paragraph — rejected items stay in the graph, listed in
`uncertainty`, and never count towards the coverage figure. A `fuzzy` match (≥0.90 similarity) is
accepted but flagged weak, and it can never survive a changed number.

## Bring your own corpus

One directory, one paper per material file. Paper text is read from the `paragraphs` list of
`material.json`, `primary-material.json` or `secondary-material.json`, or from any `*.txt`,
`*.md`, `*.pdf` (needs `pdftotext`) or JATS `*.xml` file in that directory:

```
mycase/
  case.json                 {"case_id": "my-case", "output_contract": {...}}
  corpus-manifest.json      metadata only: source_id, doi, title, authors, license, sha256
  primary-material.json     paper 1 — the only file that carries text
  secondary-material.json   paper 2
```

```json
{"source_id": "P1", "doi": "10.1000/xyz", "role": "primary",
 "paragraphs": [{"source_id": "P1", "paragraph_id": "s3p2", "section": "Results",
                 "text": "The passivated film reached a power conversion efficiency of 21.3% with PEAI passivation under AM1.5G illumination."}]}
```

A single `material.json` may hold several papers instead — keyed by source id, or as a list of
paper objects whose paragraphs or abstract are nested — and each paper keeps its `doi`/`title`.
A record nested under a paper object inherits that paper's `source_id`. In JATS, inline
markup is preserved as text (`MAPbI<sub>3</sub>` becomes `MAPbI3`, not `MAPbI 3`), and
back-matter sections (author contributions, funding, competing interests, data availability,
acknowledgements, footnotes) are left out of the body and reported as a warning.

`paragraph_id` must be the provider's own id where one exists (JATS `p` id, database id); ids
generated from PDF/plain text are `d####` and every item built from them carries
`paragraph_id_kind="derived"`. Paragraph text shorter than 40 characters is skipped (the count is
reported, never dropped silently). Without a manifest, `source_id` comes from the `source_id`
field or the file stem. `corpus-manifest.json` is metadata only — the `file` fields it lists are
**not** parsed for text, so a manifest entry alone yields a source with zero paragraphs, and a
directory with no readable paragraph exits non-zero naming the accepted file names.

The graph is built from annotations, not from the bundle. Minimum working `annotations.json` for
the paragraph above (verified: 2 nodes, 1 edge, `metric_compare` answers `21.3%`):

```json
{"nodes": [
  {"label": "PEAI", "type": "material",
   "mentions": [{"source_id": "P1", "paragraph_id": "s3p2", "quote": "21.3% with PEAI passivation"}]},
  {"label": "power conversion efficiency", "type": "metric", "aliases": ["PCE"],
   "mentions": [{"source_id": "P1", "paragraph_id": "s3p2", "quote": "21.3% with PEAI passivation"}]}],
 "edges": [
  {"source_label": "PEAI", "target_label": "power conversion efficiency", "type": "reports",
   "evidence": [{"source_id": "P1", "paragraph_id": "s3p2", "quote": "21.3% with PEAI passivation"}]}]}
```

```bash
bash run.sh build --bundle work/case_bundle.json --annotations mycase/annotations.json --out work/graph.json
```

`quote` must be copied verbatim from the cited paragraph, 8–300 characters. A quote that is not
found is rejected and the item is kept but labelled `rejected`; a longer quote is verified in full
and stored as a word-boundary prefix of itself (`quote_truncated`, `quote_chars`) so the stored
text still lies inside the paragraph. The full shape is `schema/graph.schema.json`, a
fill-in file is `templates/annotations.template.json`, and the reading procedure is `SKILL.md`
§Procedure. With no annotations file, `build_graph.py` stops and names both routes instead of
writing an empty graph.

## What is in this directory

| Path | Role |
|---|---|
| `SKILL.md` | the skill: purpose, applicability, invocation, procedure, rules, error handling, self-check |
| `schema/graph.schema.json` | JSON Schema for `annotations.json` and `graph.json` (either shape validates; `tests/regression/regression.py R11` checks the shipped and freshly built artifacts against it) |
| `scripts/prepare_case.py` | normalise heterogeneous inputs → `case_bundle.json` (sources + paragraphs + output_contract) |
| `scripts/verify_evidence.py` | the only component allowed to declare a quote verified (exact/normalized/fuzzy/not_found) |
| `scripts/build_graph.py` | verify evidence, assign ids, merge aliases, log conflicts → `graph.json` |
| `scripts/query_graph.py` | 7 query types, each returning evidence and an explicit `undetermined` branch |
| `scripts/export_graph.py` | `graph.mmd`, `graph.graphml`, `nodes.csv`, `edges.csv`, `evidence.csv`, `graph_report.md` |
| `scripts/render_svg.py` | `graph.svg` preview: standard library only, deterministic, drawn even when no image stack exists |
| `scripts/finalize.py` | `result.json` with every `output_contract` field + honest status + validation |
| `scripts/add_paper.py` | incremental update: merge a new paper, preserve existing ids, log added/merged/conflicts |
| `scripts/heuristic_extract.py` | deterministic fallback extractor (baseline, not the quality path) |
| `scripts/run_all.py` | one-command pipeline for the demo and for fallback runs |
| `scripts/render_png.py` | optional `graph.png` preview (needs matplotlib; skipped with a message if absent) |
| `run.sh` | stage dispatcher: `prepare \| build \| query \| export \| finalize \| extract \| test \| verify \| all` (`extract` takes `--bundle`/`--out`; `verify` runs both suites) |
| `templates/` | fill-in annotation JSON + a per-window extraction prompt |
| `examples/demo_perovskite/` | a real two-paper worked example (inputs, curated annotations, outputs) |
| `tests/selftest.py` | 31 checks: quote verification, merge safety, type conflicts, end-to-end, packaging (modes, entry points, documented paths) |
| `docs/` | method, limitations, measured gain, budget, changelog, attempt ledger, usability test |

## Runtime contract

The skill follows the contract of the challenge it was written for: inputs at `/input`
(`case.json`, `task.md`, `corpus-manifest.json`, `material.json`, `primary-material.json`,
`secondary-material.json`), work under `/app/work`, deliverables under `/app/output`, including
`result.json`. Those are also the **defaults** of every script: run them elsewhere and pass
`--case-dir`, `--work`, `--out` explicitly. One-command form:

```bash
bash run.sh all --case-dir /input --work /app/work --out /app/output \
                --annotations /app/work/annotations.json        # omit to use the heuristic fallback
```

`--case-dir` is required: without it the normaliser would search the current directory and could
ingest unrelated files as a corpus. A failed stage aborts the run instead of writing an empty
`result.json`.

`result.json.status` has three values. `success` requires 100 % evidence coverage, ≥3 answered
queries, evidence bound to ≥2 sources, complete source metadata, a `case_id` and no dropped edges;
`partial` names each shortfall in `status_reasons` (truncated input, unverified items, dropped
endpoints, a paper with no evidence, <3 answered queries); `undetermined` means no node, or no
evidence, survived verification. `success` is not a claim that every query was answerable — a
queries file of four may leave one `undetermined` and still be `success`. Read the reasons and the
`undetermined` branch, do not read the status alone.

## Requirements

- Python 3.9+ (standard library only; no third-party packages).
- No network access is needed at run time.
- Input formats: JSON paragraph records, JATS XML, Markdown, plain text, and PDF (PDF conversion
  shells out to the external `pdftotext` from Poppler; everything else is pure standard library).
  Ids derived from PDF/plain text are `d####` and flagged `paragraph_id_kind="derived"`.

## Worked example

`examples/demo_perovskite/` runs end-to-end on two real open-access papers and is the
regression fixture for `tests/selftest.py`:

| id | paper | DOI | license |
|---|---|---|---|
| P1 | Engineering Larger Grains in MAPbI3 Solar Cells via Covalent Organic Framework (COF)-Assisted Crystallization | 10.3390/polym18202535 | CC BY (MDPI) |
| P2 | Resolving carrier kinetics in perovskite through deep-learning-assisted photoluminescence analysis | 10.1038/s41467-026-77052-8 | CC BY (Springer Nature) |

The two papers share `Spiro-OMeTAD`, `perovskite`, `PCE`, `passivation` and
`non-radiative recombination`, but study **different absorbers** (MAPbI3 vs
FA0.9MA0.1PbI2.85Br0.15 / CsFAMA), **different device areas** (0.50 vs 0.14 cm²) and
**different metrics** (device PCE vs DL-model R²). That is deliberate: it exercises alias
merging, non-merge justification and cross-paper conflict logging on real text.
`examples/demo_perovskite/output/` is a labelled example output, not a graded answer.

Result: 35 nodes, 34 edges, 100% evidenced, 9 merge decisions (5 merged, 4 kept
separate by decision), 4 recorded cross-paper
conflicts, 6/6 queries answered, `status="success"`.

## Testing

```bash
bash run.sh verify                       # the gate: 31 self-test + 96 regression checks, exit 0 = pass
bash run.sh test                         # self-test only
python3 tests/regression/regression.py    # regression only (R1–R16)
```

## Version and provenance

- `schema_version` 1.0; skill content as shipped in this directory.
- Demo papers were retrieved from PubMed Central Open Access (JATS XML); DOI and license are
  recorded per source in `examples/demo_perovskite/input/corpus-manifest.json` together with a
  SHA-256 of each source file.
- No PDF page numbers are used anywhere. Locations are provider JATS paragraph ids, or derived
  ids flagged `paragraph_id_kind="derived"`.

## GitHub link

This work is published at

```
https://github.com/Spaceburial/literature-knowledge-graph-skill/tree/main/literature-knowledge-graph
```

`GITHUB_URL.txt` carries that link on its first line and the repository-relative directory
`literature-knowledge-graph` on its second. The repository is public, and that directory holds
exactly the files shipped in this submission. `scripts/publish_github.sh` re-publishes the
current directory when `GITHUB_TOKEN` is set; that script is how this copy was published.
