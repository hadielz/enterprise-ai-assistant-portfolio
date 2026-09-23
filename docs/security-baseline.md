# Security Baseline and Release Gaps - R4 Accepted

## Purpose

This document records the implemented security baseline through completed R4.
It is not a compliance certification or a claim of enterprise-scale security
completeness. R4 has completed independent integration, CI, deployment and the
bounded Stage-B acceptance recorded in `docs/hardening-r4.md`.

## Existing application controls preserved from R1-R3

- passwords are one-way hashed;
- JWT access tokens expire and protected requests re-resolve an active PostgreSQL user;
- conversations and tickets are relationally user-owned;
- public registration always creates `employee` users;
- `support` privilege is database-authoritative and cannot be granted by model/user prompt text;
- RAG indexing is support-only;
- the R1 safe-action gate executes before any ticket side effect;
- negated, informational, troubleshooting and ambiguous ticket language remains
  non-side-effecting even if the LLM proposes the ticket tool;
- R2 validates durable MCP ticket results against trusted
  requester/action/description/status/public-ID context;
- ticket `action_id` provides per-generation/per-action idempotency;
- the LLM has no arbitrary SQL capability;
- the cloud MCP service is IAM-private and invoked by the backend runtime identity;
- production secrets use Secret Manager and GitHub deployment uses WIF/OIDC;
- structured telemetry intentionally excludes business/user content and credentials;
- deterministic AI quality is a required CI gate.

## R4 accepted controls

### Input and action bounds

R4 adds an explicit 8,000-character maximum for chat messages and
hardens OAuth login so oversized username/password values are rejected before
password verification. Existing registration/auth field bounds, the 2,000-character
ticket-description limit, finite ticket status transitions, support-only RAG
indexing and per-action ticket idempotency remain unchanged.

### Process-local rate limiting

The backend has a thread-safe sliding-window limiter with bounded key memory. It
covers:

- registration - process-wide;
- login - process-wide plus normalized-username scope;
- streaming and non-streaming chat - one shared per-user scope;
- privileged RAG indexing - per support user;
- ticket status mutation - per authenticated user.

The limiter returns HTTP `429` with `Retry-After`. It is intentionally **per
process/Cloud Run instance**. It is a bounded abuse/cost baseline, not a global
quota, distributed anti-abuse service, or DDoS control. Cloud Run maximum-instance
limits continue to bound aggregate expansion. Redis/Cloud Armor architecture is
not added solely for v1.0 breadth.

### CORS and browser-facing headers

Production `ALLOWED_ORIGINS` must be explicit HTTPS origins. Wildcards,
credential-bearing URLs and origins containing a path/query/fragment are
rejected during runtime validation. Browser CORS permits only the application
methods (`GET`, `POST`, `PATCH`, `DELETE`) and request headers
(`Authorization`, `Content-Type`) while retaining the existing explicit-origin
and bearer-token flow.

The frontend nginx container adds:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- `Referrer-Policy: no-referrer`;
- a bounded `Permissions-Policy` disabling camera/microphone/geolocation;
- `Cache-Control: no-store` for runtime configuration;
- nginx version-token suppression.

A full CSP is not added in R4 because the production backend URL is
runtime-configured and cross-origin. A correct narrow `connect-src` policy would
need deployment-aware generation and separate browser acceptance. This remains a
visible residual rather than an ineffective broad CSP.

### Liveness/readiness

- backend `/health` is liveness-only;
- backend `/ready` checks PostgreSQL using `SELECT 1` and returns `503` when it is
  unavailable;
- MCP exposes the same liveness/readiness split;
- frontend `/health` remains an nginx process/static-server check.

Cloud Run startup/readiness probes use `/ready` for backend/MCP, while liveness
uses `/health`. External model-provider billing/quota status does not make the
whole service unready.

### Dependency and source-quality checks

R4 adds repeatable release checks:

```text
ruff check backend/app evals tests
pip-audit -r backend/requirements.txt --strict --progress-spinner off --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815
python scripts/security/repository_guard.py
npm run lint
npm audit --audit-level=high
```

Ruff is intentionally scoped to correctness-critical syntax/Pyflakes rules so
R4 does not become a repository-wide style rewrite. `pip-audit` audits project
runtime requirements; npm audit evaluates the lockfile-installed frontend tree.
Security findings are release failures unless a specific reviewed exception is
documented. R4 does not auto-upgrade dependencies or broadly suppress findings.

The R4 release has one such reviewed exception: the ChromaDB findings
`PYSEC-2026-311`, `PYSEC-2026-3813`, `PYSEC-2026-3814`, and
`PYSEC-2026-3815`. Chroma is used only as the embedded local
`PersistentClient` backend in this repository, while the production
deployment uses pgvector. No Chroma HTTP client/server path is configured.

The exception is ID-specific rather than package-wide, so newly reported
ChromaDB vulnerabilities and findings in all other dependencies continue
to fail the audit. Remove or reassess the exception when an upstream fix
is available or if the application's Chroma exposure changes.

The repository guard checks common private-key/provider/GitHub-token shapes in
public text and synthetic Author/Creator metadata on demo PDFs. It is not a DLP
engine or secret-history scanner.

