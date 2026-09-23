# R4 Security / Release Hardening - Acceptance Record

## Status

**R4 is complete.** The hardening implementation was independently integrated,
verified through CI, deployed from merged Git, and accepted through the bounded
Stage-B live/browser/load/security review. R5 Portfolio v1.0 followed as the
bounded release milestone.

The release objective was not maximum security technology count. It was to make
the bounded public reference deployment defensible, repeatably checked, negatively
tested, operationally sane, and explicit about residual risk.

## Acceptance record

The authoritative implementation path included the main R4 merge plus three
bounded integration fixes discovered by real verification:

- PR #16 merged the R4 hardening implementation;
- PR #17 aligned the deployment dependency audit with the four reviewed ChromaDB exceptions;
- PR #18 pinned a Cloud SDK version with supported Cloud Run readiness-probe flags;
- PR #19 fixed real iPhone/Safari form-focus zoom by keeping mobile form controls at 16px.

Deployment workflow #10 then succeeded from merged `main` commit `641e7c7`.

Source and CI evidence included a 192-test backend suite, the 41/41 deterministic
AI-quality inventory, frontend lint/build, zero frontend npm vulnerabilities,
the scoped Python dependency audit, production image builds, and no Alembic
migration change.

Live acceptance verified Cloud Run health/readiness probes, frontend security
headers, exact production CORS behavior, controlled 429 + `Retry-After`, the
100-request/concurrency-10 non-destructive load smoke, desktop/responsive/real
mobile browser behavior, provider-backed streaming, Cloud SQL readiness, public
repository data hygiene, and the documented residual-risk decisions.

Recent production logs showed matching streaming start/completion request IDs,
successful OpenAI chat-completion/embedding HTTP 200 responses, no provider-auth
failure pattern, and no `ContextVar`/different-context regression. Superseded
OpenAI/JWT/Gemini secret versions were disabled after the current Secret Manager
bindings and version states were verified. OpenAI v2 was exercised through
successful provider calls and JWT v2 through live authentication. Gemini v3
remained the enabled `latest` fallback version but was not re-exercised because
the available Gemini provider credits were exhausted. Database secret versions
were intentionally left unchanged.

## Acceptance/design matrix

| R4 criterion | R3 evidence / gap | R4 implementation | Accepted evidence |
|---|---|---|---|
| Input/action limits + rate baseline | Auth/ticket domain fields were bounded, but chat had no max and no rate limiter. | Chat max 8,000 chars; process-local sliding-window limits for register/login/chat/RAG indexing/ticket status; cloud explicitly enables the limiter. | Focused/negative tests and CI passed; controlled production login probing crossed the configured username limit and returned 429 with `Retry-After`. |
| Repeatable dependency/security checks | No dedicated Python/npm vulnerability gate. | Pinned release tooling (`pip-audit`, Ruff), `pip-audit`, `npm audit --audit-level=high`, and a public-repository guard in CI/predeploy verification. | Scoped Python audit passed with only the four documented ChromaDB exceptions; npm audit reported zero vulnerabilities; repository guard passed. |
| Frontend + backend quality | Frontend lint existed but normal CI skipped it; no backend lint gate. | CI runs frontend lint/build and a narrow correctness-oriented Ruff gate. | Full backend suite passed 192 tests; frontend lint/build passed; 41/41 deterministic AI evaluations passed; PR CI was green. |
| Negative auth/authz/isolation/action tests | Strong R1/R2 coverage already existed. | Existing suite preserved; R4 adds ownership/limit/CORS/readiness/partial-success regressions. | Focused hardening, auth/conversation/ticket and R1/R2/R3 regression suites passed, followed by the full backend suite. |
| Deployment health/readiness | `/health` was liveness only; no DB-aware readiness. | `/health` stays liveness; `/ready` checks PostgreSQL only; backend/MCP Cloud Run probes distinguish startup/readiness/liveness; frontend probes its process. | Cloud Run probe configuration was inspected on deployed revisions; backend `/health` and `/ready`, MCP probes, frontend `/health`, and Cloud SQL readiness were verified. |
| Basic load/failure smoke | R3 reviewed demo DB connections but had no repeatable bounded load command. | Non-destructive `scripts/load_smoke.py`, defaulting to `/ready`; existing MCP/provider failure regressions retained. | Cloud smoke completed 100 requests at concurrency 10 with zero errors: p50 146.4 ms, p95 187.6 ms, and max 220.1 ms, well below the 3000 ms release threshold. The later PR #19 change was frontend CSS only. |
| Browser/mobile smoke | Responsive CSS existed; no release matrix. | Manual bounded matrix in `docs/browser-mobile-checklist.md`; no new E2E framework. | Chrome, Edge and Firefox desktop checks plus responsive phone/tablet and real iPhone/Safari checks passed. A real iOS focus-zoom defect was fixed in PR #19 and redeployed before acceptance. |
| Synthetic public data | Visible corpus was generic but source/tests and PDF metadata still included personal-style identifiers. | Known identifiers replaced with synthetic personas; demo PDF author metadata sanitized; CI repository guard checks secret shapes + PDF author policy. | Repository guard passed from the bounded backend container; source/docs/assets and sanitized PDF metadata were reviewed. |
| Threat/security/limitations review | R3 documented cloud boundaries and residuals but no consolidated release threat model. | `docs/threat-model.md` records assets, actors, boundaries, abuse cases, mitigations, and accepted residuals. | Security baseline, threat model and known limitations were reconciled against the deployed behavior; residuals remain explicit rather than being presented as solved. |

