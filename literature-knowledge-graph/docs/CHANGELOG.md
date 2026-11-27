# Changelog

## 1.3.6 — three input shapes that produced zero paragraphs

Tested nine plausible deliveries of the same two-paper corpus through `prepare_case.py`. Three
of them failed outright, and one of those failed silently in a worse way than an error:

| shape | before | after |
|---|---|---|
| `P1`, `P2` — plain text, no suffix | exit 2, 0 paragraphs | 2 paragraphs, sources `P1`/`P2` |
| `paragraphs.json` — a corpus under a name the fixed list does not know | exit 2, 0 paragraphs | 2 paragraphs |
| `{"P1": {"text": …}, "P2": {"text": …}}` | 2 paragraphs, **both attributed to one source named after the file** | 2 paragraphs, sources `P1`/`P2` |

The third is the dangerous one: it did not fail, it merged two independent papers into a single
source, which is exactly the error the task forbids (the conditions, samples and numbers of two
papers would then sit in one source with no way to tell them apart).

- `file_kind()` decides by suffix, then by the first bytes (`%PDF`, `<`, `{`/`[`, printable text),
  so an extensionless file is read rather than skipped.
- Discovery also accepts any `*.json` not in the metadata set (`case`, `corpus-manifest`,
  `queries`, `annotations`, `schema`, `result`, …), and if nothing at all is recognised it sniffs
  every remaining regular file instead of giving up with an empty bundle.
- A dict keyed `P1`/`P2`/`paper1` now carries that key down as `source_id`; the keys are listed in
  `bundle.warnings`. Lowercase `p1`/`p2` stays a paragraph id, because that is the ordinary
  paragraph id and guessing otherwise would split one paper into two sources.
- The two extraction strategies no longer both emit the same paragraph when their source ids
  differ: de-duplication now also runs on the text.

R17 (6 checks) locks all four behaviours, including the lowercase case, which must **not** become
a source split. Regression **R1–R17 / 102 checks**.

## 1.3.5 — a wrong field type ended the run

Fuzzing the annotation file with the shapes a language model actually emits found three inputs that
raised `AttributeError` and exited 1 with a traceback: `"type": ["material"]`, `"type": 7`, and a
`label` written as a list. On this platform an execution failure is not a low score, it is no
result — so a one-line schema slip was worth zero, whatever the rest of the graph contained.

- `as_text()` coerces any field to text without trusting its type: a list gives its first non-empty
  string, a dict gives `label`/`name`/`value`/`text`, anything else `str()`. Applied to `canon`,
  `norm_type`, `norm_rel`, node `label`, edge endpoints and `quote`.
- A single evidence record written as an object instead of a one-element list is wrapped
  (`mentions` and `evidence`), and a `quote` written as a one-element list is read as that string.
- What is *not* forgiven: a quote that matches no paragraph still stops the run with exit 4, and a
  file with no nodes still exits 3. Coercion addresses the shape of a field, never its truth.

R16 (11 checks) locks all five shapes plus the two failures that must stay failures. Regression
**R1–R16 / 96 checks**.

## 1.3.4 — the case's own vocabulary was fatal

The case file states its `output_contract` in terms of `entities` and `relations`. An annotator
that reads `case.json` first therefore writes `entities`/`relations`, `from`/`to`, `relation` and
`name` — and the build step, which speaks `nodes`/`edges`, found no nodes and exited 3 with
"produced no nodes". One naming choice cost the whole case.

- `load_annotations` now accepts `entities`/`relations`/`relationships`/`triples`, `from`/`to`/
  `subject`/`object`, `relation`/`predicate`, `name`/`entity`, `kind`/`category`, and a bare JSON
  array of records tagged `kind` (a list, not an object — a third shape that used to fall through
  to the JSONL parser and yield nothing).
- Every rename is written to `graph["warnings"]` as `alias->field`, and printed. The rule this
  project already applies to type coercion applies here: adapting silently would hide a
  disagreement between the annotator and the schema.
- The guarantee is unchanged: quotes still have to match a paragraph, so a file that names the
  wrong corpus still fails (R15 keeps the canonical vocabulary warning-free, so the tolerance does
  not fire on well-formed input).

