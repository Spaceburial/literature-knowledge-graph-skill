# Per-window extraction prompt (copy-paste for the reading step)

Use this prompt for each window of paragraphs (one section or ~2500 words). Replace the
`<...>` fields. Ask for JSON only; then merge the JSON blocks into `annotations.json`.

---

You are extracting a knowledge graph from one research paper. Below is a numbered list of
paragraphs, each as `[paragraph_id] (section) text`. Work only from this text.

Rules:
1. Return JSON with keys `nodes` and `edges` (see schema below). No prose outside the JSON.
2. `quote` MUST be an exact substring of the paragraph you cite, 8–300 characters. Copy it,
   do not paraphrase. If you cannot copy an exact substring, do not emit the item.
3. `attribution`: `"self"` if the sentence reports the authors' own work ("we", "this study",
   "our"), `"other"` if it summarises a cited/previous study.
4. Entity types: researcher, material, method, task, metric, conclusion, dataset, model, other.
5. Relation types: uses, compares, outperforms, supports, contradicts, measures, evaluated_on,
   reports, improves, part_of, produces, based_on. Direction is source→target.
6. `outperforms` requires an explicit comparison in the text plus a metric; put the metric,
   sample and condition in `condition`. Co-occurrence alone is not a relation.
7. Do not merge a generic class with a specific instance. Do not merge this paper's samples or
   numbers with another paper's. If a value appears only in a figure, omit it and list it under
   `uncertainty` as `value_not_reported_in_text`.
8. Keep labels short and canonical; list surface variants in `aliases`.

Output shape:
```json
{"nodes":[{"label":"","type":"","aliases":[],"mentions":[{"source_id":"","paragraph_id":"","quote":"","attribution":""}]}],
 "edges":[{"source_label":"","target_label":"","type":"","condition":"","direction_note":"","evidence":[{"source_id":"","paragraph_id":"","quote":"","attribution":""}]}],
 "uncertainty":[{"kind":"","detail":"","items":[]}]}
```

`entities`/`relations` and `from`/`to`/`relation` are also accepted in place of `nodes`/`edges` and
`source_label`/`target_label`/`type` (the build renames them and records the rename in
`graph["warnings"]`), so a file written in the case's own vocabulary is not wasted.

source_id = `<P1 or P2>`. Paragraphs:

<[pid] (section) text ...>
