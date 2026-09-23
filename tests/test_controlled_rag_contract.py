"""
AI Quality v1C Phase 4 controlled RAG regression tests.

These tests execute the real production retrieve_context() function and RAG
prompt constructor while replacing only the vector-search boundary with local
deterministic data. They do not call embeddings, ChromaDB, or any LLM.
"""

from __future__ import annotations

import pytest

from app.prompts.rag_prompts import build_rag_prompt
from app.rag.retriever import retrieve_context
from evals.experiment import Experiment
from evals.schema import EvaluationCase, EvaluatorSpec
from evals.targets import RAGControlledTarget


def test_real_retriever_returns_controlled_policy_context_and_sources():
    calls: list[tuple[str, int]] = []

    def searcher(question: str, *, top_k: int) -> dict:
        calls.append((question, top_k))
        return {
            "context": "Hotel reimbursement is limited to 150 euros per night.",
            "sources": ["travel_policy.txt#chunk-4"],
        }

    result = retrieve_context(
        "What is the hotel reimbursement limit?",
        top_k=3,
        searcher=searcher,
    )

    assert calls == [("What is the hotel reimbursement limit?", 3)]
    assert result == {
        "context": "Hotel reimbursement is limited to 150 euros per night.",
        "sources": ["travel_policy.txt#chunk-4"],
    }


def test_real_retriever_preserves_multiple_source_order():
    expected_sources = [
        "travel_policy.txt#chunk-2",
        "travel_policy.txt#chunk-4",
    ]

    def searcher(_: str, *, top_k: int) -> dict:
        assert top_k == 2
        return {
            "context": "First context\n\nSecond context",
            "sources": list(expected_sources),
        }

    result = retrieve_context(
        "Summarise travel rules.",
        top_k=2,
        searcher=searcher,
    )

    assert result["sources"] == expected_sources
    assert result["context"] == "First context\n\nSecond context"


def test_real_retriever_preserves_empty_retrieval():
    def searcher(_: str, *, top_k: int) -> dict:
        return {
            "context": "",
            "sources": [],
        }

    result = retrieve_context(
        "Unknown policy question",
        searcher=searcher,
    )

    assert result == {
        "context": "",
        "sources": [],
    }


def test_real_retriever_propagates_search_failure():
    def searcher(_: str, *, top_k: int) -> dict:
        raise RuntimeError("controlled vector search unavailable")

    with pytest.raises(
        RuntimeError,
        match="controlled vector search unavailable",
    ):
        retrieve_context(
            "What is the hotel reimbursement limit?",
            searcher=searcher,
        )


def test_real_rag_prompt_contains_controlled_context_and_question():
    prompt = build_rag_prompt(
        "What is the hotel reimbursement limit?",
        "Hotel reimbursement is limited to 150 euros per night.",
    )

    assert "What is the hotel reimbursement limit?" in prompt
    assert "150 euros per night" in prompt
    assert "Do not invent company policies" in prompt


def test_controlled_rag_target_uses_real_retriever_and_prompt():
    target = RAGControlledTarget()

    case = EvaluationCase(
        case_id="controlled-rag-target",
        dataset="unit",
        description="Controlled RAG target",
        target="rag_controlled",
        input={
            "message": "What is the hotel reimbursement limit?",
            "controlled_documents": [
                {
                    "source": "travel_policy.txt#chunk-4",
                    "content": (
                        "Hotel reimbursement is limited to "
                        "150 euros per night."
                    ),
                }
            ],
        },
        evaluators=(
            EvaluatorSpec(
                name="source_match",
                config={
                    "expected": ["travel_policy.txt#chunk-4"],
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(name="controlled-rag-target-test"),
    )

    assert result.output["retrieval_succeeded"] is True
    assert result.output["used_rag"] is True
    assert "150 euros per night" in result.output["rag_context"]
    assert "150 euros per night" in result.output["rag_prompt"]
    assert result.output["sources"] == [
        "travel_policy.txt#chunk-4"
    ]
    assert result.output["search_calls"] == [
        {
            "question": "What is the hotel reimbursement limit?",
            "top_k": 3,
        }
    ]
    assert result.configuration["production_retriever"] is True
    assert result.configuration["production_rag_prompt"] is True
    assert result.configuration["langgraph_routing_executed"] is False
    assert result.configuration["external_embedding_calls"] is False
    assert result.configuration["external_chroma_calls"] is False


def test_controlled_rag_target_distinguishes_failure_from_empty_retrieval():
    target = RAGControlledTarget()

    failure_case = EvaluationCase(
        case_id="controlled-rag-failure",
        dataset="unit",
        description="Controlled retrieval failure",
        target="rag_controlled",
        input={
            "message": "What is the hotel reimbursement limit?",
            "controlled_documents": [],
            "retrieval_behavior": "raise_error",
            "retrieval_error_message": "controlled failure",
        },
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "retrieval_succeeded",
                    "expected": False,
                },
            ),
        ),
    )

    result = target.execute(
        failure_case,
        Experiment(name="controlled-rag-failure-test"),
    )

    assert result.output["retrieval_succeeded"] is False
    assert result.output["error_type"] == "RuntimeError"
    assert result.output["error_message"] == "controlled failure"
    assert result.output["used_rag"] is False
    assert result.output["rag_prompt"] is None
