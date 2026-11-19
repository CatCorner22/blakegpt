---
name: contract-drafting-mscd
description: Draft, review and redline contracts, addenda, policies with legal effect and employee acknowledgments using Kenneth A. Adams's A Manual of Style for Contract Drafting (5th ed. 2023) categories of contract language plus 5 mandatory user overrides. Use when the user asks to draft, review, redline, tighten or "MSCD" a contract, agreement, addendum, BAA, offer letter, acknowledgment or binding policy text. Scope boundary: non-binding one-way text (SOPs, checklists, codes, notices) → `one-way-language`; healthcare-specific clauses and statutes → `revitalist-tn-healthcare-contracts`.
---

# Contract drafting (MSCD 5e + 5 overrides)

The rules below restate MSCD in this project's own words; quote the book only by short reference (for example "MSCD ch. 3"). The book itself is copyrighted and is not reproduced here.

## A. The 5 mandatory overrides (highest precedence)

1. **Digits only.** Every number, amount, period and percentage is a numeral: `5 business days`, `12 months`, `$2,500.00`. Never words, never `five (5)`. If a number would start a sentence, restructure the sentence.
2. **No article before a defined party name.** `Company shall pay Provider`, never `The Company shall pay the Provider`.
3. **Outline hierarchy, exactly:** `I.` → `A.` → `1.` → `(a)` → `(i)`. No other label style, no skipped tier.
4. **Cross-reference by paragraph title, never by number.** `as stated in the paragraph titled "Compensation"`, never `Section III.B.2(a)`. Every referenced paragraph carries a unique descriptive title.
5. **Terms of art keep their legal meaning only.** `assignment` (transfer of rights), `consideration` (contract formation), `execute` (sign), `warrant` (warranty). For everyday meanings write `clinical duty` or `task`, `review`, `sign` or `perform`, `justify`.

## B. Categories of contract language (MSCD ch. 3)

| Category | Use | Never |
|---|---|---|
| Obligation of a party | `[Party] shall [verb]` (passes the "has a duty to" test) | `will`, `must`, `agrees to`, `is required to`, `undertakes to` |
| Prohibition | `[Party] shall not [verb]` | `may not` for a duty to refrain |
| Discretion | `[Party] may [verb]` | `is entitled to`, `has the right to` for permission |
| Condition | `must` for a condition or a non-party, for example `To be eligible, the notice must be in writing` | `shall` on a non-party |
| Policy | present tense: `This agreement terminates`, `Tennessee law governs` | `shall be deemed`, `shall be governed` |
| Declaration | `[Party] states that` | `represents and warrants that`, unless a statute or the user requires warranty language (flag it) |

Also strip archaic and redundant wording: whereas (use a titled "Background"), witnesseth, herein, hereof, thereto, said and such as pointing words, `and/or` (write `X or Y or both`), "for the avoidance of doubt", "including but not limited to" (write "including"), "null and void" (write "void").

## C. Workflow

1. Ask, in one block, for anything missing: the parties' defined names, governing law, term, price or rate, and the decision maker for each open business term. Never invent one; write `[X: missing term]`.
2. Draft or redline in the hierarchy of override 3, with a title on every paragraph.
3. Run `python -m tools.mscd_lint FILE --mode contract --party <Name> ...` and fix each error-severity finding. Decide each "review" finding (terms of art) and say what you decided.
4. Deliver: (a) the clean text; (b) a list of every substantive change with its reason; (c) open business and legal decisions, each with its decision maker; (d) the linter result line. If no shell is available, say that only the eye check ran.
5. Legal content (statutes, safe harbors, required clauses) comes only from verified cards in `knowledge/` or a source checked in this session (see `dental-office-compliance-tn` and `revitalist-tn-healthcare-contracts`).

The one-way variant of these rules (for policies) is in `references/mscd_one_way_rules.yaml`; it replaces `shall` with `must` for non-contract text.
