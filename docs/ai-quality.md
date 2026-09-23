# AI Quality and Deterministic Evaluation

## Purpose

Enterprise AI Assistant treats important AI behavior as a release contract rather than relying only on manual prompt testing. The repository therefore contains an offline deterministic evaluation framework that checks routing, tool selection, RAG contracts, provider fallback, prompt identity, streaming parity, and selected failure behavior without calling external LLM, embedding, or evaluation services.

The deterministic gate complements unit/integration tests and live deployment acceptance; it does not claim that probabilistic model wording can be made fully deterministic.

## Current inventory

The accepted R4 baseline contains **41 active required cases and 0 reserved cases**:

| Dataset | Active cases | Main concern |
| --- | ---: | --- |
| `behavior_cases` | 10 | streaming/non-streaming parity and behavior contracts |
| `rag_cases` | 6 | RAG route, grounding/source, and prompt contracts |
| `routing_cases` | 10 | LangGraph route/tool/prompt decisions |
| `tool_cases` | 15 | tool selection and provider-fallback contracts |
| **Total** | **41** | **all required** |

The last accepted R4 run passed **41/41**. R5 does not treat that historical result as the final release gate; the same suite must pass again on the release commit.

## Architecture

```text
JSON datasets
   ↓
loader + schema validation
   ↓
EvaluationCase
   ↓
target registry
   ├── controlled contract fixture
   ├── controlled LangGraph path
   ├── controlled RAG path
   ├── controlled tool selector
   ├── controlled provider fallback
   └── controlled streaming parity
   ↓
TargetResult
   ↓
deterministic evaluator registry
   ├── exact_match
   ├── contains
   ├── route_match
   ├── tool_match
   ├── source_match
   └── prompt_match
   ↓
CaseResult / ExperimentReport
   ↓
JSON report + process exit code
   ↓
GitHub Actions release gate
```

Datasets live under `evals/datasets/`. Cases are parsed into explicit schema objects; malformed datasets or duplicate case identifiers fail before execution so the gate cannot silently ignore an invalid contract.

## What is controlled

The deterministic targets use controlled fixtures/dependency seams to exercise application-owned behavior without depending on live provider variance. This lets the repository assert properties such as:

- which route is selected;
- whether a tool is selected or deliberately not selected;
- which bounded tool and input are chosen;
- whether RAG context/source contracts are respected;
- which prompt identifier/contract is used;
- provider fallback order and failure representation;
- streaming/non-streaming parity for the behaviors covered by the controlled target.

This design focuses the gate on behavior the application can own and reproduce.

## Gate semantics

Run all deterministic datasets with:

```bash
python -m evals.runner
```

The runner:

1. discovers/selects JSON datasets;
2. validates dataset/case structure and global case-ID uniqueness;
3. executes each active case through a registered deterministic target;
4. applies one or more deterministic evaluators;
5. writes a machine-readable JSON report;
6. exits non-zero if a required active case fails or errors.

Exit codes are:

- `0` — all required active cases passed;
- `1` — at least one required active case failed or errored;
- `2` — dataset/argument/framework configuration error.

Reserved cases, when present in future work, are reported as skipped and are never counted as passing.

## CI integration

`.github/workflows/ci.yml` runs the AI-quality gate after backend dependency installation, quality/security checks, migrations, and the pytest suite:

```text
Backend quality / dependency / repository checks
   ↓
Alembic migrations
   ↓
pytest
   ↓
python -m evals.runner
   ↓
JSON report uploaded as a GitHub Actions artifact
```

The CI command writes `evals/results/ci-ai-quality-report.json`. The report upload runs even after a gate failure when a report exists, so failures remain diagnosable without converting the original non-zero gate result into success.

## Relationship to the backend test suite

The deterministic AI gate and pytest suite deliberately overlap only where useful:

- **pytest** protects code-level behavior, APIs, persistence, authorization, controlled seams, MCP protocol behavior, provider identity/fallback contracts, streaming regressions, and other deterministic implementation details;
- **AI evaluations** organize selected AI-system behavior as named release contracts across routing, prompts, sources, tools, fallback, and parity.

Passing one is not a substitute for passing the other.

## What this gate does not prove

The gate does **not** prove:

- that every live LLM response will use identical wording;
- that a provider has available quota or billing at a future time;
- that embeddings or model outputs from external services are deterministic;
- that the system is safe for arbitrary enterprise domains or unrestricted tools;
- that live cloud behavior can be replaced by offline evaluation.

Those concerns are handled by a combination of application controls, backend tests, provider/error handling, live deployment acceptance, observability, security review, and documented limitations.

## Release rule

For Portfolio v1.0, the deterministic AI-quality gate is mandatory. The final release commit must pass all 41 required active cases and GitHub Actions must be green before `v1.0.0` is created.
