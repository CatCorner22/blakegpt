# BlakeGPT workspace: interactive page specification

Give this file to Muse with: "Build the interactive page this specification describes, using this project's files." The same spec works for any platform that builds pages or apps.

## Purpose
A single-page workspace where Amanda drafts, stores and finds her own compliance work. It is for personal and professional use only. It holds no personal information (PII) and no confidential business information.

## Pages (left navigation, one at a time)
1. **Ask.** A question box. Answers cite cards from `knowledge/` (verified first). It also shows "not yet in the verified base" when the base doesn't cover the question.
2. **Drafts.** A list of drafts (title, type, status draft/final, updated date). The editor saves automatically. Types: policy or SOP (one-way language), contract or acknowledgment (MSCD), checklist, letter, note. Buttons: "Check language", which runs the one-way or contract rules, and "Export" (Markdown, Word, PDF).
3. **Documents.** The sources she has ingested (`knowledge/sources/`): title, type, date added, a one-line summary, and tags. Upload or paste a link. The ingest-source skill writes the analyzed note.
4. **Office reference.** `OFFICE-REFERENCE.md`, rendered with its table of contents, cite index and health report. Stale sections are highlighted.
5. **Mind map.** `MINDMAP.md`, rendered as the Mermaid diagram, with open questions and tasks listed beside it.
6. **Compliance calendar.** Each task with its frequency, owner, next due date and citation, built only from verified cards. Rows from unverified cards are marked.
7. **Tools.** Forms for the repo's calculators and checkers: leave hours, expense audit, invoice match, exclusion check, language lint.

## Storage
- Store everything in the project's own files or the platform's per-user storage: drafts in `drafts/<slug>.md` with front matter (title, type, status, updated); documents in `knowledge/sources/`.
- Keep the version history of each draft: the last 20 saves.
- Never send stored content to a third party except the model platform the project already uses.

## Privacy guardrails
- The workspace runs text through `tools/pii_redact.py` before sending it to a model or saving it.
- Before each save, scan for names with titles, phone numbers, email addresses, dates of birth, SSN patterns, chart or member numbers, and street addresses. If any is found, block the save and offer to replace each match with a role placeholder, for example "[patient]".
- Show "No PII" in the page footer as a reminder.

## Look and feel
Calm and quiet: one accent color, generous white space, plain labels and no jargon, large click targets, readable on a phone.

## Acceptance checks
- A draft survives a reload and appears in Drafts with its updated date.
- An ingested source appears in Documents and in `knowledge/INDEX.md`.
- An Ask answer shows at least one citation and the card's last-verified date, or the "not yet in the verified base" label.
- Saving text that contains a phone number is blocked until the number is replaced.