Regression **R1–R15 / 85 checks** (R15: 6). Checked by hand first: the challenge-vocabulary file
exited 3 before the change and produces 2 nodes / 1 edge after it.

## 1.3.3 — what the package looks like from the other side of an archive

Three packaging faults, none of which any functional test could see, because each one lives
outside the process the tests run in.

- **21 of 49 files were mode 600** — readable only by the account that wrote them. A skill
  installed by a different user would fail at `python3 scripts/prepare_case.py` with a permission
  error, on every case. All files are now 644, the two `.sh` entry points 755.
- **`run.sh` loses its execute bit when the platform repacks the bundle** (verified: the submitted
  ARM bundle carries it as `-rw-r--r--`). `SKILL.md` now says to call it as `bash run.sh`, never
  `./run.sh`, and states that every script also runs standalone.
- **`SKILL.md` called `python`**, which is not guaranteed to exist where `python3` does; all 17
  documented invocations now use `python3`. Step 0 also no longer assumes the case is at `/input`:
  it names the fallback when the task puts the files elsewhere.

`tests/selftest.py` gained a `[packaging]` block (6 checks): every file readable by another
account, shell entry points executable, no symlinks, every `$SKILL_DIR/scripts/*.py` quoted in
`SKILL.md` exists, no bare `python`, and `bash run.sh all` runs from an unrelated working
directory. Self-test 25 → **31**.

## 1.3.2 — a correct quote lost to a formatting difference

Found by sampling 120 sentences from the demo corpus and re-quoting each one the way a model
transcribes from a PDF: inserting a thousands separator, spacing the percent sign, replacing the
degree symbol, dropping superscripts, substituting ASCII for Unicode minus. Of 120 quotes:

- **digit grouping** (`1350` → `1,350`, and the reverse) was **rejected in both directions**, 5 of
  120 sentences. The gate's own numeric comparison split `1,350` into `1` and `350`, so a quote that
  agreed with the paper digit for digit failed as a "numeric mismatch". That is the worst kind of
  error for this task: a true quote discarded, coverage down, and the rejection message blames the
  number.
- **spacing-only differences** (`88.1%` → `88.1 %`) dropped to `fuzzy`, i.e. weak evidence, although
  nothing but whitespace differed.

Both are formatting, not wording. `verify_evidence.py` now builds a comparison key that drops
whitespace and thousands separators from quote and paragraph alike and requires every other
character to agree; a key match is `normalized` with score 1.0 and the paragraph's own span. The
numeric check runs on the same key, so `1,350` and `1350` agree while a changed digit does not:
re-running the perturbation bench still rejects **100%** of altered digits, and `1030` versus
`10^3` — a different notation for a different value — is still refused. A comma counts as a
separator only when a digit precedes it and exactly three digits follow, so `2,5-dimethoxy` and
`3, 4 and 5` keep theirs.

Cost of the change, stated: the gate is now blind to spacing and digit grouping in a way it was
not before, so the question is whether it still refuses what it must. It does — `verify-bench` is
unchanged after the edit (exact 100%, whitespace 100%, punctuation 100%, **digit 0%**, word 90%),
and the 120-sentence sample still rejects every altered digit — all 73 sentences that contain a
digit were rejected, the remaining 47 contain none — while accepting every
formatting-only rewrite. `R14` (9 checks) locks both directions of the acceptance and the three
rejections; regression is now **R1–R14 / 79 checks**.

## 1.3.1 — what a real two-paper run on this machine changed

The first end-to-end run with the model doing the extraction (two CC BY papers, 88 paragraphs) was
not a demo: it produced 21 nodes, 16 edges, 42 verbatim quotes and 6/7 answered queries, and it found
three things the synthetic corpus never would.

- The model wrote `increases` and `decreases` as relation types; the schema had no such names, so the
  edges were stored as `other`. Both are now part of the vocabulary (schema, `build_graph`,
  `SKILL.md`), with `condition` required to name the quantity.
- `NODE_TYPES` carried `finding`, which the schema did not. That node type would have produced a
  graph that `build_graph` accepted and the published schema rejected. `finding` now maps to
  `conclusion`.
- R11 gained a drift guard: the relation and node vocabularies must be identical in the schema, in
  `build_graph` and in the test. It failed immediately on `finding`, which is the point.
