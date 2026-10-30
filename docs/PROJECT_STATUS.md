# OpsPilot AI — Current Project Status

> Update this file as milestones are completed. This is the shared status source for all Codex chats.

## Current state

- **Status:** Product discovery in progress.
- **Current phase:** Phase 1 — Product discovery.
- **Current milestone:** Validate the business problem, target users, and MVP boundary against the documented current-state workflow.
- **Target cadence:** Approximately 3 hours per day, flexible 60-day plan; extend as needed.
- **Implementation started:** No.
- **Technology decisions finalized:** No. Candidate stack is documented in `PROJECT_BRIEF.md` and remains provisional.

## Completed

- Agreed on the OpsPilot AI project direction.
- Agreed to use a learning-first, full software development lifecycle.
- Agreed to prioritize independent implementation and deep understanding over generated code.
- Prepared initial Codex project documentation.
- Mapped the assumed current-state APAC payment incident workflow, evidence sources, roles, approvals, recovery, financial remediation, post-incident review, and knowledge maintenance in `docs/CURRENT_STATE_WORKFLOW.md`.

## In progress

- Validate the fictional workflow assumptions and investigate the underlying business problem before defining product scope.

## Open questions

- Is the on-call Payments Operations Engineer the right primary user, and how frequent/costly is the investigation problem?
- Which observed delays, inconsistencies, and mistakes are most material in the current workflow?
- Which part of the workflow, if any, should become the primary MVP problem to solve?
- What exact action will be prepared for human approval, after discovery validates the need?
- Which sample documents and synthetic records are needed to demonstrate the scenario?
- What deployment constraints and budget should guide provider choices?

## Current blockers

- None recorded.

## Next actions

1. Complete validation of the fictional current-state assumptions, including any remaining refund-case closure criteria.
2. Identify the most material investigation delays, inconsistencies, mistakes, and current workarounds.
3. Agree on an evidence-backed problem statement and MVP boundary before drafting a PRD.

## Recent decisions

- The project is called OpsPilot AI (working title).
- The plan is approximately 60 days / 180 hours, but it is not a fixed deadline.
- The owner wants AI to focus on explanations, design discussion, hints, reviews, and debugging. AI-written implementation code should remain around 10–20% as a guideline.
