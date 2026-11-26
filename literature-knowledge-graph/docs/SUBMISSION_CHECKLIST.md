# Submission checklist — where each requirement is met

| Requirement (challenge rubric) | Where it is satisfied | How to verify |
|---|---|---|
| Skill body `SKILL.md` with purpose, applicability, invocation, I/O, error handling | `SKILL.md` | read sections "When to use / not use", "Procedure", "Error handling" |
| Runnable scripts and resources, with versions/paths/conditions | `scripts/`, `run.sh`, `README.md` §Requirements; Python 3.9+, stdlib only | `python tests/selftest.py` |
| Usage and method documentation | `docs/METHOD.md`, `docs/LIMITATIONS.md`, `README.md` | — |
| Minimal call example (marked as example) | `SKILL.md` §Minimal example; `examples/demo_perovskite/` (input, annotations, output) | run the three commands in that section |
| Structured per-case result with input id, main result, evidence, status, uncertainty | `scripts/finalize.py` → `/app/output/result.json` (`case_id`, `status`, `summary`, `evidence_index`, `uncertainty`, `validation`) | `jq .status /app/output/result.json` |
| Quote integrity under a single edited digit | `verify_evidence.py` numeric guard: numbers in a quote must equal those of the matched window | `python3 tests/regression/regression.py R8` |
| Evidence: page/paragraph/figure/field location, unreported and uncertain items | `evidence.csv`, `result.json.evidence_index`, `uncertainty[]` | all rows carry `source_id`,`paragraph_id`,`quote`,`match` |
| Entities are real spans, not plausible concepts | `verify_evidence.py` rejects any quote not found in the cited paragraph | `result.json.validation.checks[1]` |
| Relation type, direction, condition consistent with text | `build_graph.py` type normalisation + `condition`/`direction_note` on every edge | `edges.csv` columns `condition`, `direction_note` |
| Cross-paper alias handling without wrong merges | `merge_candidates` → `merge_log`; type-mismatch merges refused | `graph_report.md` §Merge decisions |
| Same-name / different-object handling | `uncertainty` kind `cross_paper_generic_term`; `source_conflicts` `sample_identity_conflict` | `result.json.uncertainty` |
| ≥3 real queries with subgraph + evidence + undetermined | `query_graph.py` (7 types); 6 executed in the example | `queries_result.json` |
| Nodes/edges trace back to passage | `evidence_trace` query; `evidence.csv` `context` column | `query_graph.py --type evidence_trace --name E0001` |
| Incremental/new-paper handling | `scripts/add_paper.py` preserves all existing `N/E` ids, merges by canonical key+type, unions evidence, logs added/merged/conflicts; self-test asserts incremental == full build | `python tests/selftest.py` section [3] |
| Robustness: missing files, unparseable PDF, same-name, evidence conflict, empty query | `prepare_case.py` warnings; `finalize.py` status; `query_graph.py` `undetermined` | run the PDF/Markdown and single-paper cases in `docs/METHOD.md` |
| Artifacts conform to the declared schema | `schema/graph.schema.json` is `anyOf` over the annotation and graph shapes; every quote is 8–300 characters | `python3 tests/regression/regression.py R11` |
| Documentation completeness / reuse | `README.md` (three-command quickstart, "Bring your own corpus" with a verified minimal `annotations.json`), `docs/`, `schema/`, `templates/` | `docs/USABILITY.md` — two unassisted-reader rounds and what each one needed |
| Failures are loud, never silent | empty corpus, missing annotations, node-less annotations, missing query file each exit non-zero with a route forward; `run_all` aborts on a failed stage | `python3 tests/regression/regression.py R7 R9` |
| Measured gain (two conditions, same input, 3 repeats) | `bench/run_ab.py` + `bench/metrics.py` → `docs/GAIN.md` | `python3 bench/run_ab.py ab --case-dir examples/demo_perovskite/input --annotations examples/demo_perovskite/annotations.example.json --queries examples/demo_perovskite/queries.example.json --repeats 3 --out /tmp/ab` |
| Budget guard against 64 requests / 900 s | `prepare_case.py --max-paragraphs/--max-chars` → `finalize.py` partial + reason; threshold derivation in `docs/BUDGET.md` | `python3 bench/run_ab.py budget --case-dir examples/demo_perovskite/input` |
| GitHub public link (bonus 5) | `GITHUB_URL.txt` — first line `https://github.com/Spaceburial/literature-knowledge-graph-skill/tree/main/literature-knowledge-graph`, second line `literature-knowledge-graph`; the same directory is published in that public repository | open the link in a logged-out browser, or `curl -s https://api.github.com/repos/Spaceburial/literature-knowledge-graph-skill` → `"visibility": "public"` |

## Honest limits of this submission

- The three official cases are provided by the platform at evaluation time; the worked example
  here is a real two-paper case used for validation, not a stand-in for them.
- The quantitative comparison in `docs/GAIN.md` is a pipeline-level control — same input, same
  scripts, only the extraction step differs (deterministic baseline vs Skill rules) — not a
  base-agent vs skill-agent comparison on the hidden cases. `bench/run_ab.py` accepts two commands
  so such a comparison can be run wherever the models are available; the platform measures it there.
- `docs/USABILITY.md` records two rounds of first-contact testing by a reader with no project
  context. The reader was a fresh session of the same model family, not a human panel; it is a
  lower bound on real friction, and both rounds found failures a reader cannot see from the docs
  alone (a stale default path, a merge log that hid applied decisions).
- The public repository holds exactly this directory; anonymous access to the link was checked at
  submission time, and the 5-point bonus depends on it staying open.
