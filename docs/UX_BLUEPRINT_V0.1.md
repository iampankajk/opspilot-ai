# OpsPilot AI — UX Blueprint v0.1

**Status:** Approved by product owner  
**Purpose:** Define the structure and interaction model of the OpsPilot investigation workspace.

---

## 1. UX objective

The OpsPilot investigation workspace should help a Payments Operations Engineer investigate payment-related incidents by moving naturally between:

- Understanding the incident and affected payment cases.
- Inspecting evidence from different sources.
- Reviewing findings and deciding what the evidence actually supports.
- Asking the AI assistant questions without losing investigation context.

The interface should support evidence-based investigation while keeping final decisions with the human engineer.

## 2. Overall workspace structure

The investigation workspace has four persistent areas:

| Area | Position | Responsibility |
|---|---|---|
| Incident Overview | Top | Shared incident information |
| Investigation Threads | Left sidebar | Navigate between investigation types |
| Main Workspace | Center | View Overview, Evidence or Findings |
| OpsPilot AI Assistant | Right panel | Ask questions and explore the selected investigation |

### Conceptual layout

```text
┌──────────────────────────────────────────────────────────────┐
│                     INCIDENT OVERVIEW                        │
│       Incident ID · Severity · Region · Date · Category      │
├───────────────┬────────────────────────────┬─────────────────┤
│               │                            │                 │
│ INVESTIGATION │       MAIN WORKSPACE       │   OPSPILOT AI   │
│ THREADS       │                            │                 │
│               │   Overview | Evidence |    │                 │
│ • Payment     │              Findings      │   Conversational│
│   failures    │                            │   assistant    │
│               │                            │                 │
│ • Possible    │     Selected content       │                 │
│   duplicates  │                            │                 │
│               │                            │                 │
└───────────────┴────────────────────────────┴─────────────────┘
```

This is a conceptual structure, not a pixel-perfect wireframe.

## 3. Incident Overview

The Incident Overview stays visible at the top while the engineer navigates between investigation threads and workspace sections.

It provides shared incident context, such as:

- Incident ID
- Incident category
- Severity
- Region
- Incident date

The information is shared across both investigation threads.

## 4. Investigation Threads

The left sidebar contains two investigation threads for the MVP:

1. Payment failures
2. Possible duplicates

These represent two distinct investigation contexts within the same incident.

### Thread switching behaviour

When the engineer switches threads:

- The selected thread becomes active.
- The main workspace displays that thread's content.
- The AI assistant switches to the selected thread's working context.
- Shared incident context remains available.
- Evidence, findings and relevant payment cases are focused on the selected thread.

The assistant must not silently mix evidence or conclusions from the two threads.

## 5. Main Workspace

The center area contains three sections:

### 5.1 Overview — What am I investigating?

The Overview tab gives the engineer a summary of the selected investigation thread.

It includes:

- A short investigation summary.
- Relevant aggregate metrics, where available.
- A list of individual customer/payment cases.
- Relevant case information, including references, amounts and reported issues.

#### Example case information

| Field | Example |
|---|---|
| Case reference | CASE-001 |
| Customer reference | CUST-104 |
| Payment reference | PAY-2041 |
| Amount | SGD 48.00 |
| Reported issue | Payment failure |

These are illustrative synthetic values.

The case list should help engineers identify which individual payments need closer inspection.

### 5.2 Case selection interaction

When an engineer selects an individual case from Overview:

1. OpsPilot opens the Evidence tab.
2. The selected case becomes the active case.
3. Evidence is focused on records related to that case.
4. The engineer can inspect the available records and their relationships.

The selected case should remain identifiable while the engineer explores its evidence.

### 5.3 Evidence — What information do I have?

Evidence is organized primarily by source rather than as one chronological timeline.

The following four sections remain visible:

**A. Internal Payment Records**
- Payment attempts.
- Internal payment lifecycle events.

**B. Stripe / Payment Provider**
- Provider-side payment events.
- Relevant provider identifiers and events.