### Partial-success ticket behavior

If a durable ticket is confirmed but final `tool.answer.v1` generation exhausts
all configured providers, both response paths now return a deterministic message
confirming that the ticket is persisted and identifying its public ID when
available. The existing `committed_response_failed` telemetry remains.

This does not change authorization, ticket creation order, MCP trust validation,
or idempotency. Unexpected non-provider programming failures still propagate.
Ordinary all-provider failure without a committed side effect retains the
previously characterized semantics.

## Cloud-required controls preserved from R3

### Secret handling and runtime identities

Production secrets remain Secret Manager injected rather than committed `.env`
files, image layers, frontend variables or long-lived GitHub plaintext.
Frontend, backend, MCP, migration and deployment retain distinct Google service
accounts. The frontend runtime identity has no application-cloud privilege, and
the deployment identity does not need runtime-secret read access.

### Private MCP invocation

MCP remains deployed without unauthenticated invocation. Only the backend runtime
service account receives `roles/run.invoker`. Trusted backend code obtains a
Google-signed identity token for the MCP audience and sends it in
`X-Serverless-Authorization`.

The R3 MCP Cloud Run HTTP-421 correction remains part of the security contract:
local MCP uses DNS-rebinding protection with a narrow local/Compose allowlist,
while production relies on Cloud Run's managed reverse-proxy + IAM boundary at
the inner MCP Host-validation layer.

### Cloud SQL and telemetry

Cloud Run services/jobs retain Cloud SQL Unix-socket attachment, bounded pools,
max-instance/concurrency limits and the explicit migration Job. OpenTelemetry
and structured JSON logging retain the safe-field policy. The R3 streaming
ContextVar/OTel context-preservation fix remains unchanged.

## R4 threat-model decisions / residual risks

### Shared PostgreSQL principal - accepted for v1.0

Backend, MCP and migration use distinct Google IAM identities but still share the
R3 built-in PostgreSQL application credential. That principal is broader than an
ideal runtime role. R4 reviewed a split and does not retrofit it into the already
accepted environment because safe ownership/default-privilege migration would
require multiple credentials/secrets, role/object changes and rollback work late
in the release.

The repository exposes no arbitrary LLM SQL and all ticket/authorization paths
remain bounded application capabilities. For this single demo environment the
incremental privilege reduction does not justify the migration risk. Future
environments should prefer separate migration/runtime DB roles from provisioning
time. This residual is documented in `docs/threat-model.md` and
`docs/known-limitations.md`.

### Access-token-only SPA session - accepted residual

JWTs remain access-token-only and the SPA stores the token in `sessionStorage`.
Successful same-origin XSS could read it. R4 does not add refresh/revocation or a
new session platform. Token expiry, server-side active-user resolution, existing
frontend coding practices and browser-header hardening remain the bounded v1.0
mitigations.

### Other accepted residuals

- no document-level RAG authorization model for the synthetic uniform demo corpus;
- no DLP layer;
- process-local rather than distributed rate limiting;
- no semantic ticket deduplication across independent requests;
- OpenTelemetry ratio sampling means not every successful request has a complete trace;
- no OTel Collector/custom application-metrics platform;
- no full CSP in R4.

## R4 acceptance evidence

R4 acceptance verified the controls against merged/deployed behavior rather than
source intent alone:

- the backend suite passed 192 tests and deterministic AI quality remained 41/41;
- frontend lint/build and npm audit passed, with zero reported npm vulnerabilities;
- the Python audit passed with only the four explicit reviewed ChromaDB exceptions;
- Cloud Run health/readiness probes, production CORS and frontend security headers were verified;
- a controlled production login probe returned 429 with `Retry-After`;
- the cloud `/ready` load smoke completed 100 requests at concurrency 10 with zero errors: p50 146.4 ms, p95 187.6 ms, and max 220.1 ms;
- Chrome, Edge, Firefox, responsive phone/tablet and a real iPhone/Safari path were exercised; the discovered iOS focus-zoom issue was fixed and redeployed;
- production logs showed successful OpenAI chat/embedding HTTP 200 calls, matching streaming start/completion request IDs and no streaming `ContextVar` regression;
- Cloud SQL remained `RUNNABLE` and backend `/ready` returned ready;
- the public repository guard passed from the backend container;
- superseded OpenAI/JWT/Gemini secret versions were disabled after current Secret Manager bindings/version states were verified; OpenAI v2 was exercised through successful provider calls and JWT v2 through live authentication, while Gemini v3 remained the enabled `latest` fallback without another provider call because available Gemini credits were exhausted; database secret versions were intentionally left unchanged;
- threat-model, security-baseline and known-limitations residuals were reviewed and accepted for the bounded v1.0 reference deployment.

See `docs/hardening-r4.md` for the complete acceptance record.

## Security boundary for v1.0

Portfolio v1.0 remains a production-oriented reference system. R4's objective is
not enterprise perfection: it is a defensible, repeatably checked bounded demo
with explicit residual risk. R5 packages that accepted reality; it does not reopen
R4 hardening or add new security architecture without a release-blocking defect.