# OpsPilot AI — Synthetic Tabletop Evidence Package

## Status and safeguards

This is a synthetic evidence package for facilitator-led tabletop review. It is not historical company evidence, does not establish real-world frequency or customer/financial impact, and does not select a product problem. **Every record and record value below is synthetic.** No real customer data, credentials, full card details, or secrets are included.

There is no predetermined root cause or answer key. Records contain observations only; participants assess what they support. Missing, unavailable, and unconstructed information remain distinct. All relationships must be supported by identifiers explicitly present in these records.

## Exercise clock and precision

- Incident reference date: **20 October 2026**.
- Reference timezone: **Asia/Singapore**, Singapore Time (**SGT, UTC+08:00**).
- Alert: **10:30 AM SGT**, `2026-10-20T02:30:00Z`.
- Five-minute alert window: **10:25–10:30 AM SGT**, `2026-10-20T02:25Z`–`2026-10-20T02:30Z` (minute precision).
- Machine-readable event timestamps use ISO 8601 UTC. Facilitator displays use SGT. When a timestamp is shown only to a minute, no seconds are implied.
- Event time is distinct from ingestion/record-creation time. Ingestion/creation timestamps are not constructed unless explicitly listed; do not infer them.

## Starting brief and alert

### Record SYN-PD-ALERT-001 — SYNTHETIC

| Field | Synthetic value |
|---|---|
| Source system | PagerDuty incident record; alert source is Grafana |
| Event timestamp | 10:30 AM SGT / `2026-10-20T02:30:00Z` (second precision as specified for the alert) |
| Provenance | Constructed synthetic record based on the approved fictional alert scenario |
| Incident reference | `INC-2026-1042` (fictional scenario identifier) |
| Alert title | Payment failure rate exceeded threshold |
| Severity | SEV-2 (High) |
| Affected service | Payment Processing |
| Alert source | Grafana |
| Current failure rate | 12.4% |
| Expected rate | Below 2% |
| Measurement window | 10:25–10:30 AM SGT |
| Region | APAC |
| Trigger time | 10:30 AM SGT / `2026-10-20T02:30:00Z` |
| Status | Triggered |
| Links in scenario | Grafana dashboard and troubleshooting runbook (link destinations not constructed) |

### Starting brief — SYNTHETIC scenario text

At 10:30 AM SGT, payment monitoring reports an elevated failure rate in APAC. Support has received approximately 15 complaints: the scenario brief identifies three as possible duplicate-charge reports. The alert confirms abnormal payment behavior; it does not confirm duplicate captures or their cause. The count and symptoms are scenario assumptions, not a sample of real tickets.

**Brief metadata:** Source is the facilitator-prepared fictional exercise brief; referenced event time is 10:30 AM SGT (minute precision); provenance is synthetic scenario content. It is not a separate source-system record.

The participant receives only this brief and alert initially. The source records below are released on request.

## Minimum connected record inventory

### Grafana / Prometheus

#### Record SYN-GRAF-METRIC-001 — SYNTHETIC

| Field | Synthetic value |
|---|---|
| Source system | Prometheus metric displayed/queryable through Grafana |
| Event timestamps | Five consecutive one-minute buckets, 10:25–10:30 AM SGT / `2026-10-20T02:25Z`–`2026-10-20T02:30Z` (minute precision) |
| Provenance | Constructed synthetic aggregate series; not retrieved from a real monitoring system |
| Metric | Payment failure rate |
| Window | 10:25–10:30 AM SGT / `2026-10-20T02:25Z`–`2026-10-20T02:30Z` |
| Region | APAC |
| Per-minute series | 10:25–10:26: 16 failures / 80 attempts = 20%; 10:26–10:27: 15 / 100 = 15%; 10:27–10:28: 15 / 120 = 12.5%; 10:28–10:29: 8 / 100 = 8%; 10:29–10:30: 8 / 100 = 8% |
| Aggregate calculation | 62 failures / 500 attempts = 12.4% across the five buckets; calculate as total failures divided by total attempts (attempt-weighted) |
| Comparison threshold stated in alert | Below 2% |
| Provider, method, error-code breakdown | Not constructed |
| Unique-customer counts | Not constructed |
| Ingestion timestamp | Not constructed |

