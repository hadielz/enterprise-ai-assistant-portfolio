# Portfolio v1.0 Acceptance Criteria

This checklist is the release boundary established in R0. Items may be refined by a later milestone when implementation details become concrete, but new features do not enter v1.0 unless they support one of these criteria.

## R0 — baseline and scope

- [x] Product definition and current-vs-v1.0 capability boundary are documented.
- [x] Current architecture documentation matches the repository.
- [x] Known limitations and release gaps are documented.
- [x] Obsolete JSON-era runtime configuration/code is removed or explicitly supported.
- [x] README and frontend documentation no longer describe obsolete project states.
- [x] Existing backend tests, deterministic evaluations, frontend build, Docker build, and CI remain green.

## R1 — authorization and safe actions

- [x] Minimal employee/support authorization model exists.
- [x] Privileged RAG indexing is authorization-protected.
- [x] Explicit ticket creation and troubleshooting-only requests have a documented and enforced side-effect contract.
- [x] The ambiguous-ticket evaluation is activated only after the behavior is implemented.
- [x] Authorization cannot be bypassed by prompt/model output.

## R2 — real enterprise vertical slice

- [x] Tickets are persisted in PostgreSQL.
- [x] Ticket ownership/status rules are enforced in application code.
- [x] Assistant ticket creation uses the bounded application service.
- [x] A minimal authenticated ticket API/UI path exists.
- [x] One real MCP end-to-end path exposes/consumes the bounded ticket capability.
- [x] Ticket behavior has deterministic tests/evaluations and no duplicate side effects.

## R3 — cloud and observability

Implemented in R3:

- [x] Production secrets are designed for Secret Manager injection rather than source/image/frontend plaintext.
- [x] Cloud SQL PostgreSQL connectivity and an explicit one-off migration Job are defined.
- [x] Cloud SQL + pgvector is implemented as the durable cloud RAG backend; local Chroma remains optional.
- [x] Frontend API endpoint and backend allowed origins are deployment-configurable.
- [x] Private MCP Cloud Run invocation uses backend service identity/Google ID tokens.
- [x] OpenTelemetry + structured logs correlate application request IDs with important AI/provider/tool/RAG/MCP operations.
- [x] Deployment assets use Artifact Registry, bounded service identities and GitHub Workload Identity Federation.

Live acceptance completed:

- [x] Public frontend/backend are running successfully on the chosen Cloud Run environment.
- [x] Existing PostgreSQL state persists across backend revision replacement.
- [x] pgvector index/data persists and a grounded RAG query works across revision replacement.
- [x] Backend can invoke private MCP while an unauthenticated browser/client cannot.
- [x] Explicit ticket request completes backend → MCP → PostgreSQL → UI in cloud with no duplicate row.
- [x] Negated/ambiguous/informational/troubleshooting ticket inputs create zero rows in cloud.
- [x] Sampled distributed trace and correlated logs are visible for the vertical slice.
- [x] Cloud Run/Cloud SQL health, latency/errors and connection behavior are reviewed at the bounded demo scale.

## R4 — hardening

**Status: complete.** The merged R4 implementation passed source/CI verification and Stage-B live acceptance. The acceptance record is maintained in `docs/hardening-r4.md`.

- [x] Input/action limits and rate-limiting baseline are defined and verified.
- [x] Dependency/security checks run repeatably.
- [x] Frontend lint/build and backend quality checks pass.
- [x] Authentication, authorization, conversation isolation, and side-effect abuse cases are covered by negative tests.
- [x] Health/readiness behavior is appropriate for deployment.
- [x] Basic load/failure smoke checks are documented and pass at the declared reference scale.
- [x] Browser/mobile smoke checklist passes.
- [x] Public repository uses synthetic demo organization data only.
- [x] Threat model/security baseline and known limitations are reviewed for release.

## R5 — portfolio release

- [ ] README gives a visitor a correct 30-second understanding of the product.
- [ ] Quick start is verified from a clean checkout.
- [ ] Architecture diagrams are present and match the deployed system.
- [ ] AI-quality/evaluation architecture and CI gate are explained.
- [ ] Security boundaries and known limitations are visible.
- [ ] Screenshots and a short demo are available.
- [ ] Release notes are written.
- [ ] All backend tests pass.
- [ ] Deterministic AI quality gate passes with no required active failures.
- [ ] Frontend production build passes.
- [ ] Docker image build passes.
- [ ] GitHub Actions is green on the release commit.
- [ ] Repository is tagged `v1.0.0`.
- [ ] v1.0 feature development stops after the tag; subsequent work is assigned to a post-release track.