# OpsPilot AI — Codex Project Starter

This starter kit transfers the project direction and the agreed learning workflow into a repository that Codex can use across separate chats.

## What is included

- `AGENTS.md` — persistent project-wide instructions Codex should read before working.
- `docs/PROJECT_BRIEF.md` — product concept, target workflow, users, scope, and initial technology direction.
- `docs/LEARNING_PLAN.md` — flexible 60-day learning and delivery roadmap.
- `docs/CODEX_WORKFLOW.md` — how to set up the folder and organize focused Codex chats.
- `docs/PROJECT_STATUS.md` — the shared source of truth for current phase, decisions, blockers, and next steps.
- `docs/DECISION_LOG.md` and `docs/decisions/ADR_TEMPLATE.md` — record technical decisions and trade-offs.
- `docs/LEARNING_LOG.md` — daily learning journal.
- `docs/prompts/` — copy-ready prompts for the different Codex chats.

## Recommended first steps

1. Extract this folder somewhere convenient, for example `~/Developer/opspilot-ai`.
2. Rename the folder to `opspilot-ai` if needed.
3. Open the **folder itself** in the Codex app and make it the working project.
4. Start a first chat named `00 - Project Guide & Learning Lead` and paste the prompt from `docs/prompts/00-project-guide.md`.
5. Ask Codex to read `AGENTS.md` and all files under `docs/`, summarize the project, and confirm that it understands the learning-first rules. Do not ask it to write application code yet.
6. Initialize Git when you are ready, then commit this starter documentation as the first commit.

The folder is deliberately documentation-only. Do not scaffold the app until product discovery and the initial requirements/design decisions are complete.