## Input and action limits

R4 defines intentionally small release limits rather than a distributed abuse
platform.

### Fixed domain limits

- chat message: 8,000 characters;
- username: existing 50-character maximum;
- display name: existing 100-character maximum;
- password input: existing 128-character maximum;
- ticket description: existing 2,000-character normalized maximum;
- conversation ID: existing 100-character maximum.

One chat request can reach at most one bounded tool execution. Ticket creation
therefore inherits the authenticated chat-request rate limit in addition to R1's
safe-action policy and R2's per-action idempotency.

### Process-local rate limits

Cloud deployment enables these defaults:

| Scope | Limit |
|---|---:|
| registration | 20 / 10 min / backend instance (global) |
| login capacity | 60 / min / backend instance (global) |
| login guessing | 10 / 5 min / normalized username / backend instance |
| chat + stream combined | 30 / min / authenticated user / backend instance |
| RAG indexing | 3 / hour / support user / backend instance |
| ticket status mutation | 30 / min / authenticated user / backend instance |

A rejection returns HTTP 429 with `Retry-After`.

**Guarantee boundary:** the limiter is in-process and is not globally consistent
across Cloud Run instances. With the accepted backend maximum of three instances,
aggregate allowance can be up to roughly three times an individual per-instance
limit. It is a capacity/abuse baseline for the bounded portfolio environment, not
DDoS protection. R4 deliberately does not add Redis or an External Application
Load Balancer + Cloud Armor solely to claim distributed rate limiting.

## CORS and browser headers

Backend CORS retains exact configured origins and bearer-token compatibility but
no longer uses method/header wildcards:

```text
methods: GET, POST, PATCH, DELETE
headers: Authorization, Content-Type
credentials: true
origins: explicit ALLOWED_ORIGINS only
```

Production backend HTTP runtime validation rejects an empty/wildcard origin set. This browser-specific validation is not applied to the private MCP process, which has no CORS role. The cloud
workflow initially uses a non-routable placeholder origin for a first deployment,
then updates the backend to the exact deployed frontend URL as before.

Frontend nginx adds:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- `Referrer-Policy: no-referrer`;
- a restrictive camera/microphone/geolocation `Permissions-Policy`;
- `Cache-Control: no-store` for runtime configuration.

A full CSP is **not** introduced in R4. The frontend uses a runtime
cross-origin backend URL, and a correct CSP would need deployment-aware
`connect-src` generation. Adding a broad/incorrect CSP would provide misleading
protection or break streaming. The SPA contains no intentional dangerous HTML
sink; CSP remains a documented residual improvement rather than a v1.0 blocker.

## Liveness and readiness

- `/health`: process liveness only; no external/provider/database calls.
- `/ready`: PostgreSQL `SELECT 1`; returns 503 if the critical application state
  store is unavailable.
- MCP exposes the same liveness/readiness distinction.
- Frontend `/health` remains a process/static-server health check.

LLM provider credit/quota status, optional fallback providers, and external model
latency do not make the whole service unready. Those are request-level degraded
conditions already covered by provider failure handling/telemetry.

Cloud Run startup and readiness probes use `/ready` for backend/MCP so a new
instance is not considered useful before its critical database dependency works.
Liveness uses `/health` so a temporary database outage does not cause a restart
loop.

## Dependency and source quality policy

R4 adds only release-oriented checks:

```text
ruff check backend/app evals tests
pip-audit -r backend/requirements.txt --strict --progress-spinner off --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815
npm run lint
npm audit --audit-level=high
python scripts/security/repository_guard.py
```

