---
name: ingest-source
description: Capture any source (URL, PDF, article, video transcript, pasted text, or file) into the project's persistent knowledge base. Use when the user says "ingest", "save this to my project", "add this to my knowledge base", or wants research to be remembered across sessions. Pre-analyzes each source into structured notes with an index so it is easy to retrieve later.
---

# Ingest Source

Web research and attached documents disappear when the session ends, so every new session starts from scratch. This skill builds a persistent knowledge base inside the project so data is captured once and reused forever.

The key: do not store raw dumps. Raw data is hard to search. Pre-analyze every source into structured notes — think of it as writing the table of contents for a textbook, so future sessions know exactly where to look instead of re-reading everything.

## Knowledge base layout

All ingested material lives in a `knowledge/` folder at the project root:

```
knowledge/
  INDEX.md               # master table of contents, one line per source
  sources/
    <slug>.md            # one analyzed note per source
  board/                 # expert persona files (used by ask-the-board)
  focus-group/           # audience persona files (used by internal-focus-group)
```

Create `knowledge/`, `knowledge/sources/`, and `knowledge/INDEX.md` on first use if they do not exist.

## Workflow

### 1. Acquire the source

- **URL** — fetch the content (prefer the `web-scraping` skill for JavaScript-heavy pages).
- **PDF or file** — read the attached or referenced file.
- **Pasted text / transcript** — use it directly.

If the content cannot be retrieved, tell the user and stop; never ingest content you have not actually read.

### 2. Pre-analyze

Extract, in your own words:

- What the source is and who produced it (author, outlet, date).
- The 3–10 key concepts, claims, or findings, each with enough detail to be useful without re-reading the source.
- Concrete data points: numbers, protocols, steps, quotes worth keeping verbatim.
- How it relates to sources already in the knowledge base (agrees, contradicts, extends). Check `knowledge/INDEX.md` for related entries.

### 3. Write the source note

Save to `knowledge/sources/<slug>.md`, where `<slug>` is a short kebab-case name (e.g. `huberman-zone2-protocol.md`):

```markdown
# <Title>

- **Source:** <URL or filename>
- **Author/Origin:** <who>
- **Date:** <publish date if known>
- **Ingested:** <today's date>
- **Tags:** <comma-separated topics>

## Summary

<2-4 sentence overview of what this source contains and why it matters to this project.>

## Key concepts

### <Concept 1>
<Detailed, self-contained explanation.>

### <Concept 2>
...

## Notable data & quotes

- <specific numbers, steps, or verbatim quotes with context>

## Relation to existing knowledge

- <agrees/contradicts/extends which existing notes, or "first source on this topic">
```

### 4. Update the index

Append one line to `knowledge/INDEX.md` (create the file with a `# Knowledge Base Index` heading if new):

```markdown
- [<Title>](sources/<slug>.md) — <one-line description of what questions this note answers> (tags: <tags>)
```

Keep the index sorted by topic if sections already exist; otherwise a flat list is fine.

### 5. Confirm

Report back: the note's path, the key concepts captured, and any conflicts with existing knowledge that the user should know about.

## Retrieval

When a future question touches an ingested topic, read `knowledge/INDEX.md` first, then open only the relevant source notes. Example: after ingesting fitness research, "What should I do as a 36-year-old getting back into cardio?" should be answered from the knowledge base, citing the specific source notes used.

## Rules

- One note per source; if a source is re-ingested, update its existing note rather than duplicating it.
- Never invent metadata (dates, authors). Mark unknown fields as `unknown`.
- Keep notes self-contained: a reader should get value without opening the original source.
