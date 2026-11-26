# Submission checklist — where each requirement is met

| Requirement (challenge rubric) | Where it is satisfied | How to verify |
|---|---|---|
| Skill body `SKILL.md` with purpose, applicability, invocation, I/O, error handling | `SKILL.md` | read sections "When to use / not use", "Procedure", "Error handling" |
| Runnable scripts and resources, with versions/paths/conditions | `scripts/`, `run.sh`, `README.md` §Requirements; Python 3.9+, stdlib only | `python tests/selftest.py` |
| Usage and method documentation | `docs/METHOD.md`, `docs/LIMITATIONS.md`, `README.md` | — |
| Minimal call example (marked as example) | `SKILL.md` §Minimal example; `examples/demo_perovskite/` (input, annotations, output) | run the three commands in that section |
| Structured per-case result with input id, main result, evidence, status, uncertainty | `scripts/finalize.py` → `/app/output/result.json` (`case_id`, `status`, `summary`, `evidence_index`, `uncertainty`, `validation`) | `jq .status /app/output/result.json` |
| Evidence: page/paragraph/figure/field location, unreported and uncertain items | `evidence.csv`, `result.json.evidence_index`, `uncertainty[]` | all rows carry `source_id`,`paragraph_id`,`quote`,`match` |
| Entities are real spans, not plausible concepts | `verify_evidence.py` rejects any quote not found in the cited paragraph | `result.json.validation.checks[1]` |
| Relation type, direction, condition consistent with text | `build_graph.py` type normalisation + `condition`/`direction_note` on every edge | `edges.csv` columns `condition`, `direction_note` |
| Cross-paper alias handling without wrong merges | `merge_candidates` → `merge_log`; type-mismatch merges refused | `graph_report.md` §Merge decisions |
| Same-name / different-object handling | `uncertainty` kind `cross_paper_generic_term`; `source_conflicts` `sample_identity_conflict` | `result.json.uncertainty` |
| ≥3 real queries with subgraph + evidence + undetermined | `query_graph.py` (7 types); 6 executed in the example | `queries_result.json` |
| Nodes/edges trace back to passage | `evidence_trace` query; `evidence.csv` `context` column | `query_graph.py --type evidence_trace --name E0001` |
| Incremental/new-paper handling | `scripts/add_paper.py` preserves all existing `N/E` ids, merges by canonical key+type, unions evidence, logs added/merged/conflicts; self-test asserts incremental == full build | `python tests/selftest.py` section [3] |
| Robustness: missing files, unparseable PDF, same-name, evidence conflict, empty query | `prepare_case.py` warnings; `finalize.py` status; `query_graph.py` `undetermined` | run the PDF/Markdown and single-paper cases in `docs/METHOD.md` |
| Documentation completeness / reuse | `README.md`, `docs/`, `schema/`, `templates/` | — |
| GitHub public link (bonus 5) | `GITHUB_URL.txt` — first line `https://github.com/Spaceburial/literature-knowledge-graph-skill/tree/main/literature-knowledge-graph`, second line `literature-knowledge-graph`; the same directory is published in that public repository | open the link in a logged-out browser, or `curl -s https://api.github.com/repos/Spaceburial/literature-knowledge-graph-skill` → `"visibility": "public"` |

## Honest limits of this submission

- The three official cases are provided by the platform at evaluation time; the worked example
  here is a real two-paper case used for validation, not a stand-in for them.
- The quantitative comparison in `docs/GAIN.md` is curated-vs-heuristic on the same example,
  not curated-vs-base-agent on the hidden cases; the platform measures the latter.
- The public repository holds exactly this directory; anonymous access to the link was checked at
  submission time, and the 5-point bonus depends on it staying open.
