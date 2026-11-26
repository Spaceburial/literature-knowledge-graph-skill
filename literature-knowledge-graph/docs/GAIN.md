# Measured behaviour: Skill rules vs no rules, same input

Two conditions, one input (`examples/demo_perovskite/input`, two real papers, 141 paragraphs), same
normalized bundle, same downstream scripts. Only the extraction step differs:

- **baseline** — `heuristic_extract.py`: deterministic, no Skill rules, no alias reasoning, no
  attribution, no merge decisions.
- **treatment** — annotations written under `SKILL.md`: typed entities, relations with condition,
  verbatim evidence, explicit merge/keep-separate decisions.

Three repeats per condition; the table reports medians. Produced by
`python3 bench/run_ab.py ab …`; raw rows are in `ab_report.json` next to the report.

| metric | baseline (no Skill rules) | treatment (Skill rules) |
|---|---:|---:|
| status | partial | success |
| nodes | 140 | 35 |
| edges | 92 | 34 |
| typed share (type ≠ `other`) | 0.200 | 0.943 |
| distinct node types | 5 | 7 |
| distinct relation types | 5 | 9 |
| nodes with verified evidence | 140 | 35 |
| edges with verified evidence | 92 | 34 |
| evidence coverage | 1.00 | 1.00 |
| unresolved edge endpoints | 68 | 0 |
| merge decisions recorded | 0 | 9 |
| kept-separate decisions | 0 | 4 |
| conflicts recorded | 68 | 4 |
| queries answered (of 6) | 6 | 6 |
| query hit rate | 1.00 | 1.00 |
| wall time | 0.7 s | 0.5 s |

## What the numbers say

- The baseline is **not** a strawman on volume: it emits four times as many nodes and nearly three
  times as many edges. It loses on **structure and provenance**: four fifths of its nodes are
  untyped noun phrases, it makes no alias decision, and 68 candidate edges name an endpoint that
  resolves to no node — those edges are dropped, and the run now reports `partial` instead of
  hiding the loss behind `success`.
- The treatment graph is smaller because it carries only claims the text makes, each with its
  condition. Its two-to-four conflicts are the cross-paper ones that matter (`non_comparable_efficiency`,
  sample-identity differences), not 68 dangling endpoints.
- Both runs verify 100% of what they keep. The difference is therefore not "which one has evidence"
  but **what counts as an answer**: a typed, conditioned, merge-decided graph, or a bag of noun
  phrases that cannot answer "what is claimed to outperform what, under which condition".

## Claim limit

This is a **pipeline-level control** on one demo case: it isolates the extraction step, runs offline,
and reproduces for free. It is **not** the platform's base-agent vs skill-agent comparison, and must
not be quoted as that. For an agent-level comparison, point either condition at a command that writes
`annotations.json`:

```bash
python3 bench/run_ab.py ab --case-dir /input \
        --baseline-cmd  'python3 my_base_agent.py  --bundle {bundle} --out {out}' \
        --treatment-cmd 'python3 my_skill_agent.py --bundle {bundle} --out {out}' \
        --queries /input/queries.json --repeats 3 --out /tmp/ab_agent
```

## Reproduce

```bash
python3 bench/run_ab.py ab \
    --case-dir examples/demo_perovskite/input \
    --annotations examples/demo_perovskite/annotations.example.json \
    --queries examples/demo_perovskite/queries.example.json \
    --repeats 3 --out /tmp/ab
python3 bench/metrics.py --run-dir /tmp/ab/treatment/rep1/out --work-dir /tmp/ab/treatment/rep1/work
```

## Method improvement, measured: the quote gate against plain matching

The claim "our verification is stricter than substring matching" is only worth something with
numbers. `bench/run_ab.py verify-bench` derives five perturbations from the case's own paragraphs —
each a real sentence, altered in exactly one way the label names — and applies three rules to the
same text with the same window scan: naive substring, best-window similarity ≥ 0.90, and this
skill's gate (similarity plus an exact comparison of every number in the window).