Ruff is intentionally configured for correctness-critical syntax/Pyflakes-style
rules only (`E9`, `F63`, `F7`, `F82`) to avoid a late repository-wide formatting
campaign. R4 does not mass-upgrade dependencies unless integration finds a real
vulnerability requiring a bounded remediation.

The existing Python requirements remain a mixture of direct unpinned and bounded
requirements. `pip-audit -r backend/requirements.txt` audits the project runtime
requirement set and its resolved transitive dependencies rather than unrelated
packages preinstalled on the CI runner. A fully hash-locked Python supply chain
is not introduced as a new packaging project in R4.

During R4 verification, `pip-audit` reported four ChromaDB advisories:
`PYSEC-2026-311`, `PYSEC-2026-3813`, `PYSEC-2026-3814`, and
`PYSEC-2026-3815`. The release accepts a temporary scoped exception for
these IDs only. This repository uses Chroma through the embedded
`chromadb.PersistentClient` local backend, does not configure the Chroma
HTTP client/server path, and the production deployment explicitly uses
`VECTOR_STORE_BACKEND=pgvector`.

CI therefore ignores only these four reviewed ChromaDB findings; every
other dependency finding remains release-blocking. The exception must be
removed when a fixed ChromaDB release becomes available, or reconsidered
before any Chroma network/server functionality is introduced.

## Partial-success release decision

R3 made this sequence observable:

```text
durable ticket created
→ final tool-answer LLM provider exhaustion
```

R4 improves the user-facing result **only for the known committed ticket case**.
If all answer providers fail after durable creation, both response paths return a
deterministic message that includes the already-created ticket ID and tells the
user that the ticket is persisted and visible in the ticket workspace. The
exchange is persisted once. The existing `committed_response_failed` telemetry
event remains.

Ordinary all-provider failure semantics remain as characterized by AI Quality:
non-streaming still propagates `LLMProviderError`; streaming still returns its
normal unavailable message. Unexpected programming exceptions after a side
effect still propagate rather than being disguised as a provider outage.

This change is a release-hardening UX decision: it reduces misleading retries
without changing ticket authorization, MCP, provider fallback, or idempotency.

## Database least-privilege decision

R3 intentionally shares one built-in PostgreSQL credential between backend, MCP,
and migration. Cloud SQL grants built-in users `cloudsqlsuperuser` unless custom
roles are assigned, so this is broader than ideal.

R4 **does not retrofit database-principal separation** into the already accepted
cloud environment. A safe split would require a new operational bootstrap for
roles/users, ownership/default privileges across existing and future Alembic
objects, multiple secrets, deployment-workflow changes, and live privilege
migration/rollback. A compromised application runtime already needs CRUD access
to the bounded application tables, and the current code exposes no arbitrary SQL
capability. For this single-project reference deployment, the incremental
privilege reduction does not justify the late migration risk.

The residual risk is explicitly accepted for v1.0 and remains visible in the
threat model/known limitations. A future environment should create separate
migration/runtime database roles from the start rather than repeating the R3
bootstrap choice.

## Bounded load/failure smoke

The release-scale smoke is deliberately safe:

```text
100 GET requests
concurrency 10
path /ready by default
0 accepted errors
p95 <= 3000 ms after one warm-up request
```

This is not a throughput claim. It verifies that the bounded Cloud Run/Cloud SQL
reference deployment remains responsive under a small concurrent burst without
creating tickets, indexing documents, or spending model tokens.

Use existing deterministic tests for provider exhaustion, MCP failure, safe-action
suppression, authorization failures, and the committed-ticket response fallback.
Do not intentionally stop the production database or create destructive failure
conditions merely to satisfy R4.

## Stage A / Stage B completion record

### Stage A - source verification (complete)

Completed verification included:

- compile/config checks;
- focused hardening tests;
- full backend tests in the normal Docker test environment;
- 41-case AI quality gate;
- frontend lint/build;
- dependency/security checks;
- production image builds;
- no Alembic migration change.

### Stage B - authoritative acceptance (complete)

Completed acceptance included:

- inspect Cloud Run probe status and `/health` versus `/ready`;
- verify exact production CORS and security headers;
- intentionally cross one safe rate limit using a controlled account and observe
  429 + `Retry-After` without affecting side-effecting data;
- run the non-destructive bounded load smoke;
- complete the browser/mobile matrix;
- rerun public/synthetic-data review;
- review IAM/database residuals and threat model against the actual deployment;
- reconcile checklist/security/limitations docs in the final R4 acceptance PR.

Both stages are complete. This acceptance record is the final R4 documentation
reconciliation; after the docs-only acceptance PR was green and merged, R5 became
the active release milestone.