This is a minimal synthetic trend series. It does not provide pre-window trend points or diagnostic breakdowns.

### Zendesk and Support handoff

#### Record SYN-ZD-TICKET-001 — SYNTHETIC, representative failure complaint

| Field | Synthetic value |
|---|---|
| Source system | Zendesk |
| Event timestamp | Ticket-created time: 10:31 AM SGT / `2026-10-20T02:31Z` (minute precision); approximate payment time is separately customer-reported |
| Provenance | Constructed synthetic ticket; identifier source is stated below, and complaint content/time are customer-reported within the fictional scenario |
| Ticket reference | `SYN-ZD-TICKET-001` |
| Created | 10:31 AM SGT / `2026-10-20T02:31Z` (minute precision) |
| Reported issue | Payment did not complete; customer reports a timeout message |
| Customer reference | `SYN-CUST-001` |
| Order reference | `SYN-ORD-001` |
| Reported amount/currency | SGD 48.00 |
| Approximate payment time | 10:27 AM SGT |
| Transaction ID supplied by customer | None |
| Identifier provenance | Customer ID and Order ID are fictional trusted portal fields; complaint and approximate time are customer-reported |

#### Record SYN-ZD-TICKET-002 — SYNTHETIC, possible-duplicate complaint

| Field | Synthetic value |
|---|---|
| Source system | Zendesk |
| Event timestamp | Ticket-created time: 10:33 AM SGT / `2026-10-20T02:33Z` (minute precision); approximate payment time is separately customer-reported |
| Provenance | Constructed synthetic ticket; identifier source is stated below, and complaint content/time are customer-reported within the fictional scenario |
| Ticket reference | `SYN-ZD-TICKET-002` |
| Created | 10:33 AM SGT / `2026-10-20T02:33Z` (minute precision) |
| Reported issue | Customer reports seeing two charges for one purchase |
| Customer reference | `SYN-CUST-002` |
| Order reference | Not supplied in the ticket |
| Reported amount/currency | SGD 120.00 |
| Approximate payment time | 10:17–10:18 AM SGT |
| Transaction ID supplied by customer | None |
| Identifier provenance | Customer ID is a fictional trusted portal field; amount and approximate time are customer-reported |
| Bank/issuer evidence | Not supplied; posting status unknown |

#### Record SYN-ZD-HANDOFF-001 — SYNTHETIC Support lookup history

| Field | Synthetic value |
|---|---|
| Source system | Authorized read-only customer/order lookup interface; history attached to the synthetic Zendesk handoff |
| Event timestamp | Lookup event: 10:36 AM SGT / `2026-10-20T02:36Z` (minute precision) |
| Provenance | Constructed synthetic Support lookup history; search/results are fictional exercise data |
| Related ticket | `SYN-ZD-TICKET-002` |
| Search time | 10:36 AM SGT / `2026-10-20T02:36Z` (minute precision) |
| Search criteria | Customer `SYN-CUST-002`; SGD 120.00; 10:00–10:30 AM SGT |
| Source searched | Authorized read-only customer/order lookup interface |
| Candidate records returned | `SYN-PO-ATT-002-A`, `SYN-PO-ATT-002-B` |
| Search result | Two attempts associated with one candidate order, `SYN-ORD-002` |

#### Record SYN-ZD-ESCALATION-001 — SYNTHETIC Support escalation packet

| Field | Synthetic value |
|---|---|
| Source system | Zendesk |
| Event timestamp | Escalation event: 10:40 AM SGT / `2026-10-20T02:40Z` (minute precision) |
| Provenance | Constructed synthetic Support escalation packet; its intentional omission is an exercise condition, not an observed company behavior |
| Related ticket | `SYN-ZD-TICKET-002` |
| Escalated | 10:40 AM SGT / `2026-10-20T02:40Z` (minute precision) |
| Included | Ticket reference, Customer ID, reported amount/currency, approximate payment time, customer-reported issue |
| Omitted from packet | Prior search criteria, systems searched, candidate order/attempt references, lookup result |

