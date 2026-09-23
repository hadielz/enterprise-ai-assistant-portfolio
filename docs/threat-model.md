# Portfolio v1.0 Threat Model - R4 Accepted

## Scope and security objective

This threat model covers the bounded public reference deployment: Cloud Run
frontend/backend, private MCP service, Cloud SQL/pgvector, Secret Manager,
external model providers, GitHub deployment federation, and the synthetic demo
corpus. It is not a compliance certification or a claim of internet-scale
resilience.

The primary objective is to prevent ordinary users, model output, public clients,
or compromised request data from crossing authorization/side-effect boundaries;
keep credentials and private data out of public source/telemetry; and keep common
failure/abuse modes bounded and diagnosable.

## Assets

- password hashes and JWT signing secret;
- authenticated conversation/message/summary data;
- employee/support role state;
- ticket ownership/status/action IDs;
- internal demo RAG documents and embeddings;
- provider API keys;
- Cloud SQL credentials/data;
- backend → MCP identity tokens;
- GitHub → GCP deployment federation;
- trace/log metadata;
- availability/cost budget of the public demo.

## Actors

- unauthenticated internet client;
- authenticated employee;
- authenticated support operator;
- malicious/prompt-injecting user;
- probabilistic or malformed LLM output;
- compromised browser JavaScript/XSS context;
- compromised backend or MCP runtime;
- repository/deployment contributor;
- external provider or infrastructure failure.

## Trust boundaries

```text
browser / internet
      ↓ public HTTPS
Cloud Run frontend
      ↓ public HTTPS
Cloud Run backend
      ├── JWT → user identity/role in PostgreSQL
      ├── provider credentials → external LLM/embedding APIs
      ├── Cloud SQL credential → application persistence
      └── Google identity token
             ↓ Cloud Run IAM
         private MCP
             ↓ bounded ticket service
          Cloud SQL

GitHub Actions
      ↓ OIDC / WIF
bounded deploy service account
      ↓
Cloud Run / Artifact Registry / migration orchestration
```

## High-value abuse cases and controls

| Threat / misuse | Current mitigation | R4 status / residual |
|---|---|---|
| Registration self-elevates to support | Role is database-authoritative; registration always employee. | Covered by negative tests. |
| Employee invokes support-only RAG index | Python authorization dependency returns 403. | Preserved; RAG index also rate-limited. |
| Cross-user conversation/ticket enumeration | Repository queries scope by authenticated user; cross-owner reads return 404. | R4 adds cross-owner conversation-delete regression. |
| Prompt says "pretend I am support" | Model text never sets authenticated role. | Accepted control. |
| LLM selects ticket for ambiguous/negated/troubleshooting request | Deterministic R1 safe-action policy runs before side effect. | Existing negative suite preserved. |
| LLM supplies another requester/role | Trusted execution context supplies user ID/action ID; MCP result is context-validated. | R2 control preserved. |
| Duplicate execution of one ticket action | Unique trusted `action_id`. | Per-action only; semantic duplicate requests remain possible. |
| MCP is called by browser/internet | Cloud Run IAM-private service; backend obtains Google ID token. | Preserve R3 transport-security correction. |
| Credential/token appears in telemetry | Structured-log sensitive-field filtering and bounded span attributes. | Repository guard supplements source review; no DLP claim. |
| Brute-force/burst/cost abuse | R4 process-local rate limits + Cloud Run max instances + existing bounded actions. | Not globally distributed/DDoS-grade. |
| Oversized chat causes excessive provider/context cost | R4 caps chat at 8,000 characters. | Token count is provider-dependent; character cap is the deterministic contract. |
| DB outage gets confused with dead process | Separate `/health` and DB-aware `/ready`. | Cloud Run probes use both semantics. |
| Durable ticket is created but final wording fails | R3 telemetry identifies committed-response failure. | R4 returns deterministic persisted-ticket confirmation for provider exhaustion. |
| Cross-site browser request abuses API | Explicit CORS origins/methods/headers; bearer auth remains required. | CORS is browser policy, not authentication. |
| UI is framed/clickjacked | `X-Frame-Options: DENY`. | Full CSP deferred. |
| Known vulnerable dependency reaches release | `pip-audit` + `npm audit` in CI/predeploy. | Findings require reviewed remediation/exception; scans depend on vulnerability services. |
| Secret accidentally committed | Secret Manager/WIF architecture; repository guard catches common key/private-key shapes. | Not a full DLP/secret-history scanner. |
| Compromised app DB credential abuses Cloud SQL privileges | R3 built-in DB user is broader than least privilege. | Explicit v1.0 residual; see DB decision below. |

## Residual-risk decisions for v1.0

### Access-token-only JWT and sessionStorage

The SPA retains the access token in `sessionStorage`; successful same-origin XSS
could read it. R4 does not invent a refresh/revocation/session platform. The
frontend has no intentional dangerous HTML rendering sink, browser headers are
hardened, tokens expire, and server requests re-resolve active users. This remains
an explicit residual risk rather than a hidden "secure session" claim.

### No full Content Security Policy

The production frontend uses runtime-configured cross-origin backend URLs. R4
adds low-risk browser headers but does not generate a deployment-specific CSP in
this milestone. A broad `connect-src` would be weak; a narrow dynamic one would
add deployment/template complexity and needs independent browser acceptance.

### Shared PostgreSQL database principal

Backend, MCP, and migration keep distinct Google service accounts but share the
R3 built-in PostgreSQL principal. Cloud SQL built-in users receive
`cloudsqlsuperuser` by default. Retrofitting role/object ownership and multiple
secrets into the live R3 environment is not required to satisfy the bounded
release contract and carries nontrivial migration risk. This is accepted for the
single demo database; future environments should prefer separate migration and
runtime DB roles from provisioning time.

### Process-local rate limiting

The rate limiter is per backend process/instance. It provides bounded capacity
and simple-abuse protection, not a global quota or DDoS service. Cloud Armor would
require an external load balancer/serverless NEG path and direct Cloud Run ingress
restrictions to avoid bypass. That added platform/cost surface is deferred unless
future public exposure justifies it.

### Uniform RAG authorization

There is support-only indexing but no document-level employee authorization. The
v1.0 corpus is synthetic/uniform internal demo knowledge. A multi-department or
sensitive-document product would need document/tenant ACLs before reusing this
boundary.

### No DLP, semantic deduplication, or OTel collector

These remain outside the bounded v1.0 threat model. Action idempotency protects a
single trusted action identity; traces/logs deliberately avoid business content;
Cloud platform metrics plus direct OTel traces are sufficient for the declared
reference scale.

## Security acceptance review

This model was reviewed against the **deployed merged R4 implementation**, not
only source intent. Live CORS, readiness, rate-limit, browser/mobile, provider,
load and public-data acceptance did not expose a remaining release-blocking
security path.

The real iPhone/Safari form-focus issue found during browser acceptance was fixed
through PR #19 and redeployed before closure. The remaining risks documented
above are deliberate bounded v1.0 residuals, not claims of controls that the
system does not implement.