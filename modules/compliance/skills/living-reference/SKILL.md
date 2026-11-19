---
name: living-reference
description: "Build and maintain 'living reference' files — Markdown outlines that are updated often and read constantly, so accuracy and fast comprehension matter more than prose. Law-school-outline structure (organize by rule: Rule → Elements → Exceptions → Test → Examples → Policy → Open → Last verified), stable section IDs, a short-cite sources ledger, and four auto-regenerated apparatus blocks: table of contents, cite index (table of authorities), subject index with See/See also, and a health report (stale sections, undefined cites, orphan sources, broken cross-references). Ships scripts/refresh_reference.py and templates/living-reference.template.md. Use when the user asks for a living document, master reference, outline, cheat sheet that must stay current, project bible, knowledge file, 'single source of truth', or wants a file they will update often and keep citing. Scope boundary: one-off research reports → `exhaustive-research`; bibliography formatting in a paper → `citation-literacy`; capturing a single source into a knowledge base → `ingest-source`; folder taxonomy → `library-taxonomy-retrieval`; persistent session memory → `ai-transfer-memory`."
metadata:
  priority: 6
  pathPatterns:
    - '**/*reference*.md'
    - '**/*outline*.md'
    - '**/*living*.md'
  bashPatterns:
    - '\brefresh_reference\.py\b'
---

# Living reference

A living reference is a file you will edit often and read far more often. Two users must be served at once: the person who needs one fact in ten seconds, and the person who needs to trust that the whole file is still true. Everything below follows from those two needs.

Sources this skill draws on: ISO 999 and ANSI/NISO Z39.4 (indexes), ANSI/NISO Z39.19 (controlled vocabularies), Chicago Manual of Style ch. 16 and the ASI Index Evaluation Checklist, Bluebook Rule 4 and 10.9 (short cites), FRAP 28 table-of-authorities practice, CSL item metadata, law-school outlining guides (UC Davis, ABA, Touro), Diátaxis, Zettelkasten structure notes and Maps of Content, Johnny.Decimal IDs, Butterick's Practical Typography, Tufte, and the signaling/headings research (Lemarié, Lorch & Péry-Woodley 2012).

## 1. Decide before writing

Ask these once, up front, in one block; otherwise assume and label the assumption:

1. **Reader and vocabulary.** Who looks things up here, and what words do they use? Index terms must match the reader's words, not the source's (ASI: "heart attack" for the public, "myocardial infarction" for clinicians). Pick one preferred term per concept; everything else becomes an alias.
2. **Unit of organization.** Organize by **rule / principle / decision**, never by source, meeting, or date (law outlines: "organize by rule, not by case"). A source can appear under many rules; a rule has one home.
3. **Scope sentence.** One sentence on what the file covers and what it does not. Put it under the title. It stops the file from becoming a dump.
4. **Verification cadence.** How many days before a section counts as stale (default 90). Encode it in the refresh command.

## 2. Structure (fixed skeleton)

Start from `templates/living-reference.template.md`. The skeleton, with Johnny.Decimal-style stable IDs:

| ID | Block | Purpose |
|---|---|---|
| `[00]` | Title, version, owner, scope, refresh instruction | Trust header |
| `[01]` | **Attack sheet** | The 10–20 lines used most. Each ends with a `§ID`. Rewrite it whenever a rule below changes. |
| `[02]` | Contents | Front door. Auto-generated. |
| `[03]` | How to read this file | Conventions in five bullets. |
| `[10]`–`[79]` | Body: `##` topic, `###` rule | One rule per `###`, in the fixed field order below. |
| `[80]` | Glossary | Preferred term + `UF:` aliases + definition + `§ID`. The controlled vocabulary (Z39.19). |
| `[85]` | Changelog | Dated lines; version bumps. Deprecate, never silently delete. |
| `[90]` | Sources ledger | Full citations keyed `[S#]`. Keys are permanent. |
| `[91]` | Cite index | Back door #1, auto-generated: every source → every section citing it (a table of authorities). |
| `[92]` | Index | Back door #2, auto-generated: concept → sections, with *see* / *see also*. |
| `[99]` | Health | Auto-generated: stale, undefined, orphan, duplicate, broken. |

**Section IDs.** Every heading is `## [12] Title` or `### [12.04] Title`. IDs are assigned once and never reused or renumbered, even if the section moves (Johnny.Decimal). Cross-reference with `§12.04`, never "see above" or "below". Leave gaps (10, 20, 30) so topics can be inserted without renumbering.

**Rule section field order** (fixed, labels in bold, omit empty fields):

```
### [12.04] Heading that states the rule as a sentence
{{index: preferred term | alias; alias; see also: related term}}
**Rule.** One sentence. [S3 at 12]
**Elements.** 1) … 2) … 3) …
**Exceptions.** …
**Test / steps.** The procedure you actually run.
**Examples.** Short, concrete, with outcome. [S7]
**Policy / why.** One or two lines.
**Open.** What is unverified, contested, or pending.
Last verified: 2026-03-14
```

Headings are **informative, not topical**: "Short cites need a full cite within five footnotes", not "Short cites". Readers remember text organization through headings and headings bias what they take away (Lemarié et al.), so a heading must carry the answer. Field labels (`Rule`, `Exception`, `Test`) are signaling words; keep them identical everywhere so the eye can scan.

## 3. Citations

