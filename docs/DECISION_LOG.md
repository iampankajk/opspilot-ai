# OpsPilot AI — Decision Log

Record decisions only after they have been discussed and accepted. Do not treat candidate technologies or assumptions as final decisions.

| ID | Date | Decision | Context / alternatives | Consequences | Status |
|---|---|---|---|---|---|
| D-001 | 2026-10-30 | Use OpsPilot AI as the working project concept | Combine enterprise operations investigation, RAG, controlled agent tools, approvals, and observability in one coherent portfolio product. | Product discovery will validate and refine the business scenario before implementation. | Accepted |
| D-002 | 2026-10-30 | Use a flexible 60-day learning horizon | Depth and independent understanding are more important than finishing within 30 days. | Plan around roughly 180 hours but extend phases when needed. | Accepted |
| D-003 | 2026-10-30 | Keep AI-generated implementation code limited | Owner wants to write and understand most code independently. | Prefer explanation, hints, pseudocode, small examples, reviews, and debugging support. | Accepted |
| D-004 | TBD | Select backend/API framework | Candidate: FastAPI; Flask experience already provides a foundation. | Decide during architecture/design after requirements are clearer. | Proposed |
| D-005 | TBD | Select relational/vector storage approach | Candidate: PostgreSQL + pgvector; compare with alternatives and operational complexity. | Decide during data and architecture design. | Proposed |

## Adding a decision

For significant decisions, create an ADR using `docs/decisions/ADR_TEMPLATE.md`, then add a short entry here linking to it. Include context, options, decision, consequences, and validation plan.
