# [00] LLM Failure Modes — Living Reference
_Version 1.0 · Owner: Blake Reagan · Scope: recurring failure modes of LLM assistants and coding agents, their mechanisms, and the remedy class for each. Does not cover model benchmarks or pricing._
_Refresh: run `scripts/refresh_reference.py examples/llm-failure-modes.reference.md --stale-days 120` after every edit._

## [01] Attack sheet
- A file visible in a Project is not in the model's context; the model must call a search tool. §10.01
- Compaction drops file contents; the agent re-reads instead of remembering. §10.02
- Rules files are guidance, not enforcement; hooks are the only deterministic layer. §20.01
- Context files cut tokens but do not raise success rates. §20.02
- Ask-vs-assume: ask once up front; mid-task interruptions carry a measurable cost. §30.01
- Any action that must never happen needs a hook, not a sentence. §20.01

## [02] Contents
<!-- toc:start -->
- [00 LLM Failure Modes — Living Reference](#00-llm-failure-modes-living-reference)
- [01 Attack sheet](#01-attack-sheet)
- [03 How to read this file](#03-how-to-read-this-file)
- [10 Resource blindness and re-work](#10-resource-blindness-and-re-work)
  - [10.01 Project files are retrieved on demand, not always present](#1001-project-files-are-retrieved-on-demand-not-always-present)
  - [10.02 Compaction causes re-read loops](#1002-compaction-causes-re-read-loops)
- [20 Guidance versus enforcement](#20-guidance-versus-enforcement)
  - [20.01 Rules files are guidance; hooks are enforcement](#2001-rules-files-are-guidance-hooks-are-enforcement)
  - [20.02 Context files reduce tokens, not failures](#2002-context-files-reduce-tokens-not-failures)
- [30 Interaction policy](#30-interaction-policy)
  - [30.01 Ask once, up front; label cheap assumptions](#3001-ask-once-up-front-label-cheap-assumptions)
- [80 Glossary](#80-glossary)
- [85 Changelog](#85-changelog)
- [90 Sources](#90-sources)
- [91 Cite index](#91-cite-index)
- [92 Index](#92-index)
- [99 Health](#99-health)
<!-- toc:end -->

## [03] How to read this file
- Headings carry stable IDs in brackets; link to them as `§10.02`, never to page or position.
- Cites are short keys like `[S3]` or `[S3 at 2]`; full citations live in §90.
- `Rule`, `Mechanism`, `Test`, `Example`, `Fix`, `Open` labels start lines so you can scan.
- Every rule section ends with `Last verified: YYYY-MM-DD`.

## [10] Resource blindness and re-work
### [10.01] Project files are retrieved on demand, not always present
{{index: resource blindness | project files; Claude Projects; ChatGPT Projects; RAG; see also: re-read loop}}
**Rule.** Once a Project's knowledge is large, Claude and ChatGPT switch to retrieval; the model sees a file only if it decides to search for it. [S1] [S2]
**Mechanism.** The UI shows the folder; the model sees the context window. Retrieval is a tool call the model may skip. [S1]
**Test.** Ask "what files can you see right now?" before asking for analysis. If the answer omits the file, the model has not retrieved it.
**Example.** Nebula Genomics project: file present in the Medical folder; model proposed re-downloading it. [S7]
**Fix.** Inventory-before-fetch habit; a hook that blocks downloads of files already in the manifest. §20.01
**Open.** No public rate for retrieval misses in either product. [cite needed]
Last verified: 2026-11-10

### [10.02] Compaction causes re-read loops
{{index: re-read loop | compaction; context eviction; see also: resource blindness}}
**Rule.** When a coding agent compacts context, previously read files vanish and the agent re-reads them, often repeatedly. [S3] [S4]
**Example.** One Codex session: 74 compactions, 95% followed by a re-read of an already-read file. [S3]
**Fix.** A read manifest on disk; the file remembers what the model forgot. §20.01
Last verified: 2026-11-10

## [20] Guidance versus enforcement
### [20.01] Rules files are guidance; hooks are enforcement
{{index: enforcement | hooks; CLAUDE.md; rules files; see also: guidance}}
**Rule.** CLAUDE.md and similar rules files are "context, not enforced configuration"; only PreToolUse/Stop hooks block an action deterministically. [S5]
**Test.** If a failure cost more than ten minutes or any data, it belongs in a hook or on-disk state, not in a rule.
Last verified: 2026-11-10

### [20.02] Context files reduce tokens, not failures
{{index: guidance | AGENTS.md; context files; see also: enforcement}}
**Rule.** Two studies find AGENTS.md-style files lower token use or change style without raising task success. [S6]
**Open.** Whether short, trigger-specific skills behave differently from long always-on files.
Last verified: 2026-11-10

## [30] Interaction policy
### [30.01] Ask once, up front; label cheap assumptions
{{index: clarifying questions | ask or assume; interruption cost}}
**Rule.** Clarifying questions improve outcomes when batched before work starts; mid-task interruptions carry a measurable cost to users. [S8]
**Fix.** Ask all legitimate questions in one block; proceed on reversible guesses with "Assumed: X."
Last verified: 2026-11-10

## [80] Glossary
- **Resource blindness** (UF: ignoring project files) — failure to use information or tools already available. §10.01
- **Compaction** (UF: context eviction) — summarizing or dropping earlier context to free the window. §10.02
- **Enforcement** (UF: hooks) — a mechanism that blocks an action regardless of what the model intends. §20.01

## [85] Changelog
- 2026-11-10 v1.0 — created from the exhaustive-research report.

## [90] Sources
- [S1] Anthropic, *Retrieval Augmented Generation (RAG) for Projects*, Claude Help Center. https://support.claude.com/en/articles/11473015. Accessed 2026-11-10. Grade: A.
- [S2] OpenAI, *Projects in ChatGPT*, OpenAI Help Center. https://help.openai.com/en/articles/10169521. Accessed 2026-11-10. Grade: A.
- [S3] openai/codex issue, compaction followed by repeated file reads, GitHub (2026). Accessed 2026-11-10. Grade: C.
- [S4] anthropics/claude-code issue, unchanged file re-read loop, GitHub (2026). Accessed 2026-11-10. Grade: C.
- [S5] Anthropic, *Claude Code hooks reference*. https://docs.anthropic.com/en/docs/claude-code/hooks. Accessed 2026-11-10. Grade: A.
- [S6] Two arXiv studies on AGENTS.md effectiveness and efficiency (2025–2026). Accessed 2026-11-10. Grade: B.
- [S7] Blake Reagan, session note, 2026-11-10 (Nebula Genomics Project, Claude). Grade: D.
- [S8] Studies on clarifying-question timing and interruption budgets (2025). Accessed 2026-11-10. Grade: B.

## [91] Cite index
<!-- authorities:start -->
- [S1] Anthropic, *Retrieval Augmented Generation (RAG) for Projects*, Claude Help Center → §10.01
- [S2] OpenAI, *Projects in ChatGPT*, OpenAI Help Center → §10.01
- [S3] openai/codex issue, compaction followed by repeated file reads, GitHub (2026) → §10.02
- [S4] anthropics/claude-code issue, unchanged file re-read loop, GitHub (2026) → §10.02
- [S5] Anthropic, *Claude Code hooks reference* → §20.01
- [S6] Two arXiv studies on AGENTS.md effectiveness and efficiency (2025–2026) → §20.02
- [S7] Blake Reagan, session note, 2026-11-10 (Nebula Genomics Project, Claude) → §10.01
- [S8] Studies on clarifying-question timing and interruption budgets (2025) → §30.01
<!-- authorities:end -->

## [92] Index
<!-- index:start -->

**A**
- AGENTS.md — *see* guidance
- ask or assume — *see* clarifying questions

**C**
- ChatGPT Projects — *see* resource blindness
- **clarifying questions** — §30.01
- Claude Projects — *see* resource blindness
- CLAUDE.md — *see* enforcement
- compaction — *see* re-read loop
- context eviction — *see* re-read loop
- context files — *see* guidance

**E**
- **enforcement** — §20.01 · *see also* guidance

**G**
- **guidance** — §20.02 · *see also* enforcement

**H**
- hooks — *see* enforcement

**I**
- interruption cost — *see* clarifying questions

**P**
- project files — *see* resource blindness

**R**
- RAG — *see* resource blindness
- **re-read loop** — §10.02 · *see also* resource blindness
- **resource blindness** — §10.01 · *see also* re-read loop
- rules files — *see* enforcement
<!-- index:end -->

## [99] Health
<!-- health:start -->
_Refreshed 2026-11-10: 18 sections, 8 sources, 5 index terms._
- §10.01 Project files are retrieved on demand, not always present: [cite needed]
<!-- health:end -->
