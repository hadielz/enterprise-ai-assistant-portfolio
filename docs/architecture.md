# Current Architecture

## Status

R0-R4 are merged and complete. This document describes the accepted application
and cloud architecture that R5 packages for Portfolio v1.0. R5 does not change
these boundaries unless a genuine release-blocking defect is found. The R4
hardening acceptance record is maintained in `docs/hardening-r4.md`.

## Local runtime

```text
React/Vite
    ↓ HTTP
FastAPI backend
    ↓ JWT-authenticated user
Chat service
├── non-streaming -> compiled LangGraph
└── streaming     -> service orchestration
    ↓
Tool selection / RAG / LLM
    ├── PostgreSQL application state
    ├── Chroma or pgvector retrieval
    └── actual MCP Streamable HTTP
            ↓
        MCP service
            ↓
        ticket service/repository
            ↓
        PostgreSQL
```

Docker Compose remains the local orchestrator. PostgreSQL and test PostgreSQL
use the accepted pgvector-enabled PostgreSQL 17 image, while
`VECTOR_STORE_BACKEND=chroma` remains the local default. R4 does not alter the
R3 vector or MCP architecture.

## Cloud topology

```text
Internet
  ↓
Cloud Run frontend (public HTTPS)
  ↓
Cloud Run backend (public HTTPS transport)
  ├── application JWT remains end-user authorization authority
  ├── Cloud SQL PostgreSQL
  │    ├── users / conversations / messages / summaries / tickets
  │    └── pgvector document_chunks
  ├── Secret Manager injected secrets
  ├── external LLM / embedding providers
  └── Google-signed identity token
          ↓
     Cloud Run MCP service (IAM-private)
          ↓
     Cloud SQL PostgreSQL

Cloud Run migration Job
  ↓
Alembic upgrade head

backend + MCP
  ├── OpenTelemetry OTLP traces -> Google Telemetry / Cloud Trace
  └── structured JSON stdout    -> Cloud Logging
```

Artifact Registry stores backend and frontend images. R4 keeps the R3 bounded
instance/concurrency/database-pool settings and does not introduce a new cloud
platform or distributed cache.

## API, authentication and authorization

Public application routes include:

- `GET /`
- `GET /health`
- `GET /ready`
- `POST /api/auth/register`
- `POST /api/auth/login`

Authenticated routes include chat, conversation history, `/api/auth/me`, and
the ticket workspace APIs. `POST /api/rag/index` remains restricted to the
database-backed `support` role.

Cloud Run permits unauthenticated transport to the backend because
registration/login are public and application JWT remains the end-user auth
boundary. This does **not** make authenticated APIs public in application
semantics. The MCP Cloud Run service remains IAM-private and only the backend
runtime identity receives `roles/run.invoker`.

R4 adds bounded endpoint hardening without changing those authorities:

```text
input limits
  ├── registration/auth domain bounds (existing + login hardening)
  ├── chat message max = 8,000 characters
  └── ticket description max = 2,000 characters (existing)

process-local request limiting
  ├── registration
  ├── login (global + normalized username scope)
  ├── non-streaming + streaming chat (shared per-user scope)
  ├── support RAG indexing
  └── support ticket-status mutation
```

The rate limiter is intentionally per backend process/Cloud Run instance. It is
an abuse/cost baseline for the bounded demo, not a globally consistent quota or
DDoS service. Cloud Run max-instance bounds remain part of the aggregate safety
story. See `docs/hardening-r4.md` and `docs/threat-model.md`.

## CORS and browser boundary

CORS remains environment-configurable. Local development may use the explicit
localhost origins from `.env.example`. Production runtime validation requires
explicit HTTPS origins and rejects wildcard, credential-bearing, path/query or
fragment origins.

Browser CORS is restricted to the methods/headers used by the application:

```text
methods: GET, POST, PATCH, DELETE
headers: Authorization, Content-Type
credentials: enabled
origins: explicit ALLOWED_ORIGINS only
```

The frontend nginx container adds a small browser-header baseline
(`nosniff`, frame denial, referrer policy, bounded permissions policy) and makes
`runtime-config.js` non-cacheable. R4 deliberately does not add a rushed CSP;
the runtime cross-origin backend URL would require deployment-aware `connect-src`
configuration and browser acceptance.

## Liveness and readiness

R4 separates process liveness from dependency readiness:

```text
backend /health -> process can serve HTTP; no dependency probe
backend /ready  -> PostgreSQL SELECT 1; 503 while DB is unavailable

MCP /health     -> MCP process can serve
MCP /ready      -> PostgreSQL SELECT 1; 503 while DB is unavailable

frontend /health -> nginx/static-container health
```

Cloud Run startup/readiness probes use `/ready` for backend and MCP; liveness
uses `/health`. Optional/fallback model-provider quota or billing status does not
make the entire service unready. This avoids restart loops during a temporary DB
outage while preventing a new revision from receiving traffic before its
critical application-state dependency is usable.

## Relational persistence

PostgreSQL/Cloud SQL stores:

