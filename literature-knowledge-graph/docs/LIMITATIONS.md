# Limitations

- **Lexical verification.** A correct paraphrase is rejected because it is not a substring.
  This is intentional (it blocks invented quotes) but it pushes work onto exact copying. A quote
  that reaches 0.90 similarity is accepted as `fuzzy` and marked weak evidence; the stored text is
  then the submitted string, so a fuzzy match is *not* proof of a verbatim quote — only an exact or
  normalized match is. Numbers are checked separately: a quote whose numeric tokens differ from the
  matched window is rejected outright, whatever its similarity. For a fuzzy record the
  paragraph's own wording is kept in `matched_text`, so the difference from the submitted
  quote stays visible.
- **Paragraph granularity.** Long paragraphs are not split; a quote must fit inside one
  paragraph and be ≤300 characters after folding.
- **Extraction quality is bounded by the reading step.** The deterministic fallback produces
  many untyped `other` nodes and does not align entities; treat it as a baseline only.
- **No figure/supplement mining.** Values shown only in plots or supplementary files are
  reported as `value_not_reported_in_text`, not extracted.
- **JATS parsing is minimal.** `prepare_case.py` handles `sec/title/p`; complex tables,
  footnotes and nested lists are flattened or skipped. The original XML is kept for cross-check.
- **Alias merging is conservative.** Abbreviation/full-form and case/hyphen variants are
  merged; chemically distinct names and generic-vs-instance pairs are deliberately left
  separate, so the graph may contain two nodes a domain expert would merge. The merge log
  makes each case visible and correctable.
- **Language.** Rules are written for English papers; Chinese surface forms are accepted as
  strings but abbreviation/normalisation heuristics are English-oriented.
- **Not a truth judgement.** `supports`/`contradicts` record what the papers assert, not which
  claim is correct.
