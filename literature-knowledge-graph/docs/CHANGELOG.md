# Changelog

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