**C. Logs & Traces**
- Application logs.
- Technical traces.
- Relevant request information.

**D. Support Tickets**
- Customer-reported issues.
- Relevant support ticket information.

Each evidence record should show useful identifying information, its timestamp, its source and why it is considered related to the selected case.

#### Empty evidence sections

All four source sections remain visible, even when no matching records are available.

Example:

> No matching records found in the available synthetic dataset.

This distinction matters: not finding a matching record does not prove that the event never happened or that no evidence exists elsewhere.

### 5.4 Findings — What have I established?

The Findings tab presents individual investigation claims.

Each finding should include:

- **Claim:** What the available evidence indicates.
- **AI-proposed status:** Confirmed, Not confirmed or Inconclusive.
- **Explanation:** Why the AI proposed that status.
- **Evidence references:** Supporting or contradicting records.
- **Human review:** An action to accept or correct the proposed status.

#### Example finding

**Claim:** The provider response timed out.

**AI-proposed status:** Confirmed

**Explanation:** An application log records a timeout while waiting for the provider response.

**Evidence references:**
- LOG-104
- TRACE-204

**Human review actions:**
- Accept proposed status.
- Correct status.

The examples above are illustrative, not actual investigation conclusions.

#### Human review principle

AI-proposed statuses and human-reviewed decisions must be visually distinct.

An AI suggestion must never appear as though the engineer has already accepted it.

Each claim is reviewed individually. There is no bulk acceptance of all findings.

## 6. OpsPilot AI Assistant

The assistant occupies a persistent right-side panel.

It remains available while the engineer switches between:

- Overview
- Evidence
- Findings

### Assistant context behaviour

The assistant follows the selected investigation thread.

For example:

- In Payment failures, it works with payment-failure evidence and findings.
- In Possible duplicates, it works with possible-duplicate evidence and findings.

The assistant retains the selected thread's context while the engineer moves between the three workspace sections.

Shared incident context remains available.

Cross-thread information should only be used when the engineer explicitly asks for it or when a supported relationship makes it relevant.

## 7. Expected engineer journey

The intended high-level journey is:

1. Engineer opens an incident.
2. OpsPilot displays the Incident Overview.
3. Engineer selects an investigation thread.
4. Engineer reviews its Overview and individual payment cases.
5. Engineer selects a case.
6. OpsPilot opens Evidence with that case selected.
7. Engineer inspects evidence from the four source sections.
8. Engineer moves to Findings.
9. Engineer reviews AI-proposed claims individually.
10. Engineer accepts or corrects each proposed status.
11. Engineer can ask the AI assistant questions throughout the process.

## 8. Core UX principles

The workspace should follow these principles:

1. **Human ownership:** The engineer owns investigation decisions.
2. **Evidence traceability:** Claims should link back to their underlying evidence.
3. **Visible uncertainty:** Missing or inconclusive evidence should remain explicit.
4. **Context preservation:** Moving between workspace sections should not disrupt the assistant's conversation.
5. **Thread separation:** Payment failures and possible duplicates should have distinct working contexts.
6. **Clear status ownership:** AI proposals must remain distinguishable from human-reviewed decisions.
7. **No unsupported conclusions:** Temporal relationships, missing records or incomplete provider data must not be presented as proof of a root cause or duplicate charge.

## 9. Decisions still to be designed

This blueprint intentionally does not settle every interaction detail.

The following are future design topics:

- Detailed incident entry and saved-investigation experience.
- Exact visual hierarchy and fields in Incident Overview.
- Case list layout, sorting and filtering.
- Evidence record detail presentation.
- How evidence relationships and correlation reasons are displayed.
- How findings are grouped and how corrections are recorded.
- How the assistant presents citations and references.
- How investigation revisions and saved states appear in the interface.
- Responsive layout and detailed visual design.

These should be discussed and understood before implementation.

---

**Blueprint principle:** OpsPilot should help an engineer move from incident context, to individual payment cases, to traceable evidence, to human-reviewed findings — without allowing an AI suggestion to become an unreviewed conclusion.
