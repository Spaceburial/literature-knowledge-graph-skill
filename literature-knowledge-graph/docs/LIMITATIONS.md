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
- **JATS parsing is minimal.** `prepare_case.py` handles `sec/title/p`, keeps inline formatting
  from splitting tokens (`MAPbI<sub>3</sub>` → `MAPbI3`) and drops back matter by section title
  (author contributions, funding, competing interests, data availability, acknowledgements,
  footnotes), reporting the count. Complex tables are flattened to their text, display equations
  become plain text, and lists are not reconstructed. The original XML is kept for cross-check.
  On two real PMC articles (282 KB and 217 KB) the reader produced 166 body paragraphs and left
  out 6 back-matter blocks.
- **Alias merging is conservative.** Abbreviation/full-form and case/hyphen variants are
  merged; chemically distinct names and generic-vs-instance pairs are deliberately left
  separate, so the graph may contain two nodes a domain expert would merge. The merge log
  makes each case visible and correctable.
- **Language.** Entity and relation rules are written for English papers. Chinese text is parsed,
  quoted and verified like any other string, and the fallback extractor now proposes CJK phrase
  candidates (punctuation-delimited runs, stop-word filtered) instead of returning nothing — but
  relation detection in the fallback stays English-lexicon based, so a Chinese corpus read by the
  fallback yields nodes with few edges. The agent reading path is language-agnostic.
- **Not a truth judgement.** `supports`/`contradicts` record what the papers assert, not which
  claim is correct.

## PDF paragraph boundaries are inferred

A PDF carries no paragraph ids and often no blank lines. `prepare_case.py` infers block boundaries
from blank lines, headings, a sentence-final line followed by a new sentence, and page breaks. The
inference is good on ordinary single-column body text and on the layouts in R12; it can over-split
dense two-column text or under-split a page whose lines all end mid-sentence. Whatever the split,
the id is a derived `d####` and `pdf_page` is recorded beside it as a reading aid — never as the
paragraph id, and never presented as the publisher's location. When a JATS or JSON paragraph set is
available for the same paper, prefer it: the provider ids are exact.