The omission is an intentional **synthetic exercise condition**, not an observed company behavior. The underlying Support lookup history is separately discoverable. It allows the participant to determine whether a later lookup is a repeat, an extension, necessary independent verification, or unclear.

### Internal Payment Operations Console

#### Record SYN-PO-ATT-001 — SYNTHETIC failure-path attempt

| Field | Synthetic value |
|---|---|
| Source system | Internal Payment Operations Console |
| Event timestamp | Payment attempt event: 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Provenance | Constructed synthetic transaction record; identifiers and values are fictional |
| Transaction / attempt | `SYN-TXN-001` / `SYN-PO-ATT-001` |
| Customer / order | `SYN-CUST-001` / `SYN-ORD-001` |
| Amount/currency | SGD 48.00 |
| Event time | 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Internal status | Outcome unknown after timeout |
| Sanitized internal error | `PROVIDER_REQUEST_TIMEOUT` |
| Provider reference / request | `SYN-PI-FAIL-001` / `SYN-REQ-FAIL-001` |
| Trace reference | `SYN-TRACE-FAIL-001` |
| Application version field | `v2.8.1` (synthetic; inherited from the previously discussed fictional rollout assumption) |
| Idempotency/retry detail | Not constructed for this attempt |

#### Records SYN-PO-ATT-002-A and SYN-PO-ATT-002-B — SYNTHETIC possible-duplicate path

| Field | `SYN-PO-ATT-002-A` | `SYN-PO-ATT-002-B` |
|---|---|---|
| Source system | Internal Payment Operations Console | Internal Payment Operations Console |
| Event timestamp / timezone / precision | 10:17 AM SGT / `2026-10-20T02:17Z`, minute precision | 10:18 AM SGT / `2026-10-20T02:18Z`, minute precision |
| Provenance | Constructed synthetic transaction record | Constructed synthetic transaction record |
| Transaction / attempt | `SYN-TXN-002` / `SYN-PO-ATT-002-A` | `SYN-TXN-002` / `SYN-PO-ATT-002-B` |
| Customer / order | `SYN-CUST-002` / `SYN-ORD-002` | `SYN-CUST-002` / `SYN-ORD-002` |
| Amount/currency | SGD 120.00 | SGD 120.00 |
| Event time | 10:17 AM SGT / `2026-10-20T02:17Z` (minute precision) | 10:18 AM SGT / `2026-10-20T02:18Z` (minute precision) |
| Internal attempt status | Timeout; provider outcome initially unknown | Succeeded |
| Provider reference | `SYN-PI-DUP-001` | `SYN-PI-DUP-001` |
| Provider request reference | `SYN-REQ-DUP-A` | `SYN-REQ-DUP-B` |
| Idempotency key | `SYN-IDEM-DUP-001` | `SYN-IDEM-DUP-001` |
| Capture reference | Not present on this attempt row | `SYN-CAP-DUP-001` |

These synthetic records intentionally distinguish two attempts from provider capture events. They do not state a conclusion about the customer's bank posting.

### Stripe provider records

#### Record SYN-STRIPE-FAIL-001 — SYNTHETIC, failure path

| Field | Synthetic value |
|---|---|
| Source system | Stripe provider event/dashboard extract (synthetic fixture) |
| Event timestamp | Returned event time: 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Provenance | Constructed synthetic provider record; no real Stripe data was accessed |
| Payment Intent | `SYN-PI-FAIL-001` |
| Related provider request | `SYN-REQ-FAIL-001` |
| Event time | 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Provider Payment Intent status observed in the returned synthetic extract | Processing |
| Capture event in this returned extract | None present |
| Extract completeness | **Not independently verified.** Completeness of the returned Payment Intent event set through 10:30 AM is unknown; absence of a capture in this returned extract does not prove no additional capture existed |
| Settlement/bank posting evidence | Not constructed |

#### Record SYN-STRIPE-DUP-001 — SYNTHETIC, possible-duplicate path

