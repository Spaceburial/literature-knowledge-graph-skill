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
