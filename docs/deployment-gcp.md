# Google Cloud Deployment Runbook

> **Repository/deployment scope.** This runbook records the accepted R3/R4 deployment path. The canonical engineering repository remains the deployment authority. In this public portfolio repository, `.github/workflows/deploy-gcp.yml` is retained as release evidence but execution is intentionally disabled; this public snapshot is not the deployment authority.

## Architecture

```text
Internet
   ↓
Cloud Run: frontend (public)
   ↓ HTTPS
Cloud Run: backend (public transport; application JWT protects user APIs)
   ├── Cloud SQL PostgreSQL
   │     ├── users/conversations/messages/summaries/tickets
   │     └── pgvector document_chunks
   ├── Secret Manager injected runtime secrets
   ├── external LLM/embedding providers
   └── Google identity token
          ↓
      Cloud Run: MCP (private IAM-protected)
          ↓
      Cloud SQL PostgreSQL

Cloud Run Job: migration
   ↓ explicit Alembic upgrade head
Cloud SQL

backend + MCP
   ↓ OpenTelemetry OTLP traces
Google Telemetry / Cloud Trace
   ↓ stdout JSON logs
Cloud Logging
```

Docker Compose remains the local-development orchestrator. It is not used as the production orchestrator.

## R4 hardening in the accepted deployment baseline

R3 established the Cloud Run/Cloud SQL/MCP topology. R4 preserved that topology,
added bounded release-hardening controls, and was deployed from merged Git before
the Stage-B acceptance checks in `docs/hardening-r4.md` were recorded.

The deployment workflow now preserves this health contract:

```text
backend/MCP /health  = process liveness only
backend/MCP /ready   = PostgreSQL-aware readiness
frontend /health     = nginx/container liveness/readiness
```

Cloud Run startup and readiness probes for backend/MCP use `/ready`; liveness uses
`/health`. External LLM-provider quota/billing state is deliberately not a
readiness dependency.

The backend R4 cloud baseline also enables the process-local limiter with bounded
route-specific settings. This limiter is per Cloud Run instance, not a globally
consistent distributed quota. Existing Cloud Run maximum-instance limits provide
an aggregate bound; Redis or another distributed limiter is not introduced for
v1.0.

Production `ALLOWED_ORIGINS` must contain explicit HTTPS origins only. The
deployment continues to bootstrap the backend with the non-sensitive placeholder
`https://invalid.example`, deploys the frontend, then updates the backend to the
exact deployed frontend origin. Wildcard, credential-bearing, path-bearing, query,
fragment, and non-HTTPS production origins are rejected by runtime validation.

## R3 infrastructure choice

R3 uses version-controlled PowerShell/gcloud provisioning plus a manual GitHub Actions deployment workflow instead of introducing Terraform. The current cloud footprint is small enough that this is reviewable and bounded, while still making every resource/identity/deployment setting explicit. If later releases grow into several environments or significantly more resources, migrating this provisioning layer to Terraform becomes reasonable.

## Prerequisites

Before running provisioning:

- a Google Cloud project with billing enabled;
- current `gcloud` CLI installed and authenticated;
- permission to enable APIs and create IAM/Cloud Run/Cloud SQL/Secret Manager/Artifact Registry resources;
- a GitHub repository whose exact `owner/repository` name will be bound to Workload Identity Federation;
- a conscious choice of Cloud SQL tier based on current regional availability/pricing.

Do not copy a machine type from an old tutorial. Cloud SQL is the primary ongoing cost driver in this reference deployment.

## Checkpoint 1 — choose variables

Example PowerShell variables:

```powershell
$PROJECT_ID = "your-gcp-project"
$REGION = "europe-west1"
$ENV_PREFIX = "enterprise-ai-demo"
$GITHUB_REPOSITORY = "owner/repository"
$CLOUD_SQL_TIER = "<choose-after-checking-current-pricing>"
```

Set the active project and confirm billing/project identity before creating resources:

```powershell
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud config get-value project
gcloud billing projects describe $PROJECT_ID
```

## Checkpoint 2 — provision bounded cloud resources

Run:

