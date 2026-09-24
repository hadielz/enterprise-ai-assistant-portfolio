# Portfolio v1.0.0 Release Notes

**Status:** Released. Portfolio v1.0.0 was created only after the final canonical `main` commit passed GitHub Actions. This public repository preserves the accepted release snapshot while allowing post-release documentation maintenance without moving the protected tag.

These notes describe the bounded Portfolio v1.0.0 release built from the accepted R0-R4 implementation and prepared through the R5 release process.

## Summary

The Portfolio v1.0.0 release is a production-oriented reference application for an internal enterprise operations assistant. It demonstrates authenticated conversational AI, enterprise RAG, bounded business actions, multi-provider LLM fallback, LangGraph orchestration, relational persistence, MCP integration, deterministic AI-quality evaluation, a real GCP deployment, observability, and an explicit security/release-hardening baseline.

The release is intentionally a coherent reference system rather than a claim of enterprise-scale SaaS completeness.

## Highlights

### Authenticated application and persistence

- FastAPI backend and React/Vite frontend
- JWT-based authentication with database-backed users
- `employee` / `support` authorization boundary
- user-owned PostgreSQL conversations, messages, summaries, and tickets
- SQLAlchemy/Alembic migration history

### LLM and agent orchestration

- OpenAI, Gemini, Ollama, and deterministic Mock providers
- ordered provider fallback
- versioned prompt contracts
- LangGraph non-streaming workflow
- separately characterized streaming orchestration
- bounded calculator/RAG/ticket tool selection

### Enterprise RAG

- TXT/PDF document loading
- OpenAI embedding reference path
- ChromaDB local backend
- PostgreSQL/pgvector durable cloud backend
- support-only indexing boundary
- deterministic grounding/source contracts in AI evaluation

### Safe enterprise action and MCP

- real PostgreSQL-backed IT-ticket entity
- deterministic safe-action policy separating explicit creation from troubleshooting/informational requests
- ownership and bounded status-transition rules
- actual MCP Streamable-HTTP ticket capability
- private Cloud Run MCP service invoked by the backend with Google identity tokens
- deterministic confirmation when a durable ticket exists but final provider wording fails

### AI quality and CI

- 41 active required deterministic AI-quality cases across behavior, RAG, routing, and tool datasets
- accepted R4 baseline: 41/41 passed
- accepted R4 backend baseline: 192 tests passed
- GitHub Actions backend/frontend/Docker jobs
- Ruff correctness checks
- Python dependency audit with four explicit reviewed ChromaDB exceptions
- frontend lint and npm audit
- synthetic public-repository guard

R5 release-candidate verification re-ran the complete gate set on candidate `f084f44cae9032198962ef9f9d9160add8e1584f`: 192/192 backend tests, 41/41 deterministic AI-quality cases with average score 1.0000, frontend install/lint/audit/build, both production Docker builds, Ruff, Python dependency audit with the four reviewed ChromaDB advisory exceptions, and the public repository guard. GitHub Actions then passed on PR run #48 and post-merge `main` run #49 at `5a795984f9be4aad17b924b697dea01925f584af`. The final canonical release commit subsequently passed GitHub Actions before the `v1.0.0` tag was created.

### Cloud and observability

- public Cloud Run frontend/backend
- private IAM-protected Cloud Run MCP service
- Cloud SQL PostgreSQL with pgvector
- explicit one-off Cloud Run Alembic migration Job
- Secret Manager runtime injection
- Artifact Registry images
- Workload Identity Federation for GitHub deployment
- OpenTelemetry trace export and structured Cloud Logging-compatible logs
- request/provider/tool/RAG/MCP/ticket correlation

### Release hardening

- explicit input/action bounds
- process-local route-specific rate limiting with `429` / `Retry-After`
- explicit production CORS validation
- browser-facing nginx security headers
- separate liveness/readiness behavior
- bounded non-destructive load smoke
- Chrome/Edge/Firefox + responsive + real iPhone/Safari acceptance
- threat-model, security-baseline, public-data, and residual-risk review

## Accepted R4 evidence entering R5

The R5 release starts from the accepted R4 baseline rather than reinterpreting source intent:

- 192 backend tests passed;
- deterministic AI quality passed 41/41 active required cases;
- frontend lint/build and npm audit passed;
- both production Docker images built successfully;
- Cloud Run health/readiness, CORS, headers, rate limiting, and bounded load smoke passed;
- the cloud `/ready` load smoke completed 100 requests at concurrency 10 with zero errors (p50 146.4 ms, p95 187.6 ms, max 220.1 ms);
- production OpenAI chat/embedding requests and streaming start/completion correlation were observed without the prior streaming `ContextVar` regression;
- the private MCP/ticket vertical slice and persistent Cloud SQL/pgvector state were accepted;
- browser/mobile acceptance passed after the iOS form-focus zoom correction was merged, deployed, and retested;
- the repository public-data guard and final R4 threat/security/limitations reviews passed.

These are historical R4 acceptance results. R5 deliberately re-runs the release gates before tagging rather than treating R4 evidence as sufficient.

## Known limitations

The release keeps several limitations explicit rather than adding last-minute architecture solely for breadth. Important examples include:

- process-local rather than distributed rate limiting;
- access-token-only browser sessions stored in `sessionStorage`;
- no document-level RAG authorization model for the uniform synthetic demo corpus;
- shared PostgreSQL application principal across bounded runtime components;
- no full CSP in the R4 baseline;
- reviewed unresolved advisories in the local embedded Chroma dependency;
- direct OTLP export without an OpenTelemetry Collector;
- bounded ticket idempotency rather than general semantic deduplication;
- no multi-region / high-availability / very-large-scale claim.

See [`known-limitations.md`](known-limitations.md), [`security-baseline.md`](security-baseline.md), and [`threat-model.md`](threat-model.md) for the complete release boundary.

## Release boundary and finalization

R5 clean-checkout acceptance, architecture/media preparation, release-metadata alignment, local final gates, and candidate/post-merge CI verification are complete.

The release-notes finalization was merged to canonical `main`, GitHub Actions passed on the final canonical release commit, and `v1.0.0` was created only after those gates passed.

Release packaging then recorded the GitHub release, final archive SHA256/file count, and the publication decision: the canonical engineering repository remains private, while this repository publishes the clean accepted Portfolio v1.0.0 snapshot.

Feature development for v1.0 is closed. New functionality belongs to post-release tracks; documentation and portfolio-maintenance changes may continue without moving the protected `v1.0.0` tag.
