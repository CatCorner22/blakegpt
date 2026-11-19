# Healthcare fraud-and-abuse and contract rules

Scope: federal fraud-and-abuse rules (Anti-Kickback Statute and safe harbors, Stark, EKRA, OIG exclusions and CMPs, beneficiary inducement, False Claims Act, overpayments), 42 CFR Part 2, selected HIPAA and IRS contract-adjacent rules, and Tennessee dental ownership, fee-splitting, referral-service, noncompete, records and Medicaid false-claims rules, for a small Tennessee dental practice billing commercial insurance, cash and TennCare dental.

All Tennessee statute text came from Justia, an unofficial mirror of the Tennessee Code (2025 edition); the official LexisNexis text was not fetched. Agency guidance is labeled as guidance, not law.

## Cards

| id | title | status |
|---|---|---|
| us-aks-kickback-prohibition | Anti-Kickback Statute: no pay for referrals of Federal health care program business | verified |
| us-aks-safe-harbor-space-rental | AKS safe harbor: space rental | verified |
| us-aks-safe-harbor-equipment-rental | AKS safe harbor: equipment rental | verified |
| us-aks-safe-harbor-personal-services | AKS safe harbor: personal services and management contracts | verified |
| us-aks-safe-harbor-employees | AKS safe harbor: bona fide employees | verified |
| us-aks-safe-harbor-referral-services | AKS safe harbor: referral services | verified |
| us-stark-dentist-physician-dhs | Stark law: dentists are physicians, but only Medicare-payable designated health services count | verified |
| us-ekra-recovery-homes-labs | EKRA: no kickbacks for referrals to recovery homes, clinical treatment facilities, or laboratories, any payer | verified |
| us-exclusion-effect-no-payment | OIG exclusion: no Federal program payment for items or services of an excluded person | verified |
| us-cmp-excluded-person-contracting | Civil money penalty for employing or contracting with an excluded person | verified |
| us-oig-exclusion-screening-guidance | Exclusion screening: OIG monthly-screening guidance and the State Medicaid monthly database check | verified |
| us-cmp-beneficiary-inducement-nominal-value | Beneficiary inducement CMP and the $15 / $75 nominal-value guidance | verified |
| us-fca-false-claims | Federal False Claims Act: liability for false claims to the Government | verified |
| us-overpayment-60-day-return | Report and return Medicare and Medicaid overpayments within 60 days of identification | verified |
| us-42-cfr-part-2-scope | 42 CFR Part 2: when substance use disorder confidentiality rules reach a dental office | verified |
| us-hipaa-ba-breach-notice-60-days | HIPAA: business associate must notify the covered entity of a breach within 60 calendar days | verified |
| us-hipaa-authorization-no-conditioning | HIPAA: do not condition treatment on a signed authorization; compound authorizations are limited | verified |
| us-irs-accountable-plan-reasonable-period | IRS accountable plan: substantiate within a reasonable period (30 / 60 / 120-day safe harbors) | verified |
| tn-63-5-121-dental-practice-ownership | Tennessee: only a licensed dentist may own an active dental practice | verified |
| tn-63-5-124-fee-splitting-commissions | Tennessee dentistry: no fee splitting for referrals and no commissions on professional fees | verified |
| tn-63-5-133-dental-referral-service | Tennessee: dental referral services must register and may not charge per referral | verified |
| tn-48-101-610-professional-corporation-shares | Tennessee professional corporations: share ownership limits | verified |
| tn-71-5-182-medicaid-false-claims | Tennessee Medicaid False Claims Act: penalties for false TennCare claims | verified |
| tn-63-1-148-provider-noncompete | Tennessee healthcare-provider noncompetes, including dentists: 2-year and geographic safe limits | verified |
| tn-63-2-101-patient-record-copies | Tennessee: give patients a copy of their records within 10 working days | verified |

## Items added beyond the assigned scope

- tn-63-5-124-fee-splitting-commissions (dental-board fee-splitting and commission grounds).
- tn-63-5-133-dental-referral-service (Tennessee dental referral services).
- tn-48-101-610-professional-corporation-shares (who may hold professional-corporation shares).
- us-overpayment-60-day-return (60-day overpayment report-and-return rule).
- tn-63-1-148-provider-noncompete, tn-63-2-101-patient-record-copies, us-hipaa-ba-breach-notice-60-days, us-hipaa-authorization-no-conditioning, us-irs-accountable-plan-reasonable-period (written because the spec claims behind them hold up, at least in part, and help the office).

## Scope items not covered, and why

- Revitalist contracts skill: not found. Searched every repository in the CatCorner22 GitHub account by file path and with GitHub code search for "revitalist"; no match. The only contracts skill found is `mscd-contracts` (a contract-drafting style skill in agent-skills-export and Cursor_Skills), which is not legal authority and is not carded.
- Whether Tennessee or TennCare requires providers to screen the LEIE and SAM monthly: not verified. Federal regulation puts the monthly LEIE/EPLS check on the State Medicaid agency (42 CFR 455.436(c)(2)); OIG guidance says providers are not required by statute or regulation to check the LEIE. No TennCare provider agreement, dental benefits manager manual or Tennessee rule was fetched. See us-oig-exclusion-screening-guidance.
- Tennessee rules on management services organizations and percentage-based MSO fees for dentistry: no Tennessee statute or Board of Dentistry rule addressing MSO fees was found or fetched; covered only through T.C.A. 63-5-121 and 63-5-124(a)(11), (a)(15) and the federal personal-services safe harbor.
- Stark exceptions (42 CFR 411.355-411.357), current inflation-adjusted CMP and FCA penalty amounts (45 CFR part 102; 28 CFR 85.5), and 2023-2026 court decisions were not fetched or searched.
- Tennessee APRN collaboration rules and the Board of Medical Examiners AMA ethics adoption: checked for SPEC_CHECKS only; not carded because they govern physicians and nurse practitioners, not a dental office.
