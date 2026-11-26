# Changelog

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