- **Ledger line:** `- [S12] Author/Org, *Title*, Container, Date. URL. Accessed YYYY-MM-DD. Grade: A|B|C|D. Note.` Fields mirror CSL item metadata so the cite can be re-rendered in Bluebook, Chicago, or APA later. Grade: A primary/official, B peer-reviewed or vendor doc, C reputable secondary, D forum/anecdote.
- **Short cite in body:** `[S12]` or `[S12 at 4]` (pinpoint). Bluebook's short-form test applies: the reader must know which authority, and must find the full cite easily. Here the ledger guarantees both, so a short cite is always allowed after the key exists.
- **Never renumber.** A retired source keeps its key: `- [S12] (retired 2026-05-01, superseded by [S40]) …`. The cite index then shows where the stale cite still lives.
- **Claim–evidence pairing:** a `Rule` line without a cite is an `Open` item. Mark it `[cite needed]` so the health block can find it (search for the literal string).
- **Table of authorities view:** `[91]` groups sources by key with every citing section. When the file is legal, keep the ledger itself grouped by type (cases, statutes, regulations, secondary) and alphabetical within type (FRAP 28 convention); the script preserves ledger order.

## 4. Indexing

The script builds the *mechanical* index; you supply the *intellectual* one (JHU: indexes "must be thought into being"; a word list is a concordance, not an index).

- Tag each rule section with one or more `{{index: term | alias; alias; see also: other}}` lines. The preferred term is the glossary term; aliases generate `*see*` entries (Z39.19 USE/UF); `see also:` generates related-term pointers.
- Index **concepts the reader will look for**, not every noun. Ask: "If I forgot where this was, what word would I search?" Add that word.
- A term pointing at more than 7 sections is too broad (ASI); the script flags it. Split it into subentries (`negligence — duty`, `negligence — breach`) or into more specific terms.
- Double-post synonyms the audience actually uses; never let the reader's word dead-end.
- Keep the index and glossary consistent: every glossary term should appear as an index term at least once.

## 5. Design and comprehension rules

- Markdown, UTF-8, one file unless it passes ~3,000 lines; then split by `##` topic into files that share one ledger and run the script per file.
- ≤ 4 heading levels. One idea per paragraph. Prefer tables for parallel facts (elements, thresholds, deadlines), bullets for steps, prose only for *why*.
- Bold for field labels only; italics for *see* / *see also* and titles; never underline; never bold and italic together (Butterick). Sentence-case headings.
- Lines of body text ≤ ~100 characters where the editor wraps poorly; keep tables ≤ 6 columns.
- Callouts: `> **Warning.**`, `> **Changed 2026-03-14.**` — use for things that bite, not decoration.
- Density is good when it is legible (Tufte): a number, its unit, its source, and its date in one line beats four lines.
- Dates ISO `YYYY-MM-DD` everywhere. Numbers with units. No "recently", "currently", "the new version".
- Write for the ten-second reader first: the answer in the heading, the rule in the first line, the source at the end of the line.

## 6. Update protocol (every edit)

1. Edit the rule section. Update its `Last verified:` date **only if you re-checked the source**; a wording edit does not re-verify a fact.
2. If a rule changed, update the `[01]` attack sheet and add a `> **Changed YYYY-MM-DD.**` callout in the section for one cycle.
3. Add or retire sources in `[90]`; never renumber.
4. Add a changelog line in `[85]`; bump the minor version for any rule change, the major version for a reorganization.
5. Run `python3 scripts/refresh_reference.py FILE.md --stale-days N`. It rewrites `[02]`, `[91]`, `[92]`, `[99]` in place and prints the health findings. Fix undefined cite keys and broken `§` references before finishing; stale sections become `Open` items or get re-verified.
6. In CI or a pre-commit hook, run with `--check` so a file with health findings fails the build (docs-as-code).
7. Report: the stamp line the script prints, plus any health findings you could not clear.

## 7. Review checklist (before calling it done)

- [ ] Scope sentence present; attack sheet ≤ 20 lines, each with a `§ID`.
- [ ] Every `###` follows the field order; every `Rule.` has a cite or `[cite needed]`.
- [ ] Every section has `Last verified:`; none older than the cadence without an `Open` note.
- [ ] Every `[S#]` resolves; no orphan sources (or they are marked retired/background).
- [ ] Index terms are the reader's words; aliases exist for the source's words; no term > 7 locators.
- [ ] TOC, cite index, index, health regenerated; health shows "No findings" or each finding is explained in `Open`.
- [ ] Changelog line and version bump present.

## 8. Script reference

`scripts/refresh_reference.py FILE.md [--stale-days 90] [--check]`

Reads headings `## [ID] Title`, ledger lines `- [S#] …`, short cites `[S# at …]`, tags `{{index: …}}`, and `Last verified:` lines. Rewrites the content between `<!-- toc:start/end -->`, `<!-- authorities:start/end -->`, `<!-- index:start/end -->`, `<!-- health:start/end -->`. Pure standard library; idempotent; safe to run on every save. Exit 1 with `--check` when health has findings.

## 9. Anti-patterns

- **Chronological dump**: sections named by date or meeting. Reorganize by rule.
- **Source-shaped outline**: one section per document read. Sources belong in the ledger; rules belong in the body.
- **Floating facts**: a number with no source, no date. Add both or move to `Open`.
- **Renumbering**: breaks every external link and memory. Leave gaps instead.
- **Concordance index**: tagging every noun. Tag what the reader will search.
- **Silent deletion**: a rule that stopped being true vanishes. Mark it `(superseded YYYY-MM-DD → §x)` and log it.
- **Manual TOC**: hand-maintained TOC/index drift within a week. Generate them.
