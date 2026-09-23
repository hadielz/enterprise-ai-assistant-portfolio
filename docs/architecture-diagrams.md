# Architecture Diagrams

These diagrams are the reviewer-facing visual companion to the detailed architecture documents. They summarize the accepted R0-R4 implementation that R5 packages for Portfolio v1.0; they do not introduce new runtime behavior.

## 1. System and cloud architecture

```mermaid
flowchart LR
    User[Browser user]

    subgraph Cloud["Accepted GCP reference deployment"]
        FE[Cloud Run frontend<br/>public HTTPS]
        BE[Cloud Run backend<br/>public transport + JWT auth]
        MCP[Cloud Run MCP<br/>IAM-private]
        DB[(Cloud SQL PostgreSQL<br/>application state + pgvector)]
        SM[Secret Manager]
        MIG[Cloud Run migration Job<br/>Alembic upgrade head]
        TRACE[Google Telemetry / Cloud Trace]
        LOG[Cloud Logging]
    end

    Providers[OpenAI / Gemini<br/>LLM + embedding providers]

    User --> FE
    FE --> BE

    BE --> DB
    BE --> Providers
    SM -. runtime secrets .-> BE
    SM -. runtime secrets .-> MCP

    BE -->|Google-signed identity token| MCP
    MCP --> DB
    MIG --> DB

    BE -. OpenTelemetry traces .-> TRACE
    MCP -. OpenTelemetry traces .-> TRACE
    BE -. structured JSON stdout .-> LOG
    MCP -. structured JSON stdout .-> LOG
```

Important boundary: Cloud Run transport to the backend is public because registration/login must be reachable, while application JWT authorization protects authenticated application semantics. The MCP service remains IAM-private.

## 2. Ticket creation and MCP safe-action sequence

```mermaid
sequenceDiagram
    actor U as User
    participant B as Backend
    participant A as Tool selector
    participant S as Safe-action policy
    participant M as Private MCP + ticket service
    participant D as PostgreSQL
    participant L as LLM providers

    U->>B: Authenticated ticket request
    B->>A: Select route and tool
    A-->>B: ticket_creator + bounded input
    B->>S: Validate context + bounds
    S-->>B: Allowed
    B->>M: create_ticket via MCP
    M->>D: Commit durable ticket
    D-->>M: Ticket + public ID
    M-->>B: Durable result
    B->>L: Request final wording

    alt Provider succeeds
        L-->>B: Final response
    else Provider exhaustion after confirmed commit
        L--xB: All providers fail
        B->>B: Deterministic persisted-ticket confirmation
    end

    B-->>U: Response with durable ticket ID
```

For readability, the sequence groups the private MCP server and its internal ticket service/repository into one participant; the implementation still follows the real MCP boundary before durable PostgreSQL persistence. The LLM does not receive unrestricted database authority, and a model-selected business action must pass deterministic application policy.

## 3. RAG indexing and grounded-answer flow

```mermaid
flowchart TB
    subgraph Indexing["INDEXING — support-only"]
        direction LR
        Support[Support user] --> IndexAPI[POST /api/rag/index]
        IndexAPI --> Docs[TXT / PDF corpus]
        Docs --> Loader[Load + chunk]
        Loader --> ChunkEmbed[OpenAI<br/>chunk embeddings]
    end

    Store[(Vector store<br/>Chroma / pgvector)]

    subgraph Query["QUERY — grounded answer"]
        direction LR
        Employee[Authenticated user] --> Chat[Chat service]
        Chat --> Retrieve[Retriever<br/>embed query + search]
        Retrieve --> Prompt[Versioned RAG prompt<br/>context + sources]
        Prompt --> LLM[Provider abstraction]
        LLM --> Answer[Grounded response]
    end

    ChunkEmbed --> Store
    Store -->|top chunks + source IDs| Retrieve
```

The retriever groups the query-embedding and vector-search steps for readability; both indexing and query-time retrieval use the configured OpenAI embedding path. The local default vector backend is Chroma, while the durable cloud-reference path uses PostgreSQL/pgvector. The synthetic v1.0 corpus is treated as a uniform knowledge domain; document-level ACLs are an explicit non-goal for this release.

## 4. Deterministic AI-quality and CI gate

```mermaid
flowchart LR
    Datasets["JSON datasets<br/>41 active required cases"]
    Validation["Schema + case-ID validation"]
    Targets["Controlled targets<br/>routing / RAG / tools<br/>fallback / parity"]
    Evaluators["Deterministic evaluators"]
    Report["ExperimentReport<br/>+ process exit code"]
    CI["GitHub Actions<br/>release gate"]

    Datasets --> Validation --> Targets --> Evaluators --> Report --> CI
```

The diagram groups internal `EvaluationCase`, `TargetResult`, and individual evaluator/reporting types so the release pipeline remains readable at normal GitHub width; [`ai-quality.md`](ai-quality.md) documents those details. The deterministic gate focuses on behavior the application can own and reproduce: routing, tool selection, RAG contracts, provider fallback, prompt identity, and selected streaming/non-streaming parity. It complements pytest and live cloud acceptance; it does not claim deterministic wording from external LLMs.

## Related documentation

- [`architecture.md`](architecture.md) — detailed runtime and cloud architecture
- [`ai-quality.md`](ai-quality.md) — deterministic evaluation design and gate semantics
- [`deployment-gcp.md`](deployment-gcp.md) — accepted GCP deployment/runbook
- [`observability.md`](observability.md) — traces, logging, correlation, and operational view
- [`security-baseline.md`](security-baseline.md) — accepted security controls and residual risks
- [`known-limitations.md`](known-limitations.md) — intentional v1.0 limitations
