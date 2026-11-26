# Usability record — three first-contact rounds

The plan for this work asked for one test: hand the package to a reader with no project context,
give them only `README.md`, and write down where they get stuck. This file records three rounds,
because the first two changed the package enough that the earlier findings no longer applied.

**Protocol (all rounds).** A fresh session of the same model family, told to play a materials
researcher who has just downloaded an unknown directory. It may read `README.md` first; it may open
source files only after the README has failed it, and must log each such escalation as a
documentation gap. It works on a copy, invents its own two-paper corpus, and reports a step table
with timestamps, exit codes and real output. No round was given any project context, and none of
them saw the test plan of the previous round.

**What this test is not.** The reader is a language model, not a human panel: it does not tire, it
reads code fluently, and it recovers from bad messages faster than a researcher would. Its
timings are a lower bound on friction, and its successes are an upper bound on usability.

## Round 1 — the demo worked, the real task did not

- Demo quickstart: 18 s from commands to a graph and an answered query, output matching the README.
- Own two papers: **dead end** from the README alone. `prepare` reported `paragraphs=0` and exited
  0 with five warnings; `build` then reported `0 nodes` and exited 0. The reader concluded the
  tool "works but produces nothing", and only recovered by reading `prepare_case.py`.
- A quote with one digit changed (`21.3%` → `21.8%`) came back `verified` at fuzzy similarity 0.905.
- `bash run.sh all` — described in the README as the one-command form — swallowed the package's own
  `README.md` and `SKILL.md` as the corpus and wrote to `/app/work`.

Round 1 produced: the "Bring your own corpus" contract, the numeric guard in `verify_evidence.py`,
non-zero exits for an empty corpus / missing annotations / missing query file, `--case-dir` as a
required argument, and regression cases R7 and R8.

## Round 2 — the contract worked, three silences remained

- Own corpus from the README alone: graph in 26 s via `run.sh all`, an answered query with its
  quote at 28 s, a fully verified `status="success"` result at 1 min 09 s after hand-writing
  annotations. Inside the 30-minute target.
- `build` **with no `--annotations`** read a stale `/app/work/annotations.json` from an earlier run
  and printed `78 nodes, 7 edges` with exit 0.
- The demo's merge log held only the four `kept_separate` decisions; the five applied merges were
  in the graph but in no log entry.
- The README said "three commands" over a five-command block, quoted an answer block that print did
  not produce, and carried stale suite sizes.

Round 2 produced: the annotations default derived from the bundle's directory, the complete merge
log, the three-command quickstart, and a real output sample.

## Round 3 — the failures are loud, except where nothing was verified

- Own two papers: 2 nodes / 1 edge from the README's own snippets in under ten minutes, the
  `metric_compare` query returning `21.3%` with its quote; `-v`, all seven query types, the
  `partial` rule, the 40-character rule and the error paths all behaved as documented.
- Still silent: a bundle paired with a **present but unrelated** `annotations.json` produced
  `78 nodes, 7 edges`, 0 verified, 117 rejected quotes, exit 0; a query answered with
  `n_evidence: 0` from evidence-rejected nodes; and `status="success"` printed beside a failed
  entry of `validation.checks` (plain-text ids were `t####`, which the derived-id check rejects).

Round 3 produced: exit 4 when no item's quote is found in the bundle, `partial` plus a named
reason whenever a validation check fails, plain-text ids normalised to `d####`, and R9.

## Frictions that remain, with the reason each was left

- **Fuzzy matching is still recall-oriented.** A non-numeric paraphrase at ≥0.90 similarity is
  accepted and marked weak, and the stored quote is the submitted string, not the paragraph's. The
  number guard closes the case that matters for data; tightening further would reject legitimate
  hyphenation and case variants.
- **`source_id` can still be inferred.** With no manifest and no `source_id`, the id comes from the
  file stem. That is a guess, and `finalize` treats missing DOI/title as a `partial` reason rather
  than hiding it.
- **`result.json` duplicates nodes and edges** under `graph`, `nodes`/`edges` and
  `entities`/`relations` for contract compatibility; the copies are identical, and the file is
  large for a small graph.
- **A case with one paper can never reach `success`** by design: a cross-paper graph needs two
  sources with evidence, so such a run reports `partial` and says why.
- **No human test.** A single researcher with a stopwatch would find different things — most
  likely the jargon (`kept_separate`, `evidence_status`, `output_contract`) that all three rounds
  learned from the schema rather than the README.
