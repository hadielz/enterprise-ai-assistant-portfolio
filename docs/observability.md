# Observability Architecture

## Scope

The accepted reference deployment uses a bounded production-observability baseline without changing AI/provider/tool semantics. The design uses vendor-neutral OpenTelemetry traces, structured JSON logs on stdout, and Google Cloud's built-in Cloud Run/Cloud SQL metrics.

It intentionally does **not** add a Prometheus/Grafana stack, a custom metrics backend, or an OpenTelemetry Collector service merely for breadth.

## Runtime modes

Local/tests:

```text
OTEL_ENABLED=false
```

Optional local debugging:

```text
OTEL_ENABLED=true
OTEL_EXPORTER=console
OTEL_SAMPLE_RATIO=1.0
```

Cloud Run:

```text
OTEL_ENABLED=true
OTEL_EXPORTER=gcp_otlp
OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.googleapis.com:443/v1/traces
OTEL_SAMPLE_RATIO=0.1
GOOGLE_CLOUD_PROJECT=<project-id>
```

The cloud runtime uses its attached service account through Application Default Credentials. Traces are exported directly to Google's OTLP Telemetry endpoint. Structured logs are written to stdout and ingested by Cloud Run/Cloud Logging.

## Why direct OTLP instead of a collector

A collector is a strong option when the application needs one place to fan out traces, metrics, and logs, or requires advanced processing. This reference application currently needs only a small trace pipeline while Cloud Run already captures stdout logs and Cloud Run/Cloud SQL already provide operational metrics.

The reference deployment therefore uses direct OTLP trace export to avoid adding a sidecar/multi-container collector solely for architecture breadth. The application-facing instrumentation remains OpenTelemetry, so moving to a collector later does not require redesigning business code.

## Correlation model

The application keeps its existing `request_id` as an application correlation ID. It is not replaced by the OpenTelemetry trace ID.

```text
request_id
    +
trace_id / span_id
    +
conversation_id
    +
route / provider / tool / action status
```

`backend/app/observability/context.py` binds request and conversation identifiers with `ContextVar`s for the lifetime of a generation. The JSON log formatter adds active trace/span IDs when a sampled trace exists.

When `GOOGLE_CLOUD_PROJECT` is set, logs also emit Cloud Logging's recognized trace/span correlation fields.

## High-value trace boundaries

Automatic instrumentation covers:

- inbound FastAPI requests;
- SQLAlchemy operations;
- `requests` HTTP calls;
- `httpx` HTTP calls.

Application spans cover high-value AI/business boundaries:

```text
assistant.generate / assistant.stream
├── ai.tool_selection
├── ai.provider.generate / ai.provider.stream
├── rag.retrieve
│   └── rag.embedding
└── tool.ticket
    └── mcp.ticket.create
        ↓ W3C trace context
        MCP ASGI request
        └── ticket.create
            └── ticket.repository.create
```

The code deliberately does not wrap every function in a span.

## Backend → MCP propagation

The MCP client injects W3C trace context into the actual Streamable-HTTP transport. In cloud mode it separately adds the Google-signed Cloud Run identity token in `X-Serverless-Authorization`.

The MCP ASGI application is wrapped with OpenTelemetry ASGI middleware, so propagated trace context can continue on the server side.

## Structured logging policy

Structured logs may contain bounded operational metadata such as:

- event name;
- service;
- request ID;
- conversation ID;
- trace/span ID;
- route;
- provider/model name;
- fallback flag;
- tool name;
- safe-action status;
- ticket public ID/status;
- RAG vector backend/result count;
- error class.

They must not intentionally include:

- passwords;
- JWTs;
- provider API keys;
- database credentials;
- MCP identity tokens;
- full user messages;
- full ticket descriptions;
- retrieved document text/context;
- raw LLM/provider responses.

The tool selector preserves the provider's raw response internally for protocol diagnostics, but telemetry records only the protocol outcome and normalization mode (for example `complete_markdown_fence`).

## Durable ticket partial-success behavior

R2 intentionally commits a durable ticket before asking the final LLM to phrase `tool.answer.v1`. R3 made that sequence observable. R4 kept the transaction order and improved the user-facing provider-exhaustion case when durable creation is already known.

It does make the two states distinguishable:

```text
tool_side_effect_committed
```

followed, if answer generation fails, by:

```text
tool_answer_generation_failed_after_side_effect
```

with `action_status=committed_response_failed` and the durable ticket public ID. In the accepted R4 behavior, `LLMProviderError` after a committed ticket produces a deterministic response that confirms the durable ticket ID instead of presenting the request as a total failure. Streaming appends that deterministic confirmation if partial provider text was already emitted. Ordinary provider exhaustion with no committed side effect keeps the previously characterized behavior, and unexpected exceptions are not converted into success. The same telemetry event remains available for operator diagnosis.

## Provider observability

Provider attempts emit spans/log fields for:

- provider;
- model;
- whether the candidate is a fallback;
- success/failure;
- error class;
- streaming versus non-streaming operation.

No provider fallback rule is changed by observability.

Token usage is not fabricated. It is not emitted unless a future provider integration exposes a reliable common contract.

## RAG observability

RAG spans expose only bounded metadata:

- `rag.vector_backend`;
- `rag.top_k`;
- result count;
- result/no-result/error outcome;
- embedding provider/model.

Document content is not added to traces/logs.


## R4 health and abuse-control observability

R4 keeps `/health` as liveness and adds PostgreSQL-aware `/ready` for backend and
MCP traffic eligibility. Provider billing/quota state is not a readiness input.
Cloud Run's platform metrics remain the primary signal for probe failures and 5xx
behavior.

The R4 application rate limiter is intentionally process-local. HTTP 429 responses
and the `Retry-After` header are the observable contract; R4 does not add a custom
metrics backend solely for rate-limit counters. Repeated limiter behavior can be
correlated with existing Cloud Run request logs without logging credentials, user
messages, or ticket descriptions.

## Operational view

Use Cloud Run built-in service metrics for request volume, latency, instance count, CPU and memory. Use Cloud SQL built-in metrics for connections, CPU, storage and database health. The reference deployment does not duplicate these as custom application metrics.

Useful Cloud Logging queries include:

```text
resource.type="cloud_run_revision"
jsonPayload.request_id="<request-id>"
```

```text
resource.type="cloud_run_revision"
jsonPayload.event="mcp_ticket_call_failed"
```

```text
resource.type="cloud_run_revision"
jsonPayload.event="tool_answer_generation_failed_after_side_effect"
```

In Trace Explorer, inspect the sampled request trace and verify that the backend HTTP request, AI spans, MCP client span and MCP server span share propagated trace context.

## Alerts

The reference deployment relies first on Cloud Run/Cloud SQL built-in signals. For the deployed reference environment, create only bounded alerts such as:

1. Cloud Run backend 5xx/error-rate alert.
2. Cloud SQL connection/utilization alert appropriate to the selected instance size.

Exact thresholds should be selected after observing the deployed demo baseline rather than hard-coded in source as universal values.
