---
name: revitalist-tn-healthcare-contracts
description: Draft, review and redline Tennessee healthcare contracts (originally built for Revitalist clinical, behavioral-health, infusion and wellness operations, and usable for dental practices): clinical provider employment and contractor agreements, collaborative-practice addenda, medical barter and reciprocal services, HIPAA and 42 CFR Part 2 business associate agreements, patient media and testimonial releases, and vendor, EHR, pharmacy and management services agreements. Applies federal fraud-and-abuse rules and Tennessee licensing, ownership, fee-splitting and non-compete rules, drafted under `contract-drafting-mscd`.
---

# Tennessee healthcare contracts

Draft every clause under `contract-drafting-mscd` (MSCD categories plus the 5 overrides) and run its linter.

## Legal checks (only from verified sources)
Each legal requirement below must come from a verified card in `knowledge/healthcare-contracts/` or `knowledge/privacy/`, or a source checked in this session. `knowledge/healthcare-contracts/SPEC_CHECKS.md` records which claims from the original third-party specification held up; never rely on a claim it marks FALSE or UNVERIFIED.

| Topic | What to check in the draft |
|---|---|
| Anti-Kickback Statute and safe harbors | Compensation set in advance, consistent with fair market value, not tied to referral volume or value; the safe harbor's written-agreement and term elements |
| Stark | Whether a physician (as the statute defines it) and a designated health service are involved at all |
| EKRA | Whether the facility type is covered; no per-patient or percentage pay to marketers where it applies |
| Beneficiary inducements | Federal-program patients excluded from promotions, memberships and barter unless an exception applies |
| HIPAA BAA | Every element the regulation requires, plus subcontractor flow-down and the notice period the parties choose |
| 42 CFR Part 2 | Only when substance-use-disorder records are involved |
| Media releases | Treatment never conditioned on a marketing authorization; authorization separate from clinical consent |
| Tennessee ownership and fee splitting | Who may own and control the practice; management fees structured as the verified Tennessee rule permits |
| Tennessee non-competes | Duration, geography and exceptions only as the verified statute states |
| Barter | Two-way invoicing at documented fair market value; tax reporting per IRS guidance |

## Output
1. The draft or redline.
2. A risk matrix: clause, rule (citation and card id), risk if wrong, required or optional.
3. Open decisions and their decision makers (owner, attorney, CPA).
4. The linter result line.
