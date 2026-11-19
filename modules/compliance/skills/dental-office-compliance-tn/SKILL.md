---
name: dental-office-compliance-tn
description: Answer and act on Tennessee + federal compliance questions for a small dental practice: Tennessee Board of Dentistry rules (assistant registration, scope, certifications, CE/CPR, records, infection control), OSHA/TOSHA (bloodborne pathogens, hazard communication, recordkeeping), CDC infection-control guidance, HIPAA privacy/security/breach, DEA and Tennessee prescribing rules, dental x-ray registration, and Tennessee + federal employment law. Use for any "are we required to", "how often", "how long do we keep", "who may do", or compliance-calendar question in a dental office.
---

# Dental office compliance (Tennessee + federal)

## Sources of truth
1. `knowledge/<section>/*.md` cards. Answer from cards with `status: verified`, quoting their exact text, citation and `last_verified` date.
2. If no verified card covers it: say so first, then check the official source (see each section README for where), label the answer "not yet in the verified base", and offer to write a new card (status `unverified` until its quote is checked against the source).
3. Never answer a number, deadline, threshold or citation from memory.

## Sections
| Section | Covers |
|---|---|
| `tn-dentistry` | Board of Dentistry rules 0460: assistant levels, registration, scope, certifications, CE/CPR, infection control, records, advertising, ownership |
| `osha` | TOSHA state plan, 29 CFR 1910.1030, 1910.1200, 1904, PPE, eyewash, exits, fire, posters |
| `infection-control` | CDC dental guidance (guidance, not law), sterilization monitoring, waterlines, waste, amalgam separators |
| `privacy` | HIPAA Privacy, Security, Breach; BAAs; Tennessee breach law; Section 1557 |
| `controlled-substances-radiation` | DEA registration, records, inventory, disposal; CSMD; opioid limits; e-prescribing; nitrous; x-ray registration |
| `federal-employment` | Coverage thresholds, FLSA, PUMP Act, FMLA, I-9, EEOC, posters, NLRA, FCRA, payroll taxes |
| `tn-employment` | Wage payment, breaks, THRA, TN PWFA, E-Verify, leave laws, workers' comp, non-competes |
| `healthcare-contracts` | AKS, Stark, EKRA, OIG exclusions, CMPs, False Claims Acts, Tennessee ownership and fee splitting |

## Answer shape
1. One-sentence answer, with the office facts it assumes (headcount, TennCare billing, controlled-substance prescribing).
2. The rule, quoted, with citation and `last_verified`.
3. Law vs guidance vs good practice, labeled.
4. "What to do": steps with owner and frequency, in one-way language (`one-way-language`).
5. What a professional decides (dentist-owner, attorney, CPA, insurer), if anything.

## Compliance calendar
When asked for a calendar, build it only from verified cards: each row is task, frequency, owner, citation, record kept and retention. Mark each row whose card is unverified.