| Field | Synthetic value |
|---|---|
| Source system | Stripe provider event/dashboard extract (synthetic fixture) |
| Event timestamps | Listed event times are SGT / UTC at minute precision; returned event-set scope is through 10:30 AM SGT |
| Provenance | Constructed synthetic provider record; no real Stripe data was accessed |
| Payment Intent | `SYN-PI-DUP-001` |
| Related internal attempts | `SYN-PO-ATT-002-A`, `SYN-PO-ATT-002-B` |
| Provider requests | `SYN-REQ-DUP-A`, `SYN-REQ-DUP-B` |
| Idempotency key shown on both requests | `SYN-IDEM-DUP-001` |
| Returned lifecycle events | Two request/attempt references; one authorization reference `SYN-AUTH-DUP-001`; one capture reference `SYN-CAP-DUP-001` for SGD 120.00 |
| Capture event time | 10:18 AM SGT / `2026-10-20T02:18Z` (minute precision) |
| Other event-specific timestamps | Not constructed |
| Reversal/refund event in returned extract | None present |
| Extract scope and completeness | Returned Payment Intent event set through 10:30 AM SGT; **completeness has not been independently verified**. One capture reference is present in the returned set, but this does not prove that no additional capture existed |
| Settlement/bank posting evidence | Not constructed |

The record gives the participant lifecycle evidence to assess; it contains no facilitator-authored conclusion. Provider capture evidence is not issuer/bank posting evidence. Settlement and bank-posting status remain unknown.

### Loki logs and Tempo trace

#### Record SYN-LOKI-FAIL-001 — SYNTHETIC

| Field | Synthetic value |
|---|---|
| Source system | Grafana Loki (application log) |
| Event timestamp | 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Provenance | Constructed synthetic structured log; not retrieved from a real logging system |
| Event time | 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Service/region | Payment Processing / APAC |
| Attempt / provider request | `SYN-PO-ATT-001` / `SYN-REQ-FAIL-001` |
| Trace ID | `SYN-TRACE-FAIL-001` |
| Application version | `v2.8.1` (synthetic; inherited fictional assumption) |
| Sanitized event | Application recorded a timeout while awaiting the provider request outcome |
| Provider response body | Not present in this application log |
| Ingestion timestamp | Not constructed |

#### Record SYN-TEMPO-FAIL-001 — SYNTHETIC

| Field | Synthetic value |
|---|---|
| Source system | Grafana Tempo (distributed trace) |
| Event timestamp | 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Provenance | Constructed synthetic trace; not retrieved from a real tracing system |
| Trace ID | `SYN-TRACE-FAIL-001` |
| Related attempt/request | `SYN-PO-ATT-001` / `SYN-REQ-FAIL-001` |
| Event time | 10:27 AM SGT / `2026-10-20T02:27Z` (minute precision) |
| Application span result | Deadline exceeded while awaiting outbound provider request result |
| Application version | `v2.8.1` (synthetic; inherited fictional assumption) |
| Provider-side span | Not present in this trace |
| Ingestion timestamp | Not constructed |

The log and trace link to one another through the explicit trace/request identifiers. Their contents do not distinguish provider delay, regional connectivity, or application behavior as the root cause.

### Deployment history and configuration audit evidence

#### Record SYN-DEPLOYMENT-TIMELINE-001 — SYNTHETIC fixture

**Source/provenance:** Facilitator-constructed deployment timeline fixture, not an independently retrieved release-ledger record. The event times below are SGT, mapped to UTC at minute precision.

| Event | SGT | UTC (minute precision) |
|---|---|---|
| Rolling deployment starts | 10:12 AM | `2026-10-20T02:12Z` |
| Old version `v2.8.0` / new version `v2.8.1` overlap | 10:15–10:18 AM | `2026-10-20T02:15Z`–`2026-10-20T02:18Z` |
| Fictional rollout window ends (deployment success not independently verified) | 10:20 AM | `2026-10-20T02:20Z` |

This reuses the previously discussed fictional timing and version mapping only. The end of the rollout window is not evidence of independently verified deployment success. No commit SHA, pull request, workflow-run ID, actor, target service/environment/region scope, deployment success telemetry, or rollback fact is added here. Temporal proximity does not establish causation.

**Configuration audit history: not constructed.** A request for a runtime configuration or feature-flag change record receives “not constructed; scenario status unknown.” This does not imply that no change occurred.

## Evidence relationship map

