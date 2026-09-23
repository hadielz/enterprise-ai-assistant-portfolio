# Product Scope and Contract

## Product definition

Enterprise AI Assistant is a production-oriented reference application for an **Internal Enterprise Operations Assistant**. It demonstrates how a reusable enterprise-AI core can combine authenticated conversations, internal knowledge retrieval, bounded tools, multiple LLM providers, agent orchestration, persistence, deterministic evaluation, and CI.

It is not intended to be a generic ChatGPT clone or a finished enterprise SaaS product. The repository is a portfolio reference system whose v1.0 release must be coherent, deployable, testable, and defensible without pretending to provide enterprise-scale completeness.

## Current reference domain

The current reference domain is internal enterprise operations. The application can presently support:

- authenticated users with private, user-owned conversations;
- general assistant questions;
- company-policy questions grounded through RAG over the demo knowledge base;
- simple arithmetic through a calculator tool;
- persisted IT ticket creation guarded by deterministic safe-action policy and executed through MCP;
- streamed and non-streamed chat responses;
- persisted conversation history and summaries;
- multiple LLM providers with fallback;
- deterministic AI behavior evaluation and a CI quality gate;
- an accepted cloud-reference deployment using Cloud Run, Cloud SQL/pgvector, private MCP invocation, managed secrets and OpenTelemetry.

R1 established the intentionally small v1.0 authorization model: every registered user is an `employee` by default, while the `support` role is a privileged operator capability assigned administratively rather than through public registration. Broader enterprise RBAC remains outside v1.0.

## Primary v1.0 personas

### Employee

An authenticated internal user who can:

- ask general questions;
- ask questions about authorized internal policies;
- maintain private conversation history;
- perform safe calculations;
- explicitly request a support ticket through the assistant under the R1 safe-action contract;
- view their own persisted tickets.

### Support operator

A minimal privileged persona implemented in R1. It can perform privileged operational actions such as knowledge-base indexing. The role is assigned server-side/administratively; public registration cannot request it. R2 uses this authorization boundary for the real ticket workflow and support status operations.

### Developer / operator

A repository and deployment persona rather than an end-user product role. This person configures providers, indexes the demo knowledge base, runs migrations, operates CI, deploys the service, and reviews telemetry.

## v1.0 product contract

The implemented product contract for Portfolio v1.0 is one coherent vertical slice:

1. A user authenticates to the application.
2. Their conversations are isolated and persisted in PostgreSQL.
3. The assistant can answer ordinary questions.
4. Internal-policy questions use authorized RAG context rather than inventing policy.
5. The assistant can select bounded tools.
6. Side-effecting support-ticket actions are authorized and safe.
7. Tickets are real persisted application entities with relational ownership, bounded status transitions, and an actual internal MCP creation path.
8. At least one real MCP path connects the assistant to a bounded enterprise capability.
9. The reference application is deployable to GCP with Cloud Run, Cloud SQL and a durable pgvector cloud RAG design; live R3/R4 acceptance verified the reference environment.
10. Important request/provider/tool/RAG/MCP operations are observable through an OpenTelemetry tracing and structured-logging baseline.
11. Security and release-hardening checks are documented and repeatable.
12. Deterministic AI evaluation remains a required CI gate.
13. The repository explains architecture, trade-offs, limitations, setup, and verification clearly enough for another engineer to evaluate it.

## Product behavior boundaries

### General knowledge versus enterprise knowledge

The assistant is intentionally a general helpful assistant **plus** an enterprise-context assistant. It is not restricted to answering only from internal documents.

When internal context is supplied, company-policy answers must be grounded in that context and must not invent policies. Ordinary harmless questions may still be answered from model knowledge.

### Tool authority

The LLM does not receive unrestricted database access. Business actions must follow this boundary:

```text
LLM intent
  ↓
authorized application tool
  ↓
validation / permission check
  ↓
application service / repository
  ↓
PostgreSQL or external integration
```

The model may request a capability; it may not bypass authorization or directly execute arbitrary SQL.

### AI provider behavior

External model responses are probabilistic. The application controls prompts, history, RAG context, tools, provider choice, validation, fallback, logging, and regression tests, but it does not promise identical wording across providers.

The product contract therefore focuses on observable properties such as route, tool, source, protocol status, prompt contract, persistence behavior, and failure handling where deterministic assertions are possible.

## Explicit non-goals for v1.0

The following are outside the frozen v1.0 scope unless a release milestone uncovers a concrete blocking need:

- Kubernetes;
- Redis merely for architectural completeness;
- additional LLM providers beyond OpenAI, Gemini, Ollama, and Mock;
- a large multi-agent organization;
- broad ERP/customer-support/admin workspaces;
- dozens of enterprise tools;
- direct LLM database administration;
- training or fine-tuning a custom LLM;
- decision-support/optimization systems;
- multi-region high availability, disaster recovery, or 100,000-user scale claims;
- rich analytics dashboards;
- multiple business-domain packs.

These belong to post-v1.0 work or separate projects.

## Scope-freeze rule

A new feature may enter v1.0 only if it is required to satisfy an acceptance criterion in `docs/release-checklist.md` or to correct a release-blocking defect. Otherwise it is recorded in the backlog and does not expand the release.
