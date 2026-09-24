# Portfolio v1.0 Release Roadmap

## Release-track rule

The bounded Portfolio v1.0 implementation and release gates are complete, and `v1.0.0` is released. R0 froze the scope, and R1–R5 release work implemented only what was required by the product contract and v1.0 acceptance criteria. R5-06 post-release propagation remains active; new functionality belongs to post-v1.0 tracks.

```text
R0 — Release Baseline, Product Contract & Scope Freeze
R1 — Enterprise Authorization & Safe Actions v1
R2 — Real Ticket Workflow + Real MCP Vertical Slice
R3 — Cloud + Production Observability v1
R4 — Security / Release Hardening
R5 — Portfolio v1.0
      ↓
   tag v1.0.0
      ↓
   stop feature development for v1.0
```

## R0 — Release Baseline, Product Contract & Scope Freeze

Status: **complete**

Goals:

- define the product and reference domain;
- freeze the v1.0 feature boundary;
- document personas, current architecture, security baseline, known limitations, and acceptance criteria;
- clean stale JSON-era configuration/code and clearly obsolete tutorial-era documentation;
- create the definitive release backlog.

R0 does not introduce new product capabilities.

## R1 — Enterprise Authorization & Safe Actions v1

Status: **complete**

Release reason: authentication and conversation ownership exist, but privileged operations and side-effect policy are incomplete.

Bounded goals:

- introduce the minimum role/permission model required by the reference application;
- protect privileged RAG indexing;
- distinguish explicit ticket creation from troubleshooting-only requests;
- enforce action policy in Python/service/tool boundaries rather than prompts alone;
- activate the remaining reserved ambiguous-ticket evaluation only when implemented.

Not in R1: real persisted ticket feature, MCP redesign, cloud deployment.

## R2 — Real Ticket Workflow + Real MCP Vertical Slice

Status: **complete**

Release reason: v1.0 should demonstrate one real bounded enterprise action rather than only simulated tools.

Bounded goals:

- PostgreSQL-backed tickets with ownership/status fields appropriate to the small reference workflow;
- service/repository/API layer;
- minimal React ticket view;
- assistant uses the bounded business capability under R1 authorization;
- one end-to-end MCP path for the same capability;
- deterministic tests/evaluations for the vertical slice.

One convincing capability is sufficient. Do not add a catalog of fake tools.

## R3 — Cloud + Production Observability v1

Status: **complete**

Release reason: the portfolio needs a real deployment story and request-level production operations baseline.

Completed scope:

- Cloud Run topology for public frontend/backend and private IAM-protected MCP service;
- Cloud SQL PostgreSQL plus explicit one-off Cloud Run migration Job;
- Cloud SQL + pgvector selected as the durable cloud RAG backend while Chroma remains a local option;
- Secret Manager runtime secret injection and distinct frontend/backend/MCP/migration/deployment service identities;
- Google identity-token authentication for backend → MCP;
- environment-driven frontend API/backend CORS configuration;
- OpenTelemetry traces exported through OTLP plus structured Cloud Logging-compatible stdout;
- request/provider/tool/RAG/MCP/ticket correlation, including R2 partial-success visibility;
- conservative Cloud Run scaling/database-pool baselines;
- Artifact Registry images and manual GitHub deployment using Workload Identity Federation.

R3 completed authoritative integration, live GCP deployment and the runbook smoke checks. R4 subsequently completed security/release hardening and live acceptance. R5 then packaged the accepted system as Portfolio v1.0.0; the release gates are complete and R5-06 post-release propagation remains active.

## R4 — Security / Release Hardening

Status: **complete**

Release reason: deployment alone is not a release.

Completed scope:

- explicit chat/login limits and a documented process-local rate-limiting baseline;
- repeatable Python/frontend dependency security checks;
- frontend lint plus a narrow backend correctness-quality gate;
- additional negative ownership/limit/failure regressions while preserving the R1/R2 suite;
- production HTTPS-origin validation, narrower CORS methods/headers and a bounded nginx browser-header baseline;
- separate liveness and PostgreSQL-aware readiness for backend/MCP plus Cloud Run probe configuration;
- non-destructive load/failure smoke tooling;
- a deployed browser/mobile acceptance matrix;
- synthetic public-demo-data cleanup and repository guard;
- explicit threat model and residual-risk decisions, including the shared database principal;
- deterministic user-facing confirmation when a durable ticket exists but final answer providers are exhausted.

R4 completed independent integration, CI, merged deployment, live rate/readiness/header/load/browser acceptance, provider/log regression verification, public-data review, secret-version cleanup, and final security/residual-risk review. `docs/hardening-r4.md` is the acceptance record.

## R5 — Portfolio v1.0

Status: **released; post-release propagation active** — release outcome: **Portfolio v1.0.0**

Release reason: convert the working repository into a concise, reviewable portfolio artifact.

Bounded goals:

- final README and quick start;
- architecture/sequence/ER/RAG/evaluation/MCP diagrams as useful;
- screenshots;
- short demo video or equivalent live-demo walkthrough;
- architecture and AI-quality explanation;
- security/limitations/future-work section;
- release notes;
- `v1.0.0` tag;
- portfolio/CV/LinkedIn packaging.

R5 ended feature development for v1.0.

## Post-v1.0 tracks

### Mastery track

- reconstruct major components from a blank repository;
- explain architectural decisions without notes;
- debugging exercises;
- interview/system-design practice;
- detailed learning guide.

### v1.1 / v2 backlog

- richer roles;
- more tools/workspaces;
- additional domains;
- advanced RAG;
- provider comparison experiments;
- scaling features when justified.

### Separate projects

- model training/fine-tuning;
- decision-support/optimization system;
- Kubernetes/advanced distributed deployment.