```text
SYN-PD-ALERT-001 ── time window + APAC ── SYN-GRAF-METRIC-001

SYN-ZD-TICKET-001
  └─ Customer ID + Order ID ── SYN-PO-ATT-001
       ├─ provider reference + request ID ── SYN-STRIPE-FAIL-001
       └─ request ID + trace ID ── SYN-LOKI-FAIL-001 ── trace ID ── SYN-TEMPO-FAIL-001

SYN-ZD-TICKET-002
  ├─ Customer ID + amount + approximate time ── SYN-ZD-HANDOFF-001
  ├─ escalation reference ── SYN-ZD-ESCALATION-001
  └─ candidate order/attempts ── SYN-PO-ATT-002-A / SYN-PO-ATT-002-B
       └─ Payment Intent + request IDs + idempotency key ── SYN-STRIPE-DUP-001

SYN-DEPLOYMENT-TIMELINE-001 ── coarse temporal context only ── failure-path timestamps
```

The diagram states intended links only where the records above share an explicit identifier. Time proximity is contextual, not a causal link.

## Evidence availability matrix

| Evidence | Status after construction | Facilitator note |
|---|---|---|
| PagerDuty brief/alert | Provided at start | Do not reveal the source records yet. |
| Grafana aggregate metric | Discoverable on request | Provider/method/error breakdown and counts are not constructed. |
| Failure Zendesk ticket | Discoverable on request | Release the synthetic ticket fields above. |
| Possible-duplicate Zendesk ticket | Discoverable on request | Do not reveal Support lookup history unless requested. |
| Support lookup history | Discoverable on request | Return the exact search and candidate references above. |
| Support escalation packet | Discoverable on request | The omission is an intentional synthetic condition; do not characterize it as real-world frequency. |
| Internal Payment Operations records | Discoverable on request | Match only on explicitly listed identifiers and criteria. |
| Stripe failure-path event extract | Discoverable on request; scope-limited and completeness not independently verified | One returned extract lacking a capture does not prove no additional capture existed; settlement/posting status remains unknown. |
| Stripe possible-duplicate event extract | Discoverable on request; returned event set contains one capture reference, completeness not independently verified | One returned capture does not prove no additional capture existed; no bank/issuer posting evidence is constructed. |
| Loki/Tempo failure path | Discoverable on request | No provider-side span/body is included. |
| Deployment timeline fixture | Discoverable on request | Synthetic minute-level timing only; no causal interpretation. |
| Runtime configuration audit record | Not constructed | Scenario status unknown; do not say “no configuration change.” |
| Network/DNS/infrastructure telemetry | Not constructed | Scenario status unknown; not evidence against an infrastructure hypothesis. |
| Complete workflow logs, source diff, PR, commit SHA, settlement records | Not constructed | Do not infer their contents from references or timing. |
| Exists in scenario but unavailable | None designated in this minimum package | Add only by explicit later design, with a stated reason. |
| Conflicting evidence | None deliberately constructed | If a conflict is later added, label the disagreeing fields without resolving it for the participant. |

## Facilitator release guide

Release evidence in response to participant requests, not as a fixed walkthrough. Normalize each request by source, identifier type/value, time range, and filters. Equivalent requests receive equivalent responses. Do not improvise records or advise where to look next.

| Participant request | Release |
|---|---|
| Review alert/dashboard or query APAC failure rate | `SYN-GRAF-METRIC-001`; provide the five minute buckets and 62/500 weighted aggregate; state that provider/method/error breakdown and unique-customer counts are not constructed. |
| Retrieve the failure complaint or search by its synthetic customer/order reference | `SYN-ZD-TICKET-001`; on valid Console query, return `SYN-PO-ATT-001`. |
| Retrieve the possible-duplicate complaint | `SYN-ZD-TICKET-002` and the escalation packet if asked for handoff material. |
| Ask what Support already searched, or request lookup history | `SYN-ZD-HANDOFF-001`, with its exact search criteria and results. |
| Search Console by `SYN-CUST-002`, SGD 120.00, and 10:00–10:30 AM SGT | Return both `SYN-PO-ATT-002-A` and `SYN-PO-ATT-002-B`. Other criteria return only records matching those criteria. |
| Inspect provider data using a listed Payment Intent/request reference | Return the corresponding Stripe record and its scope/completeness limitations. |
| Search Loki using `SYN-REQ-FAIL-001` or `SYN-TRACE-FAIL-001`; open corresponding trace | Return `SYN-LOKI-FAIL-001` and `SYN-TEMPO-FAIL-001`. |
| Review deployments around the incident | Return `SYN-DEPLOYMENT-TIMELINE-001`; state that further deployment metadata is not constructed. |
| Query configuration audit history | “Not constructed; scenario status unknown.” |
| Request an unlisted record | “Not constructed in this package; scenario status unknown,” unless the matrix explicitly marks it as existing but unavailable. |

