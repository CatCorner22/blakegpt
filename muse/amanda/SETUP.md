# Loading BlakeGPT into Muse

1. In Muse, create a project named "BlakeGPT".
2. Paste `muse/amanda/PROJECT_INSTRUCTIONS.md` into the project's instructions.
3. Add these as project files (knowledge):
   - every `SKILL.md` under `skills/`, with its `references/` and `templates/` files;
   - `knowledge/` (all cards and each section's README);
   - `tools/leave_hours.py`, `tools/expense_audit.py` and `tools/draft_guard.py`, so hard rules 5 and 6 can follow their methods on platforms that cannot run code;
   - `OFFICE-REFERENCE.md` and `MINDMAP.md` once they exist.
4. Start the first chat with: "Start the office reference and the mind map for this practice."
5. Every 90 days, run `python -m tools.kb_freshness --federal-register` in this repo. Re-verify each stale card, then replace the project files.

The same files work on other platforms. Gemini Gems and ChatGPT Projects take the instructions as the Gem or project instructions and the files as knowledge. Claude Projects take them as project instructions and files. Agent runtimes load each `skills/<name>/SKILL.md` directly.

6. For the interactive page, give Muse `muse/amanda/INTERACTIVE_WORKSPACE_SPEC.md` with: "Build the interactive page this specification describes, using this project's files."
