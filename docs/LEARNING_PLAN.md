# OpsPilot AI — Flexible 60-Day Learning Plan

## Guiding principle

The 60 days are a planning horizon, not a hard deadline. At roughly three hours per day this is approximately 180 hours. Extend any phase when understanding, design quality, or implementation evidence is not yet sufficient. Learning depth takes priority over calendar completion.

## Starting knowledge

- 4+ years of frontend engineering experience, mainly React, Next.js, and TypeScript.
- Python fundamentals and OOP concepts have been studied.
- Introductory Flask API development has been covered.
- SQL querying and relational database fundamentals are reasonably familiar.
- AI/ML foundations and practical work with LLMs, LangChain, LangGraph, RAG, embeddings, vector search, and MCP are upcoming learning topics in a course.

## Phase plan

| Phase | Approx. days | Main learning and work | Expected artifact |
|---|---:|---|---|
| 1. Product discovery | 1–7 | Business domain, users, pain points, workflows, problem statement, product scope, requirements | Problem statement, personas, user journeys, PRD, MVP scope |
| 2. UX and system design | 8–14 | Information architecture, wireframes, architecture, service boundaries, data flow, trade-offs | Wireframes, system context/container diagrams, technical design |
| 3. Database and API design | 15–21 | ER modelling, normalization, keys, constraints, indexes, transactions, REST API contracts, errors, auth design | ERD, schema proposal, API specification, ADRs |
| 4. Application foundation | 22–29 | Next.js/FastAPI integration, PostgreSQL, migrations, authentication, workspace and role model | Running application foundation with documented setup |
| 5. AI and RAG | 30–37 | LLM APIs, tokens, prompting, embeddings, chunking, vector retrieval, hybrid search, citations, evaluation | Knowledge ingestion and grounded Q&A workflow |
| 6. Agents and MCP | 38–45 | Tool calling, LangChain integrations, LangGraph state/edges, workflow pauses, MCP client/server, validated tools | Incident investigation agent with controlled tools |
| 7. Security and observability | 46–52 | RBAC, least privilege, approval gates, prompt injection, audit logs, tracing, latency/cost, eval/regression tests | Governed workflow with inspectable run history and safety tests |
| 8. Testing and delivery | 53–60 | Unit/integration/E2E testing, Docker, CI/CD, deployment, technical docs, demo preparation | Deployed MVP, README, diagrams, demo, test/evaluation report |

## Suggested daily rhythm (about 3 hours)

- 45 minutes: learn one concept or investigate one design question.
- 90 minutes: apply it through design or independent implementation.
- 30 minutes: test, debug, and inspect behavior.
- 15 minutes: document learning, decisions, blockers, and next actions.

This rhythm is flexible. A difficult concept may require a full session of reading, diagrams, and small experiments without adding a feature.

## Learning checkpoints

At the end of each phase, the owner should be able to explain:

1. What problem this phase solves.
2. What artifact or behavior was produced.
3. Why the chosen approach was selected.
4. What alternatives were considered.
5. What assumptions or limitations remain.
6. How the output will be validated.

## Scope control

Build a coherent and safe MVP first. Treat Kubernetes, Kafka, Terraform, multi-agent orchestration, local inference optimization, and other advanced infrastructure as later extensions unless the project requirements justify them.
