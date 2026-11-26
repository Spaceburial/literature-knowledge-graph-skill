# Method

## Problem

Given a handful of papers as paragraph records, produce a graph in which every node and edge
can be re-checked against the text, entities are aligned across papers without collapsing
distinct samples, and the graph answers real questions. The hard part is not extracting
triples; it is **not asserting things the text does not say**, and **not merging things that
only look alike**.

## Pipeline

1. **Normalise (`prepare_case.py`).** Any of JSON paragraph lists, id-keyed dicts, aggregate
   `material.json` plus per-paper files, or JATS XML is flattened to
   `paragraphs[] = {source_id, paragraph_id, section, text, id_derived, order_in_source}`.
   Per-paper files are attached to the manifest's real `source_id` via the paper's `role`, not
   to the literal string "primary"/"secondary". Duplicate paragraphs across the aggregate and
   per-paper files are de-duplicated by `(source_id, paragraph_id)`; differing text is reported,
   not silently chosen. `case_id` and `output_contract` are read from `case.json`, falling back
   to `corpus-manifest.json`.

2. **Extract (agent + prompt).** The agent reads paragraphs and emits nodes/edges with a
   verbatim quote per item. `templates/extraction_prompt.md` constrains the model to copy exact
   substrings and to separate `self` from `other` attribution. A deterministic fallback
   (`heuristic_extract.py`) exists only so the pipeline is never empty; its output is labelled
   as a baseline.

3. **Verify (`verify_evidence.py`).** Every quote is located in the cited paragraph by
   whitespace folding (exact), Unicode/quote/dash folding (normalized), or a ≥0.90
   similarity sliding window (fuzzy, flagged weak). Failures are rejected and logged. This is
   the mechanism that makes “回得去” (traceable back to the text) enforceable rather than
   aspirational: an invented quote cannot pass.

4. **Build (`build_graph.py`).** Canonical keys merge identical surfaces. Alias lists and
   annotated `merge_candidates` merge synonyms, but a merge is refused and logged when the two
   nodes have different types. Ids are assigned in first-appearance order (`N0001`, `E0001`).
   Relation types are normalised through a synonym table. Conflicts are detected
   (support vs contradict on one pair; bidirectional `outperforms`) and annotated
   cross-paper disagreements are appended with both quotes. Nodes/edges with no verified quote
   are kept but marked `unverified` and listed in `uncertainty` — never presented as supported.

5. **Query (`query_graph.py`).** Seven query types. Each answer separates `answered`,
   `partial` and `undetermined`, carries evidence, and returns `candidates` when a surface is
   ambiguous. `metric_compare` lists values per source/paragraph and explicitly refuses to
   aggregate across conditions.

6. **Export/finalise.** `graph.mmd`/`graphml`/CSV for reuse; `result.json` for grading, with a
   documented alias table mapping each declared `output_contract` field onto the canonical
   block, plus `validation.checks` and an honest status.

## Key assumptions

- `paragraph_id` is the provider's JATS id; when absent a derived id `d####` is generated and
  flagged. **No PDF pages are asserted**, because the contract supplies none.
- Inline formulas may be linearised in the source; they are quoted as given and never
  “corrected”.
- Numeric values are quoted, never inferred from figures; a value present only in a plot is
  recorded under `uncertainty`.
- Two papers sharing a method or material **name** do not thereby share a sample, a dataset or
  an experimental condition.

## Why this design

The failure modes that matter for a literature graph are silent: a plausible triple with no
quote, an alias merged into the wrong object, a cross-study number averaged into a fake
consensus. Each is addressed by a mechanism that leaves a record — a rejection log, a merge
basis, a conflict entry — so a reader can audit the graph instead of trusting it.
