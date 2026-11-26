# Budget model and the `--max-paragraphs` threshold

The run contract is 64 model requests, 900 s of wall time, 16384 tokens per response. This note
separates what was measured from what is a stated parameter, and gives the rule for capping input.

## What is measured

Pipeline cost on the worked example (141 paragraphs, 166,815 characters, 2 papers), three repeats:

| stage | wall time |
|---|---|
| `build_graph.py` + `query_graph.py` + `export_graph.py` + `finalize.py` | 0.5–0.7 s total |
| `prepare_case.py` | < 0.2 s |

So the scripts are not the budget. **The budget is spent on the model reading the paragraphs**, and
that is what the cap has to control.

## What is modelled, and with which parameters

| quantity | model | status |
|---|---|---|
| tokens in one window | `window_chars / 4` | approximation (chars/4), not tokenised |
| reading windows | `ceil(total_chars / window_chars)` | arithmetic |
| model requests | `windows + 5` (query set, repair pass, summary) | stated overhead, not measured |
| wall time | `windows × seconds_per_request + 60 s` | `seconds_per_request` is a **parameter**, not a measurement |

`seconds_per_request` is the one number this document cannot measure: it depends on the model and
the harness. The tables below therefore sweep it rather than assert it.

## Window size sweep (141-paragraph demo, 20 s per request)

| window (chars) | est. tokens per call | windows | requests | wall model | token headroom |
|---:|---:|---:|---:|---:|---:|
| 4,000 | 1,000 | 42 | 47 | 900 s (at the limit) | 15,384 |
| 6,000 | 1,500 | 28 | 33 | 620 s | 14,884 |
| 8,000 | 2,000 | 21 | 26 | 480 s | 14,384 |

All three fit 64 requests; only the 4,000-character window sits exactly on the 900 s edge. **Default
window: 6,000 characters** (1,500 tokens, ~9× headroom against the per-response cap).

## Time sensitivity — where the cap starts to matter

| seconds per request | windows allowed by 900 s | paragraphs that fit | recommended `--max-paragraphs` |
|---:|---:|---:|---:|
| 20 | 42 | 141 (all) | 141 → leave uncapped |
| 30 | 28 | 141 (all) | 141 → leave uncapped |
| 45 | 18 | 78 | **78** |

Reproduce any row:

```bash
python3 bench/run_ab.py budget --case-dir examples/demo_perovskite/input \
        --seconds-per-request 45 --json-out /tmp/budget.json
```

## The rule

1. **Default: do not cap.** A two-paper case of ~140 paragraphs at a 6,000-character window needs
   ~33 requests and fits the contract with margin.
2. **Cap when** paragraphs × average length exceeds ~140 paragraphs, or when the harness is slower
   than ~30 s per request. Then set
   `--max-paragraphs ≈ floor((900 − 60) / seconds_per_request) × 5` for this corpus
   (≈5 paragraphs per 6,000-character window at 1,183 characters per paragraph).
3. **A cap is a limitation, not a fix.** `finalize.py` turns truncation into `status="partial"` with
   the dropped count per paper as the first reason. Never present a truncated graph as complete.

## Why this is not over-engineering

The alternative to a recorded cap is an unrecorded overrun. In the same challenge, 691 of 1645
attempts never produced a score because execution failed; a run that dies at 900 s leaves nothing to
grade. A capped run that says which paragraphs it did not read is worth more than an uncapped run
that produces nothing.

## The warning you get without asking

`prepare_case.py` estimates the reading cost at normalisation time and warns when the corpus needs
more than 56 six-thousand-character windows (64 requests minus ~5 of overhead):

```
! reading budget: 2831940 characters is about 472 windows of 6,000 chars (plus ~5 requests of
  overhead) against a limit of 64 requests / 900 s. Pass --max-paragraphs or --max-chars to cap
  the reading, and report the truncation.
```

The demo (166,815 characters, 28 windows) stays silent. The warning is a reason to choose a cap
deliberately, not a truncation: the input is kept whole unless `--max-paragraphs`/`--max-chars`
is passed, and a truncated run reports `partial` with the cap in `status_reasons`.