```powershell
.\scripts\gcp\provision-r3.ps1 `
  -ProjectId $PROJECT_ID `
  -Region $REGION `
  -Prefix $ENV_PREFIX `
  -CloudSqlTier $CLOUD_SQL_TIER `
  -GitHubRepository $GITHUB_REPOSITORY
```

The script requires typing `CREATE-R3` because it creates billable resources, especially Cloud SQL.

It creates/enables:

- required Google APIs;
- Artifact Registry Docker repository;
- Cloud SQL PostgreSQL 17 instance/database/user;
- Secret Manager resources for database URL, JWT, OpenAI and Gemini keys;
- frontend, backend, MCP, migration and GitHub-deployment service accounts;
- bounded IAM grants;
- GitHub Workload Identity Federation pool/provider restricted to the configured GitHub repository and the main branch.

It prints the GitHub repository variables needed by `.github/workflows/deploy-gcp.yml`.

## Checkpoint 3 — add provider secret values

Provisioning intentionally creates provider secret resources without committing or printing your provider keys.

Add only providers actually used by the production configuration.

Provider keys must be written to a temporary UTF-8 file with no trailing newline and uploaded to the corresponding Secret Manager secret using:

```text
gcloud secrets versions add SECRET_NAME --data-file=<path>
```

Do not pipe provider keys through standard input for this step. Using an explicit temporary no-newline UTF-8 file avoids ambiguous pipeline newline behavior.

Use a separate temporary file for each provider key, upload it to the corresponding secret, and securely delete the temporary file afterward.

Do not place provider keys in GitHub variables, frontend configuration, Dockerfiles or committed `.env` files.

## Checkpoint 4 — GitHub repository variables (canonical deployment repository)

In the canonical engineering repository, configure the values printed by `provision-r3.ps1` as GitHub Actions **repository/environment variables**, including:

```text
GCP_PROJECT_ID
GCP_REGION
GCP_ENV_PREFIX
GCP_ARTIFACT_REPOSITORY
GCP_WIF_PROVIDER
GCP_DEPLOY_SERVICE_ACCOUNT
CLOUD_SQL_CONNECTION_NAME
FRONTEND_SERVICE_ACCOUNT
BACKEND_SERVICE_ACCOUNT
MCP_SERVICE_ACCOUNT
MIGRATION_SERVICE_ACCOUNT
DATABASE_URL_SECRET
JWT_SECRET
OPENAI_API_KEY_SECRET
GEMINI_API_KEY_SECRET
```

Optional bounded configuration variables:

```text
LLM_PROVIDER=gemini
LLM_FALLBACK_PROVIDERS=openai
GEMINI_MODEL=gemini-3.6-flash
OPENAI_MODEL=gpt-4o-mini
OTEL_SAMPLE_RATIO=0.1
BACKEND_MAX_INSTANCES=3
BACKEND_CONCURRENCY=20
MCP_MAX_INSTANCES=2
MCP_CONCURRENCY=10
BACKEND_DATABASE_POOL_SIZE=3
BACKEND_DATABASE_MAX_OVERFLOW=1
MCP_DATABASE_POOL_SIZE=2
MCP_DATABASE_MAX_OVERFLOW=1
RATE_LIMIT_REGISTER_LIMIT=20
RATE_LIMIT_REGISTER_WINDOW_SECONDS=600
RATE_LIMIT_LOGIN_GLOBAL_LIMIT=60
RATE_LIMIT_LOGIN_GLOBAL_WINDOW_SECONDS=60
RATE_LIMIT_LOGIN_USER_LIMIT=10
RATE_LIMIT_LOGIN_USER_WINDOW_SECONDS=300
RATE_LIMIT_CHAT_LIMIT=30
RATE_LIMIT_CHAT_WINDOW_SECONDS=60
RATE_LIMIT_RAG_INDEX_LIMIT=3
RATE_LIMIT_RAG_INDEX_WINDOW_SECONDS=3600
RATE_LIMIT_TICKET_STATUS_LIMIT=30
RATE_LIMIT_TICKET_STATUS_WINDOW_SECONDS=60
```

Provider order is intentionally environment-configurable. When repository variables are absent, the deployment workflow currently defaults to Gemini as primary and OpenAI as fallback.

For the accepted R4 live environment, repository variables were set to:

```text
LLM_PROVIDER=openai
LLM_FALLBACK_PROVIDERS=gemini
```

The accepted demo environment used OpenAI as the operational primary provider while preserving Gemini as the configured fallback. Available Gemini provider credits were exhausted during R4 acceptance, so live provider verification used OpenAI. This is an environment-level configuration choice, not a change to the provider abstraction.

Ollama remains supported for local/self-hosted development through the existing provider interface. The GCP reference topology does not deploy an Ollama model-serving runtime.

No downloaded service-account JSON key is required. The deployment workflow authenticates through GitHub OIDC/Google Workload Identity Federation.

## Checkpoint 5 — manually deploy after CI-quality verification

In the canonical engineering repository, run the GitHub Actions workflow:

```text
Deploy Portfolio v1 to GCP
```

through `workflow_dispatch`. In this public portfolio repository, that workflow is intentionally disabled; do not use the public snapshot as deployment authority.

The workflow first re-runs the backend tests, Ruff correctness check, Python dependency audit, public-repository guard, deterministic AI-quality gate, and frontend lint/audit/build. Only then does it authenticate to Google Cloud, push images and deploy resources.

Deployment order is deliberate:

```text
build/push images
→ private MCP service
→ grant backend SA MCP invoker role
→ migration Cloud Run Job
→ execute Alembic migration and wait
→ public backend
→ public frontend
→ set backend allowed origin to exact frontend URL
```

The web services never run Alembic automatically on instance startup.

## Cloud SQL and database URL

Cloud Run services/jobs attach the Cloud SQL instance. The generated SQLAlchemy URL uses the Cloud SQL Unix socket:

```text
postgresql+psycopg://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE
```

The URL is stored in Secret Manager and injected at runtime.

The migration chain creates the `vector` extension and the pgvector-backed `document_chunks` table. Existing R2 tables/migrations remain untouched.

## Vector persistence

Cloud deployment sets:

```text
VECTOR_STORE_BACKEND=pgvector
EMBEDDING_DIMENSIONS=1536
```

Local development defaults to Chroma. Cloud RAG vectors live in Cloud SQL and therefore do not depend on a Cloud Run instance's ephemeral filesystem.

After deployment, authenticate as a support user and run the existing privileged:

```text
POST /api/rag/index
```

Then confirm `document_chunks` is populated and repeat a grounded query after a backend revision/restart to demonstrate durable vector persistence.

## MCP service authentication

The MCP Cloud Run service is deployed with unauthenticated invocation disabled. The backend runtime service account receives `roles/run.invoker` on that service.

Cloud mode configures:

```text
MCP_AUTH_MODE=google_identity
MCP_AUDIENCE=<MCP Cloud Run service URL>
```

For every MCP call, trusted backend code obtains a Google-signed ID token through Application Default Credentials and sends it in `X-Serverless-Authorization`. The MCP protocol still uses Streamable HTTP; no direct Python server import replaces the protocol boundary.

The browser receives neither this token nor the MCP service credential.

The MCP SDK's DNS-rebinding Host validation remains enabled for local development with an explicit localhost/Compose allowlist. In production, the MCP application delegates that Host boundary to Cloud Run's managed reverse proxy and IAM invocation policy. This avoids rejecting valid Cloud Run service hostnames with HTTP 421 while keeping the MCP service IAM-private.

## Observability verification

Cloud mode enables direct OTLP trace export and JSON stdout logging:

```text
OTEL_ENABLED=true
OTEL_EXPORTER=gcp_otlp
OTEL_SAMPLE_RATIO=0.1
```

Perform an authenticated chat request and preserve the application `request_id` from logs. In Cloud Logging, filter by that request ID and open the correlated trace. For an explicit ticket request, verify the trace includes backend work followed by MCP client/server spans and ticket persistence.

See `docs/observability.md` for safe fields and diagnostic events.

## Cloud acceptance smoke test

After deployment, verify in order:

1. Frontend URL is HTTPS-reachable.
2. Register/login succeeds.
3. Create/reopen a conversation; redeploy/restart backend and confirm persistence.
4. Promote a controlled demo user to `support` administratively in the database and verify `/api/rag/index` remains support-only.
5. Index the demo documents and verify a policy query returns grounded content after a new Cloud Run revision.
6. Make an explicit ticket request and verify exactly one PostgreSQL ticket appears and the React ticket workspace refreshes.
7. Send negated, informational, troubleshooting and ambiguous ticket messages and verify ticket count does not increase.
8. Verify an unauthenticated direct request to the MCP service is denied by Cloud Run IAM.
9. Verify the backend can invoke MCP using its runtime identity.
10. Inspect a sampled trace and correlated logs for the ticket request.
11. Exercise a provider fallback/failure scenario in a controlled demo and verify provider/error metadata is diagnosable.
12. Inspect Cloud SQL connections/health and Cloud Run instance/latency/error metrics.

The R3 functional cloud acceptance checks were executed against the target GCP
project and passed. R4 later revalidated the relevant deployed paths and completed
the additional Stage-B hardening acceptance below. Future deployments should
rerun the appropriate checks because milestone acceptance does not guarantee the
health or configuration of another environment.

### R4 Stage-B hardening acceptance (completed)

The merged R4 deployment completed these non-destructive hardening checks:

```text
GET backend /health -> 200 even when dependency readiness is being evaluated
GET backend /ready  -> 200 with Cloud SQL reachable
GET MCP /ready via authenticated backend path -> healthy
CORS preflight from deployed frontend -> permitted for required methods/headers
untrusted Origin / unsupported method -> no usable CORS grant
frontend responses -> expected R4 security headers
controlled rate-limit test -> 429 + Retry-After without creating tickets
python scripts/load_smoke.py --base-url <backend-url> -> bounded /ready smoke passes
browser/mobile matrix in docs/browser-mobile-checklist.md -> recorded pass/finding
Cloud Logging/Trace -> R3 request/context propagation still intact
```

Do not load-test chat, RAG indexing, or ticket creation in the shared demo
environment. The R4 load smoke intentionally targets `/ready` so it cannot create
LLM spend or business side effects.

If a cloud-only hardening defect is found, use a small fix branch -> tests -> PR ->
CI -> merge -> redeploy. Do not patch the live service without encoding the fix in
Git.

## Cost and scaling baseline

Portfolio defaults intentionally retain `min instances = 0` and bound maximum instances so the services can scale to zero while limiting Cloud SQL connection demand.

The deployed SQLAlchemy connection-pool defaults are:

- backend: `3 + 1 overflow`;
- MCP: `2 + 1 overflow`.

The backend and MCP services use instance-based Cloud Run CPU because the OpenTelemetry `BatchSpanProcessor` performs background trace export. Instance-based CPU allows that background work to continue outside active request processing. Both services still retain `min instances = 0`, so this does not keep an instance permanently running when there is no traffic.

The defaults are a reference baseline, not universal production sizing. Instance-based CPU can increase Cloud Run cost while an instance is allocated compared with request-based CPU, so this is an explicit observability-versus-cost trade-off. Cloud Run can also briefly exceed configured maximum instances under some conditions, so Cloud SQL connections must still be monitored.

Primary likely cost drivers:

- Cloud SQL instance/storage/backups;
- model/embedding API calls;
- Cloud Run CPU/memory/request execution;
- trace/log ingestion above free allowances;
- Artifact Registry storage.

Cloud SQL remains an ongoing cost even when Cloud Run scales to zero.

## Teardown

The bounded teardown script deletes the largest R3 runtime/cost resources:

```powershell
.\scripts\gcp\teardown-r3.ps1 `
  -ProjectId $PROJECT_ID `
  -Region $REGION `
  -Prefix $ENV_PREFIX
```

It requires typing `DELETE-R3` and deletes Cloud Run services/job, Cloud SQL and the Artifact Registry repository.

It deliberately leaves secrets, service accounts and WIF configuration for explicit review. After confirming they are no longer needed, remove them separately rather than relying on a broad destructive script.

For maximum certainty in a disposable dedicated project, deleting the entire Google Cloud project removes all project resources. Do this only when you intentionally created the project for the demo and no unrelated resources live there.