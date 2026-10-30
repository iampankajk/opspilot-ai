# Using Codex for OpsPilot AI

## 1. Understand the two kinds of context

Codex chats have their own conversation history, but they work against the same repository/folder when you open them in the same local project. Do not assume one chat's full transcript is automatically available in another chat.

Use these layers:

1. **Repository context:** files in this folder, especially `AGENTS.md` and `docs/`.
2. **Chat context:** the focused conversation and role prompt for that chat.
3. **Current code/design artifacts:** the actual files, specifications, tests, and implementation in the working tree.

When a decision becomes important, record it in the repository rather than leaving it only in a chat transcript.

## 2. Set up the local project

1. Extract this starter folder to a convenient development directory.
2. Open the extracted `opspilot-codex-starter` folder in the Codex app as the local project/workspace. Rename it to `opspilot-ai` first if you prefer.
3. Confirm the project root contains `AGENTS.md` and `docs/`.
4. Ask Codex to read `AGENTS.md` and the documents under `docs/`, then summarize the project and working rules.
5. Do not scaffold the frontend or backend yet. Start with product discovery.
6. Initialize Git from the project root when ready. Commit the starter documentation before implementation.

## 3. Create focused chats

Create separate chats for distinct outcomes. Suggested names and responsibilities:

| Chat name | Main responsibility | Prompt file |
|---|---|---|
| `00 - Project Guide & Learning Lead` | Overall direction, phase gates, shared status, keep work aligned | `prompts/00-project-guide.md` |
| `01 - Product Discovery & PRD` | Business problem, users, requirements, MVP, acceptance criteria | `prompts/01-product-discovery.md` |
| `02 - System, Database & API Design` | Architecture, ERD, data contracts, API design, trade-offs | `prompts/02-system-design.md` |
| `03 - Learning Coach` | Teach concepts before/during implementation | `prompts/03-learning-coach.md` |
| `04 - Implementation Pair Programmer` | Small implementation guidance, hints, limited code generation | `prompts/04-implementation.md` |
| `05 - Code Reviewer` | Review code for correctness, readability, security, maintainability | `prompts/05-code-review.md` |
| `06 - QA & Test Engineer` | Test strategy, test cases, edge cases, quality gates | `prompts/06-qa.md` |
| `07 - Debugging Partner` | Guide systematic diagnosis and root-cause analysis | `prompts/07-debugging.md` |

You do not need to create every chat immediately. Start with `00` and `01`. Add the others when those activities begin.

## 4. How to start each chat

1. Open the same OpsPilot local project/folder.
2. Create a new chat.
3. Paste the full contents of the matching prompt file.
4. Ask the chat to read the relevant project documents and confirm the current phase from `docs/PROJECT_STATUS.md`.
5. Give it one bounded task and define the expected output.

The prompt files are role instructions, not separate autonomous agents. They are separate conversations with distinct responsibilities, all using the same repository context.

## 5. Rules for moving between chats

- Product chat creates or updates product artifacts; it should not start coding.
- Design chat proposes architecture, ERD, and API contracts; accepted decisions are recorded in ADRs.
- Learning chat explains concepts and checks your understanding; it should not silently implement features.
- Implementation chat works only from an accepted requirement and design. It should help you write most code yourself.
- Review chat inspects changes and reports findings; it should not silently rewrite the implementation.
- QA chat defines quality expectations and tests; it should not mark tests passed without running them.
- Debugging chat helps reproduce and isolate faults before proposing fixes.

## 6. A repeatable feature workflow

For each feature:

1. **Product:** clarify user problem, scope, and acceptance criteria.
2. **Learning:** identify unfamiliar concepts and learn them before implementation.
3. **Design:** agree on data model, API contract, component boundaries, and failure behavior.
4. **Implementation:** implement a small slice independently; ask for hints when blocked.
5. **QA:** define and run relevant tests.
6. **Review:** inspect correctness, security, maintainability, and trade-offs.
7. **Documentation:** update status, decisions, learning log, and README as appropriate.

Do not move to the next stage merely because a chat says it is ready. The owner decides when understanding and artifacts are sufficient.

## 7. Keep chats synchronized with project state

At the beginning of a chat, say:

> Read `AGENTS.md`, `docs/PROJECT_BRIEF.md`, `docs/LEARNING_PLAN.md`, and `docs/PROJECT_STATUS.md`. Tell me the current phase, completed milestones, open questions, and next recommended step. Do not make code changes.

At the end of a meaningful session, say:

> Summarize the decisions, artifacts, work completed, tests or validation performed, unresolved questions, and next step. Propose specific updates to `docs/PROJECT_STATUS.md`, `docs/DECISION_LOG.md`, or `docs/LEARNING_LOG.md`; do not edit them until I approve.

Then review and accept the proposed changes yourself.

## 8. Safe operating habits

- Review the diff before accepting generated edits.
- Keep changes small and commit coherent milestones.
- Do not paste API keys, passwords, access tokens, or real customer data into chats or the repository.
- Use synthetic sample records.
- Ask before adding dependencies, changing architecture, deleting files, or running destructive commands.
- Keep the first release simple and observable. Add infrastructure only when requirements justify it.
