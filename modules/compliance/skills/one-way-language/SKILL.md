---
name: one-way-language
description: Write or rewrite one-way text (text whose writer cannot answer the reader's questions) using MSCD-based one-way language: policies, SOPs, checklists, codes of conduct, notices, patient handouts, consent and privacy notices. Use when the user asks for a policy, procedure, SOP, checklist, handout, notice or plain-language rewrite, or says "one-way", "must/must not/may" or "active voice". Scope boundary: binding contracts → `contract-drafting-mscd`.
---

# One-way language

The full standard is the user's own `references/one-way-optimal-language.md` (Hard Rules H1-H8, the category lexicon, rubric R1-R30, the active-voice sweep). Follow it exactly. This file adds only the project defaults:

- **Categories:** duty `[Role] must [verb]`; prohibition `[Role] must not [verb]`; permission `[Role] may [verb]`; no duty `[Role] does not have to [verb]`. Never `shall`, `should`, `is required to`, `is responsible for`, `cannot`, `may not`.
- **Digits only**, active voice in every clause, one instruction per sentence, under 25 words where possible.
- **SOP layout** (from the EPA QA/G-6 approach the user adopted): Layer 1 governance (title, document ID, version and effective date, approver, scope, citations, definitions); Layer 2 procedure (systems used, cautions, numbered steps written as who does what in which system within how many hours or days, and a responsibility table); Layer 3 control (pass/fail checklist, escalation, records and their retention, review cadence).
- **Law in the text:** cite only verified cards in `knowledge/` or a source checked in this session (Hard Rule H5). Keep text that a law requires word for word, with its citation.
- **Checks:** run `python skills/one-way-language/scripts/av_scan.py FILE --strict` for passives and `python -m tools.mscd_lint FILE --mode one-way` for modal verbs, digits and archaic words. Report each result line. If no shell is available, say that only the eye check ran.
