# literature-knowledge-graph

A Bohrium Skill that turns a small corpus of research papers into an **evidence-bound,
queryable knowledge graph**: typed entities and directed relations, each bound to
`source_id` + `paragraph_id` + a verbatim quote, aligned across papers, with merge,
conflict and uncertainty records, plus ≥3 executed queries.

The skill follows the runtime contract of the challenge it was written for: inputs at
`/input` (`case.json`, `task.md`, `corpus-manifest.json`, `material.json`,
`primary-material.json`, `secondary-material.json`), work under `/app/work`, deliverables
under `/app/output` including `result.json`.

## What is in this directory

| Path | Role |
|---|---|
| `SKILL.md` | the skill: purpose, applicability, invocation, procedure, rules, error handling, self-check |
| `schema/graph.schema.json` | JSON Schema for `annotations.json` and `graph.json` |
| `scripts/prepare_case.py` | normalise heterogeneous inputs → `case_bundle.json` (sources + paragraphs + output_contract) |
| `scripts/verify_evidence.py` | the only component allowed to declare a quote verified (exact/normalized/fuzzy/not_found) |
| `scripts/build_graph.py` | verify evidence, assign ids, merge aliases, log conflicts → `graph.json` |
| `scripts/query_graph.py` | 7 query types, each returning evidence and an explicit `undetermined` branch |
| `scripts/export_graph.py` | `graph.mmd`, `graph.graphml`, `nodes.csv`, `edges.csv`, `evidence.csv`, `graph_report.md` |
| `scripts/finalize.py` | `result.json` with every `output_contract` field + honest status + validation |
| `scripts/add_paper.py` | incremental update: merge a new paper, preserve existing ids, log added/merged/conflicts |
| `scripts/heuristic_extract.py` | deterministic fallback extractor (baseline, not the quality path) |
| `scripts/run_all.py` | one-command pipeline for the demo and for fallback runs |
| `templates/` | fill-in annotation JSON + a per-window extraction prompt |
| `examples/demo_perovskite/` | a real two-paper worked example (inputs, curated annotations, outputs) |
| `tests/selftest.py` | 20 checks: quote verification, merge safety, type conflicts, end-to-end |
| `docs/` | method, limitations, measured gain over the baseline, changelog |

## Requirements

- Python 3.9+ (standard library only; no third-party packages).
- No network access is needed at run time. `prepare_case.py` also parses JATS XML if present.

## Run it

```bash
# 1. normalise the case
python scripts/prepare_case.py --case-dir /input --out /app/work/case_bundle.json

# 2. write /app/work/annotations.json from a close reading (see SKILL.md Step 2)

# 3. build, query, export, finalise
python scripts/build_graph.py  --bundle /app/work/case_bundle.json \
       --annotations /app/work/annotations.json --out /app/work/graph.json
python scripts/query_graph.py  --graph /app/work/graph.json --out /app/work/queries_result.json
python scripts/export_graph.py --graph /app/work/graph.json \
       --queries /app/work/queries_result.json --outdir /app/output
python scripts/finalize.py     --bundle /app/work/case_bundle.json \
       --graph /app/work/graph.json --queries /app/work/queries_result.json \
       --out /app/output/result.json --outdir /app/output
```

Or in one command (uses the fallback extractor if `annotations.json` is absent):

```bash
python scripts/run_all.py --case-dir /input --work /app/work --out /app/output
```

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

Result: 35 nodes, 34 edges, 100% evidenced, 4 merge decisions, 4 recorded cross-paper
conflicts, 6/6 queries answered, `status="success"`.

## Testing

```bash
python tests/selftest.py      # 25 checks, exit 0 = pass
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