- The task's numeric question routed to `metric_compare` (per-source values with quotes) instead of a
  generic entity lookup, and "do the papers agree…" routes to the alignment query, which now reports
  the recorded conflicts **and** the open questions.
- Regression: **70 checks** (R11 grew by two).

## 1.3 — deduction pass: read the delivery contract, then fix what it exposes

Each change below answers a line of the challenge's delivery requirements rather than a hunch.

- **PDF input is now paragraph-located.** A text PDF used to normalise to a single 500-character
  block, so a PDF-based case would have bound every node and edge to one derived `d0001` — legal,
  and useless to review. Blocks are inferred (blank line, heading, sentence end followed by a new
  sentence, form feed), hyphenated line breaks are joined, back matter stops the body, and each
  block records `pdf_page` as a reading aid while the id stays a derived `d####`. References no
  longer become body text. R12 covers this on a real generated PDF.
- **Task questions are answered, not only structural ones.** `query_graph.py` reads the case task
  text, turns its questions into queries (`derived_from: "task"`, each recording the original
  question), routes "both papers"/"两篇" phrasing to the alignment query, and fills up with the four
  structural queries afterwards. A question the graph cannot ground comes back `undetermined` with
  the reason — the challenge asks for exactly that.
- **`keyword` is implemented.** It was listed among the query types and had no handler, so any
  keyword query returned "unknown query type". It now searches node names, relation conditions and
  the verified quotes, so a question about a term that never became a node still returns the
  passages that discuss it.
- **A rendered preview always exists.** `render_svg.py` draws `graph.svg` with the standard library
  and a deterministic layout; `render_png.py` remains the optional bitmap. The delivery contract
  asks for a rendered preview of the diagram, and producing one only when matplotlib happens to be
  installed was a gamble.
- **`extraction_mode` is recorded.** `graph.json` and `result.json` state whether the annotations
  came from the model or from the deterministic fallback, so a report cannot imply that the agent
  read the papers when it did not.
- **The manifest's `root` block no longer becomes a phantom source.** `corpus-manifest.json` carries
  a `root`/`manuscript` object describing the FIRST paper; read as a separate record it produced a
  third source holding the first paper's DOI — the exact mix-up the input revision forbids. It is
  merged into the matching source with a warning, and an orphan DOI is reported rather than silently
  attached.
- **`result.json.artifacts` lists files that exist.** `graph.json` was listed before it was written,
  so the field could claim a file that was missing; the list is resolved after the writes and now
  includes `graph.svg`.
- `SKILL.md` now tells the agent to start from the deterministic draft and improve it (≤12 requests
  per case against a budget of 64), and its description carries the Chinese task vocabulary
  (文献知识图谱、实体关系抽取、证据绑定) so the harness can match a Chinese task text.
- **The readable report states the run, not only the graph.** `graph_report.md` now opens with
  status, the reasons when it is not `success`, extraction mode, paragraphs kept, stage seconds and
  which validation checks failed. A reviewer who reads only that file can no longer see a tidy graph
  and miss that the run was partial.
- **The deterministic fallback types its candidates instead of parking them in `other`.** Suffix and
  acronym rules (metric/material/method/task/researcher, English and Chinese), a discourse-word
  stop list, and a rule that an edge needs at least one typed endpoint cut the demo corpus from 140
  nodes / 160 co-occurrence edges with 112 untyped to 91 nodes / 72 edges with 26 untyped; untyped
  singletons are dropped and the count is recorded as `dropped_untyped_singletons`. When the agent
  path is unavailable this is the graph that gets graded.
- **The quote gate is now measured against the obvious alternative.** `bench/run_ab.py verify-bench`
  applies naive substring, best-window similarity ≥ 0.90 and the gate to the same perturbed quotes:
  substring loses 100% of re-wrapped quotes, similarity certifies 100% of altered numbers, the gate
  keeps the first and rejects the second. The table is in `docs/GAIN.md` and regenerates in one
  command, which is the difference between claiming a method improvement and showing one.
- Regression set: **R1–R13, 68 checks** (R12 PDF blocks, R13 task-driven queries); `run.sh verify`
  runs both suites in ~15 s.

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
  installed and with a stdlib subset otherwise. 55 checks plus two runtime/budget assertions in R1.
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
