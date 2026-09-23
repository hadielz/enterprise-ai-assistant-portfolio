# Known Limitations and Technical Debt

This inventory is part of the frozen Portfolio v1.0 release track. It separates
accepted reference-system trade-offs, completed R4 hardening, R5
packaging, and post-v1.0 ideas.

## Resolved through R3

R0 removed stale JSON-era runtime/configuration and repaired documentation drift.
R1 added database-authoritative employee/support authorization plus deterministic
safe-action policy. R2 added persisted tickets, bounded ownership/status rules, a
real Streamable-HTTP MCP vertical slice and trusted MCP-result validation.

R3 resolved the cloud-architecture gaps by adding:

- a durable pgvector cloud RAG option rather than Cloud Run local Chroma files;
- explicit Cloud SQL connectivity and migration deployment;
- Secret Manager production secret injection;
- private Cloud Run MCP invocation with Google identity tokens;
- runtime-configurable frontend API/backend CORS;
- OpenTelemetry traces and correlated JSON logs;
- bounded Cloud Run scaling/database pools;
- manual GitHub/GCP deployment using Workload Identity Federation.

The formerly unused `GenerationContext` model was retired in R3; runtime
correlation uses the actual request context/OpenTelemetry layer.

## R4 changes that address prior release gaps

R4 adds:

- an 8,000-character chat input ceiling and bounded OAuth login credential length;
- process-local rate limits for public auth, chat, privileged indexing and ticket
  status mutation;
- explicit production HTTPS-origin validation and narrower CORS methods/headers;
- a small nginx browser-security-header baseline;
- backend/MCP liveness-versus-DB-readiness endpoints and cloud probe configuration;
- repeatable Ruff, `pip-audit`, npm lint/audit and public-repository guard checks;
- an additional cross-owner conversation-delete negative regression;
- a deterministic user-facing response when ticket persistence succeeded but
  final answer providers were exhausted;
- a non-destructive bounded load-smoke script;
- a browser/mobile acceptance matrix;
- synthetic demo identity/PDF metadata cleanup;
- an explicit R4 threat model and residual-risk decisions.

These controls completed independent integration, CI and the required Stage-B
live acceptance and are part of the accepted R4 baseline.

## Known limitations intentionally retained for v1.0

### Local and cloud vector backends are not numerically identical

Chroma remains the local default and pgvector the cloud reference backend. Both
preserve the application retrieval/source contract, but their internal distance
and index behavior is not claimed to yield bit-identical rankings for every
corpus/query. R4 does not retune retrieval without evidence.

### Local Chroma dependency has reviewed unresolved advisories

The local Chroma backend currently resolves to a release for which
`pip-audit` reports `PYSEC-2026-311`, `PYSEC-2026-3813`,
`PYSEC-2026-3814`, and `PYSEC-2026-3815`.

The R4 release accepts these findings as a temporary scoped exception
because this project uses Chroma through the embedded
`PersistentClient` local path and the production deployment uses
pgvector rather than Chroma. The exception does not assert that ChromaDB
itself is vulnerability-free and must be removed or reassessed when a
fixed upstream release becomes available or if Chroma network/server
functionality is introduced.

### Fixed embedding dimension

The pgvector schema uses 1536 dimensions for the release reference embedding
path. A later embedding-dimensionality change requires an explicit schema/reindex
migration.

### Cloud SQL is the main always-on cost

Cloud Run services can scale to zero, while Cloud SQL remains a provisioned
managed database and the main likely ongoing cost driver.

### Instance-based Cloud Run CPU has a cost trade-off

Backend and MCP use instance-based CPU so the OpenTelemetry batch exporter can
work outside active request handling. `min instances = 0` still permits scale to
zero, but allocated instances can cost more than request-based CPU.

### Shared PostgreSQL principal across bounded runtime components

Backend, MCP and migration retain distinct Google service accounts but share the
R3 built-in PostgreSQL application credential. The principal is broader than the
ideal least-privilege runtime role.

R4 explicitly reviewed splitting database principals and accepts the current
layout for the single v1.0 demo environment because safely changing role/object
ownership/default privileges, multiple secrets and rollback behavior late in the
release is disproportionate to the bounded threat reduction. Future environments
should prefer separate migration/runtime DB roles from provisioning time.

### Process-local rate limiting

The R4 limiter is per backend process/Cloud Run instance. It provides a bounded
burst/cost-abuse baseline and returns 429 with `Retry-After`, but it is not a
globally consistent quota or DDoS defense. Cloud Run max-instance limits remain
part of the aggregate bound. Redis/Cloud Armor architecture is deferred unless a
future exposure/scale requirement justifies it.

