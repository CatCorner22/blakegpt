---
name: smb-internal-controls
description: Design and review internal controls and anti-embezzlement safeguards for a small practice or business (5 to 150 employees): segregation of duties with compensating controls for lean staff, cash/banking, payroll, payables and vendor master, receivables and refunds, expense reimbursement, access rights, red flags, and a fraud response sequence that preserves evidence, insurance and recovery rights. Use for "how do we stop embezzlement", "who should approve", "review these expenses/invoices", "we think someone is stealing", or internal-control SOPs. Pairs with the Precog app, which scores duty conflicts.
---

# Small-business internal controls

## Principles
- Frameworks: COSO Internal Control - Integrated Framework (2013) and the ACFE Report to the Nations (cite the edition and page for any statistic; follow `statistical-literacy`).
- With few staff, full segregation of duties is often impossible. Name each conflict, then add a compensating control that the owner performs and that leaves a record.
- Hard gates: any duty that moves money out (release payment, ACH, check signing, refunds) or creates personal statutory liability (payroll entry, approval, payroll master edits) is top priority regardless of score (the same rule Precog applies).

## Compensating controls (starting set; adapt to the office)
| Cycle | Scheme it stops | Control (owner performs) |
|---|---|---|
| Cash and banking | Check tampering, unauthorized ACH, hidden reconciling items | Positive Pay at the bank; owner reviews the bank statement or a read-only feed each month before the bookkeeper reconciles; maker and approver are 2 different people for every outgoing wire or ACH |
| Payroll | Ghost employees, rate changes, padded hours or PTO | Owner reviews the payroll change register (new hires, bank changes, rate changes) inside the payroll system before each funding |
| Payables and vendor master | Shell vendors, changed bank details | Vendor setup and bank changes need a W-9, a Secretary of State entity check and a call-back to an independently found phone number; run `tools/three_way_match.py` on invoices |
| Receivables and refunds | Skimming, lapping, false refunds or write-offs | Daily match of scheduled visits to charges to deposits; a second approver for refunds and write-offs above a set amount |
| Expenses and cards | Personal purchases, duplicates, split charges | Itemized receipts; run `tools/expense_audit.py` monthly; the owner reviews flagged rows |
| Access | Toxic permission combinations, stale accounts | Quarterly review of who can create vendors, approve invoices and release payments; remove access the day a person leaves |

All thresholds (for example a refund or dual-approval amount) are the owner's decision; write `[X: owner sets amount]` until set.

## Suspected fraud: order of steps
1. Preserve first, silently: secure logs, bank and payroll records and devices; plan access removal for the moment of any interview.
2. Call the practice's attorney and the crime or fidelity insurer before any confrontation, repayment agreement or deduction. Many crime policies have notice deadlines and conditions (read the policy).
3. Quantify the loss with documents (a chronology linking each transaction to its evidence).
4. Decide with counsel on a police or district-attorney referral; where TennCare funds or public money are involved, counsel decides on referrals to the state Comptroller or OIG.
5. Never deduct a loss from wages without counsel's sign-off; wage laws limit deductions.

Legal statements here (wage deductions, polygraph limits, reporting) come only from verified cards in `knowledge/federal-employment`, `knowledge/tn-employment` and `knowledge/healthcare-contracts`, or a source checked in this session.

## SOPs
Write SOPs in the 3-layer layout in `one-way-language`.
