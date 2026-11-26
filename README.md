# literature-knowledge-graph

A Bohrium Skill that turns a small corpus of research papers into an evidence-bound, queryable
knowledge graph. Every node and edge carries `source_id` + `paragraph_id` + a verbatim quote;
aliases are aligned across papers with explicit merge / non-merge records; at least three
queries are executed with evidence and an explicit `undetermined` branch.

- Skill: [`literature-knowledge-graph/SKILL.md`](literature-knowledge-graph/SKILL.md)
- Worked example (two real open-access papers): [`literature-knowledge-graph/examples/demo_perovskite/`](literature-knowledge-graph/examples/demo_perovskite/)
- Self-test: `python literature-knowledge-graph/tests/selftest.py` (25 checks)

Requirements: Python 3.9+, standard library only (matplotlib optional, only for the PNG preview).