### No full Content Security Policy

The R4 frontend adds low-risk security headers but not a full CSP. A useful
`connect-src` policy would need deployment-aware handling for the runtime
cross-origin backend URL and browser acceptance. This is a visible residual, not
a claim that the application has a complete browser policy.

### Access-token-only JWT/sessionStorage

The SPA stores the access token in `sessionStorage`; successful same-origin XSS
could read it. There is no refresh/revocation/session service. R4 does not add a
new auth platform solely to eliminate this bounded residual.

### No document-level RAG authorization

Indexing is support-only, but retrieval has no per-document/department ACL model.
The v1.0 corpus is synthetic and uniform. A real multi-department confidential
knowledge product would require document/tenant authorization before reusing this
boundary.

### Direct OTLP trace export, no collector

R3/R4 export traces directly to Google's OTLP endpoint and use Cloud Run stdout
for logs. There is no collector, custom metrics pipeline or Prometheus/Grafana
stack because the declared reference scale does not require one.

### Trace sampling is bounded

`request_id` remains in structured logs, but ratio sampling means not every
successful request has a complete exported trace.

### Streaming and non-streaming remain separate orchestrations

Non-streaming uses LangGraph while streaming is service-orchestrated. AI Quality
characterizes semantic parity and known differences. R4 does not refactor them.

### Known route/provider-failure representation differences remain

Valid no-tool + empty retrieval can expose `route=rag, used_rag=false` in
non-streaming while streaming's route remains `chat`. Ordinary all-provider
exhaustion also remains different between the two paths as previously tested.

### Ticket idempotency scope remains bounded

Unique `action_id` protects one generation/action and retry of that same identity.
Two independent explicit user requests receive different IDs and can create two
tickets. This is not semantic deduplication.

### MCP Cloud Run auth remains platform IAM

The private MCP service relies on Cloud Run IAM and a Google-signed identity token
from trusted backend code. R4 does not create a custom OAuth server/service mesh.

### No DLP or secret-history scanner

The repository guard catches a bounded set of common committed credential shapes
and validates demo PDF metadata. It is not a DLP product, full entropy scanner or
Git-history secret scanner.

### Non-blocking browser UX observations

The deployed browser review also identified small usability/polish behaviors that
do not change the R4 security or workflow acceptance:

- the application does not provide its own show-password toggle, so password-reveal behavior varies by browser/platform;
- long conversations do not force-scroll to the newest message after every send/response, so manual scrolling can be needed.

These are not v1.0 hardening blockers. They should not reopen R4 and should only
be changed during R5 if a very small presentation/accessibility correction is
clearly justified, otherwise they belong to post-v1.0 polish.

## R4 acceptance status

R4 Stage-B acceptance is complete. Production rate limiting, CORS/security
headers, readiness/liveness, bounded load, browser/mobile behavior, provider/log
regressions, public-data hygiene, secret-version cleanup and final
security/limitations review were completed against merged/deployed revisions.

The real iPhone/Safari focus-zoom issue discovered during acceptance followed the
established small-fix-branch -> tests -> PR -> CI -> merge -> redeploy path before
R4 closure.

## R5 packaging work

R5 is limited to release/portfolio presentation and packaging:

- recruiter-facing README/quick start;
- verified architecture/sequence/ER/RAG/evaluation/MCP diagrams;
- screenshots and concise demo walkthrough/video;
- release notes and final known-limitations/security presentation;
- final clean-checkout acceptance;
- `v1.0.0` tag after all criteria pass.

## Post-v1.0 backlog

Consider only after `v1.0.0` and a concrete requirement:

- richer role hierarchy;
- more business tools/domains;
- improved RAG/reranking/hybrid retrieval;
- distributed rate limiting if actual multi-instance guarantees require it;
- collector-based observability/custom application metrics;
- semantic action deduplication;
- optional Redis for a demonstrated cache/rate-limit/queue/state need;
- more advanced agent topologies;
- richer operator dashboards.

## Prefer separate projects

- custom LLM training/fine-tuning/evaluation;
- ML/optimization decision-support product;
- Kubernetes/GKE exercise;
- deep distributed-systems/scaling project.

## Do not add merely for resume breadth

- many extra providers;
- unrestricted SQL/model database administration;
- a large multi-agent hierarchy without workflow need;
- Kubernetes/Redis/service mesh simply to increase technology count;
- claims of enterprise-scale HA/compliance that the repository does not implement.