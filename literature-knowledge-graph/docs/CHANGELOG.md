# Changelog

## 1.2 — auditability and first-contact failures

Two rounds of a usability test by an unassisted reader (`docs/USABILITY.md`) found that the
pipeline's worst failures were silent successes. This release makes each of them speak, and
closes one hole in the evidence gate.

- `verify_evidence.py`: a near-verbatim quote whose **numbers** disagree with the paragraph is
  rejected as `numeric mismatch`. A single edited digit inside a 200-character sentence still
  scores ~0.95 on string similarity, so similarity alone was certifying quotes the paper never
  makes. (Found by the usability test: `21.8%` where the text says `21.3%` came back `verified`.)
- `build_graph.py`: `--annotations` no longer defaults to a fixed `/app/work/annotations.json`,
  where a stale file from an earlier run could be read as this run's extraction. It now defaults
  to `annotations.json` next to the bundle, prints which file it used, and stops with both routes
  named when the file is absent (it used to write a 0-node graph and exit 0). Annotations that
  yield no node exit non-zero.
- `build_graph.py`: the merge log now records an annotated `merged` decision even when the
  surfaces already share one canonical key, and `not_applicable` when no surface is in the graph.
  Five of the demo's nine decisions were applied but never logged, so `merge_log` showed only the
  four non-merges.
- `build_graph.py`: a node/edge type outside the schema is still stored as `other`, but the
  coercion is counted in `graph["warnings"]` and on stderr instead of happening silently.
- `prepare_case.py`: a directory with no readable paragraph exits non-zero; when short blocks are
  the cause, the message says how many were skipped and the 40-character minimum. The same
  minimum now applies to `*.txt` input, which was exempt. `*.txt` files other than `material.txt`
  are discovered, and a source without manifest metadata gets its id from the file stem rather
  than the literal string `unknown`.
- `query_graph.py`: `-v` (and any single `--type` query) prints the answer — nodes, per-paragraph
  values, notes, and the first quotes — instead of a bare count. A `--queries` path that does not
  exist is an error; it used to fall back to the built-in set silently. Duplicate value rows for
  one paragraph are collapsed.
- `run_all.py`: `--case-dir` is required (without it the normaliser could read the package's own
  `README.md` and `SKILL.md` as the corpus) and a failed stage aborts instead of leaving an empty
  `result.json`.
- `tests/regression/regression.py`: R7 (empty corpus, missing annotations, node-less annotations
  and missing query file each exit non-zero), R8 (one edited digit in a quote) and R9 (a build
  whose quotes match no paragraph stops; a query with no verified evidence is not `answered`;
  a failed validation check cannot sit beside `success`). 41 checks.
- `build_graph.py`: a graph in which **no** item's quote was found in the bundle exits
  non-zero. All-rejected evidence used to be printed as `0 verified` with exit 0, which read
  as a finished graph; in the default layout a stale `/app/work/annotations.json` could
  trigger exactly that. `finalize.py` moves the status to `partial` and names the check when
  any entry of `validation.checks` fails.
- `prepare_case.py`: plain-text paragraph ids are `d####` (they were `t####`, which contradicted
  the documented derived-id form and failed the derived-id validation check), and a manifest
  entry's `file` field now binds that file's text to the manifest's `source_id` instead of
  producing a second, metadata-less source.
- `query_graph.py`: a single query of any type is expressible on the command line (`--id`,
  `--relation`, `--keyword`, `--direction`, `--from`, `--to`, `--max-hops`), and a missing required
  field is an error naming the flag, instead of a query that silently asks nothing.
- `verify_evidence.py` / `build_graph.py`: a fuzzy match now stores `matched_text` — the
  paragraph's own wording at the matched span — beside the submitted quote, because "0.91 similar"
  is not verbatim and a reviewer has to be able to see the difference.
- `finalize.py`: the derived-id check now fails only for a bare integer (an id that could be read
  as a PDF page number). A namespaced derived id such as `p12` or `s3p2` no longer blocks
  `success`; the check guards its stated intent instead of one spelling of it.
- `build_graph.py`: the audit report defaults to `build_report.txt` next to `--out` rather than a
  fixed `/app/work` path.
- `prepare_case.py`: warns at normalisation time when the corpus exceeds ~56 reading windows
  (the 64-request / 900 s contract), so a cap is chosen deliberately instead of discovered
  mid-run. The input is untouched unless the flag is passed.
- Input coverage, found by running ten corpus shapes through the pipeline: JATS `*.xml` files are
  discovered at all (a directory of PMC XML used to yield zero paragraphs); metadata carried by an
  aggregate `material.json` reaches `sources[]` instead of a metadata-less stub; a
  `{"p1": {"text": ...}}` corpus is counted once, not twice with a derived id; a record nested
  under a paper object inherits its `source_id`; and id-less paragraphs are given their derived id
  *before* de-duplication, so two distinct records can no longer collide on `(source, None)` and
  overwrite each other. `heuristic_extract.py` proposes CJK phrase candidates, so a Chinese corpus
  no longer produces an empty graph. R10 covers the four input-shape fixes.