Facilitator release time is not operational wait time. Any simulated wait must be separately specified in scenario time before the exercise; none is configured in this package.

## Specialist-response catalog

All responses are fixed synthetic scripts and refer only to evidence in this package. They do not constitute a root-cause answer. **Catalog metadata:** source is the facilitator-prepared specialist-response catalog; entries are prepared responses, not records of actual specialist messages, so event timestamp/timezone/precision are not applicable; provenance is synthetic.

| Catalog entry | Trigger | Prepared response |
|---|---|---|
| `SYN-SPEC-PE-USEFUL-001` — Payments Engineering | A scoped question about the failure-path trace/log | “The application evidence records a timeout while awaiting the provider outcome. It does not include the provider response body or establish why the timeout occurred.” |
| `SYN-SPEC-PE-CANNOT-CONFIRM-001` — Payments Engineering | Ask whether the deployment caused the failure or request retry/code-level confirmation | “The package contains no code/configuration diff, commit, or comparable version-level failure metrics, and it does not establish the application's retry implementation or how provider idempotency was handled. The same idempotency key on two requests and one capture reference in an event set whose completeness is unverified do not establish that retry logic behaved correctly or that no additional capture occurred. These records do not confirm or reject deployment causation.” |
| `SYN-SPEC-SRE-CLARIFY-001` — SRE/Infrastructure | Request lacks scope or evidence reference | “Please specify the service/region, time window, and relevant request or trace reference you want assessed.” |
| `SYN-SPEC-SRE-NOT-CONSTRUCTED-001` — SRE/Infrastructure | A scoped request for regional network/DNS/infrastructure evidence | “Network, DNS, and infrastructure telemetry was not constructed for this package, so I cannot assess that hypothesis from the available evidence.” |
| `SYN-SPEC-PROVIDER-LIMIT-001` — Provider specialist | Ask whether the customer’s bank posted two debits | “The returned provider event set contains one capture reference for the listed Payment Intent, but completeness has not been independently verified. Settlement/bank-posting evidence is not constructed, so this package cannot establish whether an additional capture existed or what the customer’s bank posted.” |
| `SYN-SPEC-UNAVAILABLE-001` — Any role, conditional | Use only if a later matrix entry explicitly marks the requested specialist unavailable | “That specialist is unavailable in this exercise.” No specialist is marked unavailable in the current package. |
| `SYN-SPEC-INACCESSIBLE-001` — Any role, conditional | Use only if a later matrix entry says evidence exists but is inaccessible | “That evidence exists in the fictional scenario but is not accessible to this responder in the exercise; its contents are not available.” No evidence is designated this way in the current package. |
| `SYN-SPEC-NOT-CONSTRUCTED-001` — Any role | Request evidence absent from the package | “That evidence was not constructed for this exercise; its scenario status is unknown.” |

Clarification prompts and conditional unavailability scripts are released exactly as written. Equivalent requests receive the same entry. No modeled specialist waiting time is configured.

## Participant status definitions and evaluation boundary

- **Confirmed:** available evidence supports the claim.
- **Not confirmed:** relevant evidence was examined but did not substantiate the claim; this does not necessarily prove it false.
- **Inconclusive:** evidence is insufficient, unavailable, or ambiguous to assess the claim.

Evaluate evidence traceability, correlation rationale, competing-hypothesis handling, uncertainty, appropriate specialist requests, and separation of active work from elapsed waiting. Do not grade against a hidden root-cause answer. These records are synthetic exercise observations only, not historical evidence or real-world validation.
