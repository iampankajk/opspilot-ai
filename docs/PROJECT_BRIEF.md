# OpsPilot AI — Project Brief

## 1. Working title

**OpsPilot AI — Enterprise Operations & Incident Management Assistant**

The name is provisional and can be changed after product discovery.

## 2. Product vision

Build an AI-powered operations assistant for a fictional SaaS company. It helps support and operations teams investigate incidents by combining internal knowledge, operational business data, and controlled tool execution.

This is not intended to be another generic chatbot. It should demonstrate how an AI-enabled product can retrieve evidence, query approved data, orchestrate multi-step workflows, request human approval, and maintain an auditable record of what happened.

## 3. Illustrative business problem

A SaaS company receives multiple customer reports that payments have started failing. Some customers may have been charged more than once. Support and operations staff must search runbooks, review historical incidents, inspect transaction records, correlate tickets, and coordinate an engineering response.

OpsPilot should help an authorized employee investigate a question such as:

> Investigate the payment failures reported over the last 24 hours. Summarize the evidence, identify relevant historical incidents, and recommend the next operational steps.

The system should:

1. Retrieve relevant runbooks, internal documentation, and previous incident reports.
2. Query approved, read-only operational data such as synthetic payment transactions.
3. Find and summarize related support tickets.
4. Present an evidence-based investigation with citations and data provenance.
5. Recommend next steps.
6. Prepare a proposed action, such as drafting an incident ticket or notification.
7. Pause for human review before any sensitive or externally visible action.
8. Record tool calls, decisions, approvals, and outcomes in an audit trail.

## 4. Target users

Initial personas to validate during discovery:

- **Support engineer:** investigates customer issues and searches internal knowledge.
- **Operations engineer:** analyzes incidents and coordinates response workflows.
- **Team lead / operator:** reviews recommendations and approves controlled actions.
- **Workspace administrator:** manages users, roles, data sources, and policies.

These are starting hypotheses, not finalized user research findings.

## 5. Main product capabilities (candidate scope)

### A. Workspace and access management
- Organization/workspace concept.
- User membership and roles.
- Basic authentication and authorization.

### B. Knowledge base and RAG
- Upload selected document types (initially PDF, DOCX, and TXT if feasible).
- Extract text, chunk content, create embeddings, and index chunks.
- Retrieve relevant passages using semantic and keyword/hybrid retrieval.
- Answer with source citations and clear limitations when evidence is insufficient.

### C. Operational data intelligence
- Work with synthetic incidents, support tickets, and payment transactions.
- Expose a small set of validated, read-only query tools.
- Return structured data and explain the source and time range.
- Never allow unrestricted model-generated SQL execution.

### D. Agentic investigation workflow
- Use a controlled workflow to decide which approved tools to call.
- Keep state and execution steps understandable and inspectable.
- Combine retrieved documents and operational data.
- Produce an investigation report with evidence, hypotheses, and recommended next actions.

### E. MCP tool integration
- Expose selected business capabilities through an MCP server.
- Validate tool arguments and caller permissions.
- Keep tool descriptions and outputs explicit and bounded.

### F. Governance and human approval
- Role-based access control and least privilege.
- Human approval for sensitive or irreversible actions.
- Audit events for agent runs, tool calls, approvals, and outcomes.
- Treat documents, user input, and tool outputs as untrusted data.

### G. Observability and evaluation
- Inspect agent runs and tool calls.
- Track errors, latency, token usage, and estimated cost where available.
- Evaluate retrieval relevance, citation correctness, and task completion.
- Maintain repeatable test cases and regression checks.

## 6. Candidate technology direction

These are provisional choices to evaluate during architecture and design—not mandatory commitments.

| Concern | Candidate | Notes |
|---|---|---|
| Frontend | Next.js, React, TypeScript | Leverages existing frontend strengths. |
| UI | Tailwind CSS, shadcn/ui | Use where useful; avoid premature UI complexity. |
| Backend API | Python, FastAPI, Pydantic | Builds on Python and introductory Flask knowledge. |
| Relational database | PostgreSQL | Reuse SQL foundation; explore PostgreSQL features. |
| ORM / migrations | SQLAlchemy, Alembic | Learn mapping, migrations, and transaction boundaries. |
| Vector retrieval | pgvector | Evaluate whether it is sufficient for the initial scale. |
| AI integrations | LLM API, LangChain | Use only the abstractions that solve real integration needs. |
| Agent orchestration | LangGraph | Candidate for stateful, multi-step, approval-aware workflows. |
| Tool interoperability | MCP | Expose a deliberately small set of business tools. |
| Cache / background work | Redis | Add only when asynchronous jobs or shared state justify it. |
| Observability | OpenTelemetry and/or Langfuse | Decide after defining what needs to be measured. |
| Tests | Pytest and frontend test tooling | Include unit, integration, and evaluation tests. |
| Packaging | Docker / Docker Compose | Reproducible local setup and deployment. |

## 7. Non-goals for the first MVP

- Training a foundation model or ML model from scratch.
- Building a general-purpose autonomous agent that can do anything.
- Unrestricted production database access or arbitrary write queries.
- Connecting to real customer systems or processing real customer data.
- Multi-agent swarms without a demonstrated need.
- Kubernetes, Kafka, Terraform, or complex distributed infrastructure unless a concrete requirement emerges.
- Supporting every file type or every LLM provider in the first release.

## 8. MVP success criteria (to refine after discovery)

A demonstrable MVP should allow an authorized user to:

1. Sign in and access a workspace.
2. Upload a small set of sample operational documents.
3. Ask a question and receive an answer grounded in retrieved evidence with citations.
4. Ask for an investigation of a seeded payment incident.
5. See the agent use a limited set of approved read-only tools.
6. Review an investigation summary that distinguishes facts from hypotheses.
7. Approve or reject at least one proposed action.
8. Inspect the corresponding execution and audit history.
9. Run a repeatable set of basic functional and AI evaluation tests.

The exact acceptance criteria, data model, API contracts, security boundaries, and deployment target must be designed and agreed before implementation.

## 9. Portfolio objective

The project should demonstrate the ability to discover a business problem, make and defend technical decisions, design a full-stack system, integrate AI capabilities responsibly, build and test it independently, deploy it, and communicate its behavior and limitations.

Do not claim production readiness or quantified performance improvements without evidence from testing and deployment.