- `prepare_case.py`, JATS text fidelity (found by parsing the two demo papers straight from
  Europe PMC full-text XML, 282 KB + 217 KB): inline markup no longer splits a token, so
  `MAPbI<sub>3</sub>` yields `MAPbI3` and a quote a reader copies verifies as `exact` instead of
  failing; back-matter sections that publishers place inside `<body>` (author contributions,
  funding, competing interests, data availability, acknowledgements, footnotes) are excluded and
  counted in `bundle.warnings`. 172 raw blocks → 166 body paragraphs, 6 back-matter blocks named.
- `prepare_case.py`: warnings about skipped blocks are recorded in `bundle.warnings` before the
  bundle is written (they were appended after the dump, so only stdout showed them), and the
  no-paragraph failure now echoes every collected warning, so a PDF without `pdftotext`, or a
  manifest whose files were never parsed, states its own cause instead of a generic list.
- `finalize.py`: the no-graph result keeps the full `result.json` shape (empty `nodes`/`edges`,
  `validation` keys) instead of a three-key stub.
- `schema/graph.schema.json`: the root used `oneOf` over the annotation and graph shapes, so a built
  graph — which satisfies both — validated against neither. It is `anyOf` now, `merge_decision`
  accepts `not_applicable`, and an evidence record may carry `matched_text`. The schema had never
  been run against the shipped artifacts; both examples were failing it.
- `build_graph.py`: graph edges carry `source_label`/`target_label` (the schema requires them; ids
  alone force a reader to look each endpoint up), and a quote longer than the documented 300
  characters is verified in full but stored as a word-boundary prefix with `quote_truncated` and
  `quote_chars`. Four of the shipped example annotations exceeded the limit; they were shortened
  to verbatim prefixes.
- `tests/regression/regression.py`: R11 validates the shipped annotations, the shipped example
  graph and a freshly built graph against the schema, rejects a graph with an out-of-schema
  relation type, and asserts no stored quote exceeds 300 characters. Works with `jsonschema` when
  installed and with a stdlib subset otherwise. 55 checks.
- `README.md`: quickstart reduced to three commands plus one query, a "Bring your own corpus"
  contract with a verified minimal `primary-material.json` and `annotations.json`, the seven query
  types, and the `success`/`partial`/`undetermined` vocabulary.
- `docs/USABILITY.md`: both test rounds, the frictions that remain, and what a single reader
  needed.

## 1.1 — stability and honest truncation
- `prepare_case.py`: `--max-paragraphs` / `--max-chars` budget guard. Truncation is recorded in
  `bundle.budget` (kept/total, dropped per paper) and warned, never silent.
- `finalize.py`: a truncated input can no longer report `status="success"`; the reason is the first
  entry of `status_reasons`, so a partial graph cannot be presented as a complete one.
- `build_graph.py`: a `kept_separate` decision whose surfaces share one canonical key is reported as
  `kept_separate_single_key` (plus `keep_separate_not_applied` in `uncertainty`) instead of being
  logged as if it had been applied. Keeping two same-label objects apart now requires giving each
  its own `canonical_key`, documented in `SKILL.md` and `templates/annotations.template.json`.
- `tests/regression/regression.py`: six-case suite (R1–R6), 23 assertions, run before every
  submission. Covers the full run, a single paper with no `case.json`, an altered quote,
  same-label different objects, a missing paragraph id, and budget truncation.
- `docs/ATTEMPTS.md`: submission ledger written by `tools/poll_attempt.py`.
- `finalize.py`: a graph that dropped candidate edges for unresolved endpoints no longer reports
  `success`; the count is a status reason. (Found by the new A/B harness: the deterministic baseline
  was reporting `success` while discarding 68 edges.)
- `bench/metrics.py`: one run directory → one row of metrics, every value read from files the
  pipeline already writes; a missing source is `null` and listed, not `0`.
- `bench/run_ab.py`: `ab` compares two extraction conditions on the same normalized bundle with
  repeats and medians; `budget` models requests/windows against 64 requests / 900 s and recommends a
  `--max-paragraphs` cap. Thresholds documented in `docs/BUDGET.md`; the demo needs ~33 requests and
  ~620 s at a 6,000-character window.

## 1.0 — initial release
- Input normaliser for JSON paragraph lists, id-keyed dicts, JATS XML, and aggregate +
  per-paper material files; role→source_id mapping; duplicate handling.
- Quote-verification gate (exact / normalized / fuzzy) with rejection log.
- Graph builder with explicit merge decisions, type-conflict refusal, conflict detection.
- Seven query types with an explicit `undetermined` branch.
- Exports: Mermaid, GraphML, nodes/edges/evidence CSV, Markdown report.
- `result.json` with adaptive `output_contract` mapping and honest status.
- Deterministic fallback extractor (baseline).
- Worked two-paper example and 20-check self-test.

### Known issues
- Minimal JATS table handling.
- English-oriented normalisation heuristics.