| perturbation | n | naive substring | similarity ≥ 0.90 | this skill's gate |
|---|---:|---:|---:|---:|
| exact quote | 40 | 100% | 100% | 100% |
| extra whitespace | 40 | 0% | 100% | 100% |
| terminal punctuation changed | 40 | 0% | 100% | 100% |
| one digit changed | 24 | 0% | **100%** | **0%** |
| one word replaced | 40 | 0% | 95% | 90% |

Two things follow. Substring matching throws away 100% of quotes whose line wrapping or closing
punctuation the agent normalised — real quotes, lost. Similarity matching recovers them and also
certifies **every** quote whose number was altered, which is the failure the challenge warns about
("关键结果回到原文证据"). Adding the numeric comparison keeps the recovery and removes that
acceptance. The `word` row is honest about the cost: a paraphrase with unchanged numbers is still
accepted, at 0.90–0.95 similarity, and is stored as `match="fuzzy"` with the paragraph's own wording
in `matched_text` so a reviewer can see that it is not verbatim.

Reproduce:

```bash
python3 bench/run_ab.py verify-bench --case-dir examples/demo_perovskite/input
```

## A real two-paper run on this machine, against the same questions without the skill

The demo above is a synthetic corpus. This section is a run on two published open-access papers,
with the extraction step done by the model (not by the deterministic extractor), which is the path
the challenge actually exercises:

| | value |
|---|---|
| P1 | *Activation-Induced Turbostratic Ordering in pDCPD-Derived Hard Carbon*, DOI 10.1002/advs.78311, CC BY 4.0, 43 body paragraphs |
| P2 | *PET Waste-Derived Hard Carbon with Superior Rate Capability for Sodium-Ion Battery Anodes*, DOI 10.3390/ma19122457, CC BY 4.0, 44 body paragraphs |
| input shape | the documented revision: `case.json`, `task.md`, `corpus-manifest.json` (with a `root` block), `material.json` as an index, per-paper JSON **and** the publisher XML |
| normalisation | 88 paragraphs, provider ids kept, 12 back-matter blocks skipped, root block merged into P1, no phantom source |
| extraction | model close reading, 42 evidence items, `extraction_mode="agent"` |
| build | 21 nodes, 16 edges, 8 merge decisions (5 merged, 3 kept separate), 2 cross-paper conflicts, 7 uncertainty entries |
| verification | 42/42 quotes located verbatim; 0 rejected |
| queries | 7 executed, 6 answered, 1 undetermined (no `outperforms` edge exists) |
| result | `status=success`, coverage 1.0, all 6 declared `output_contract` fields present |

The same case and the same four task questions answered without the skill (base-agent condition, one
prose answer, 247 words, written by the same model):

| metric | base agent | this skill |
|---|---:|---:|
| task questions answered | 4 / 4 | 4 / 4 |
| claims bound to `source_id + paragraph_id` + verbatim quote | 0 | **42** |
| node / edge records | 0 | 21 / 16 |
| merge decisions with a written basis | 0 | 8 |
| cross-paper conflicts / open questions recorded | 0 | 2 / 7 |
| numeric values listed per source without pooling | no (prose mixes both) | 4 records, both sources |
| machine-queryable afterwards | no | 7 queries over `graph.json` |

Two limits on that table, stated rather than implied. The prose answer is not wrong — it is a
reasonable answer to the questions — so the difference is not "correct vs incorrect" but "auditable
vs not": nothing in it can be traced back to a paragraph without re-reading the papers. And it is a
self-run comparison written by the same model in both conditions, **not** the platform's whiteboard;
the challenge supplies the whiteboard itself, and this table does not stand in for it.

The run also changed the skill, which is the point of doing it: the model wrote `increases` and
`decreases` as relation types, the schema coerced them to `other`, and the schema now carries them
(they are ordinary measurement relations, and the challenge's relation list is explicitly a set of
examples). Without the real run that loss would have stayed invisible.