```text
users
  ↓
conversations
  ↓
messages

users
  ↓
tickets

document_chunks   <- pgvector cloud RAG
```

Ticket `action_id` remains unique and preserves R2 per-generation idempotency.
R4 introduces **no database migration or schema change**.

The accepted R3 deployment still uses one built-in PostgreSQL principal for
backend, MCP and migration while those components use distinct Google service
accounts. R4 reviews this explicitly and accepts it as a bounded v1.0 residual
risk rather than performing a late live ownership/credential migration. See
`docs/threat-model.md`.

## Vector-store decision

The application-facing RAG API remains `index_documents()` /
`search_similar_chunks()` with exactly the existing R3 deployment choice:

```text
VECTOR_STORE_BACKEND=chroma
VECTOR_STORE_BACKEND=pgvector
```

Chroma remains the low-friction local default; pgvector remains the durable
cloud-reference backend. Retrieval thresholds, embedding dimensions, source-ID
semantics and prompt contracts are unchanged in R4.

## MCP vertical slice and safe actions

The trusted flow remains:

```text
LLM proposes ticket_creator
  ↓
R1 deterministic safe-action policy
  ↓
ToolExecutionContext
  ├── authenticated user_id
  └── request_id/action_id
  ↓
actual MCP client
  ↓ Streamable HTTP
MCP server
  ↓
ticket service/repository
  ↓
PostgreSQL
```

Local Compose keeps MCP transport-security DNS-rebinding protection with its
explicit local/Compose allowlist. Production keeps the accepted R3 Cloud Run
reverse-proxy/IAM boundary that fixed the live HTTP 421 failure. R4 does not
regress or bypass the actual MCP protocol path.

## LLM and tool-selection behavior

Provider abstraction/fallback semantics remain unchanged. Tool selection still
distinguishes selected/no-tool/parse/schema/unsupported outcomes. The R2 narrow
normalization contract remains:

```text
bare valid JSON                     -> accepted
one complete ```json ... ``` fence -> unwrapped + accepted
one complete ``` ... ``` fence     -> unwrapped + accepted
prose wrapped around JSON           -> parse_error
malformed JSON                      -> parse_error
schema-invalid JSON                 -> invalid_schema
```

Raw provider output remains available internally to the protocol result, while
production telemetry records bounded normalization/status metadata rather than
raw model output.

## Partial-success ticket response hardening

The durable sequence remains unchanged: the ticket is committed before the
final `tool.answer.v1` wording call. R4 changes only the user-facing provider
exhaustion behavior after a **confirmed committed ticket**.

If all answer providers fail after the side effect is known to be durable,
non-streaming and streaming return a deterministic response that identifies the
persisted ticket and tells the user it remains visible in the ticket workspace.
The existing `committed_response_failed` telemetry remains. Unexpected
programming exceptions are still propagated rather than disguised as provider
failure.

For a streaming provider that emitted partial text before failing, the
confirmation is appended to the already-emitted text and the persisted assistant
message matches what the browser actually received.

Ordinary all-provider failure without a committed side effect retains the
Phase-6 characterized behavior.

## Observability

The R3 `app.observability` layer remains the telemetry architecture. Automatic
OpenTelemetry instrumentation covers FastAPI, SQLAlchemy, `requests`, and
`httpx`; manual spans remain limited to high-value AI/business boundaries.

The application `request_id` remains explicit and is correlated with trace/span
IDs. W3C context continues backend -> MCP over the real protocol connection.
R4 rate-limit/readiness/header work is route/config based and does not replace or
re-enter the streaming context managers that were fixed during R3 acceptance.

Structured logs still exclude user messages, document context, provider raw
output, JWTs, secrets and credentials by policy. See `docs/observability.md`.

## Frontend deployment

The React app is built once and served by nginx in Cloud Run. Runtime
`runtime-config.js` still allows `API_BASE_URL` to change without rebuilding the
frontend image. Frontend role visibility remains UX-only; authorization stays
server-side.

## CI and deployment

`.github/workflows/ci.yml` remains the normal CI workflow and now adds bounded R4
release checks:

```text
Ruff correctness-focused backend quality check
pip-audit runtime dependency audit
public repository secret/demo-data guard
frontend ESLint
npm audit --audit-level=high
```

The manually triggered GCP deployment workflow re-runs the same quality/security
checks before cloud changes. It also configures backend/MCP startup, liveness and
readiness probes and enables the R4 process-local rate limiter in production.

CI and deployment remain conceptually separate.

## Architecture differences deliberately preserved

- non-streaming uses LangGraph; streaming uses service orchestration;
- valid no-tool + empty retrieval can expose different internal route labels
  while both have effective chat semantics;
- ordinary provider exhaustion still differs between streaming and
  non-streaming as characterized in AI Quality;
- ticket idempotency is per trusted action ID, not semantic deduplication;
- backend, MCP and migration still share the R3 PostgreSQL application principal;
- the SPA access token remains in `sessionStorage`.

Those are explicit residuals or previously characterized contracts, not hidden
R4 regressions. R5 may package the accepted reality but must not silently expand
product scope.
