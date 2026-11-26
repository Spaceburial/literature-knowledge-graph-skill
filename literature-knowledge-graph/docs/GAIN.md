# Measured behaviour: curated extraction vs deterministic baseline

Same input case (`examples/demo_perovskite/input`, two real papers), same downstream scripts;
only the extraction step differs. Figures are from actual runs.

| metric | baseline (`heuristic_extract.py`) | curated close reading |
|---|---|---|
| nodes | 140 | 35 |
| nodes typed `other` | 112 (80%) | 2 (6%) |
| edges | 92 | 34 |
| distinct node types | 5 | 7 |
| distinct relation types | 5 | 9 |
| merge decisions recorded | 0 | 4 |
| cross-paper conflicts recorded | 0 | 4 |
| unresolved edge endpoints | 68 | 0 |
| queries answered | 4/4 | 6/6 |

What the numbers mean, honestly:

- The baseline is **not** a strawman at the level of coverage; it produces more nodes and edges.
  It loses on **precision and provenance of structure**: four fifths of its nodes are untyped
  noun phrases, it makes no alias decisions, and 68 edge endpoints do not resolve to a node.
  So it cannot answer “which items are claimed to outperform others, under what condition”, and
  it cannot tell a shared concept from a shared sample.
- The curated graph is smaller because it extracts the claims the text actually makes, with a
  condition on each. Its value is that every one of the 34 edges is a real sentence-level
  assertion with a located quote, and the four cross-paper conflicts are explicit.
- The gain that matters is the *absence of silent errors*: 0 rejected quotes in both runs
  (the verifier is the same), but the baseline would have merged or dropped entities without a
  record, whereas the curated path leaves a merge/conflict trail a reviewer can check.

Reproduce:

```bash
python scripts/run_all.py --case-dir examples/demo_perovskite/input --work /tmp/base --out /tmp/base_out
python scripts/run_all.py --case-dir examples/demo_perovskite/input --work /tmp/cur \
       --annotations examples/demo_perovskite/annotations.example.json --out /tmp/cur_out
```
