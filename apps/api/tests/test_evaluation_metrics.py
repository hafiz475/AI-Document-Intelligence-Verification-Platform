"""Deterministic M5 metric definition and regression-rule tests."""

from typing import cast

import pytest

from assureai_api.evaluation_metrics import (
    MetricResult,
    compare_values,
    extraction_metrics,
    rag_metrics,
    retrieval_metrics,
)


def test_extraction_all_fields_correct_and_exact() -> None:
    result = extraction_metrics(
        {"asset": "P-204", "status": "ABNORMAL"},
        {
            "asset": "P-204",
            "status": "ABNORMAL",
        },
    )
    assert result.passed
    assert result.metrics["field_exact_match"] == 1
    assert result.metrics["field_accuracy"] == 1


def test_extraction_one_field_wrong() -> None:
    result = extraction_metrics(
        {"asset": "P-204", "status": "ABNORMAL"},
        {
            "asset": "P-204",
            "status": "NORMAL",
        },
    )
    assert not result.passed
    assert result.metrics["field_accuracy"] == 0.5


def test_extraction_missing_field() -> None:
    result = extraction_metrics({"asset": "P-204", "status": "ABNORMAL"}, {"asset": "P-204"})
    assert result.metrics["missing_field_rate"] == 0.5


def test_extraction_normalized_match_keeps_exact_mismatch_distinct() -> None:
    result = extraction_metrics(
        {"status": "  Abnormal  vibration "},
        {
            "status": "ABNORMAL vibration",
        },
    )
    assert result.metrics["field_exact_match"] == 0
    assert result.metrics["field_normalized_match"] == 1
    assert result.passed


@pytest.mark.parametrize(
    ("actual_quote", "precision", "recall"),
    [
        ("8.4 mm/s RMS", 1.0, 1.0),
        ("invented quote", 0.0, 0.0),
    ],
    ids=["evidence-correct", "evidence-incorrect"],
)
def test_extraction_evidence_metrics(actual_quote: str, precision: float, recall: float) -> None:
    expected = {"vibration": [{"chunk_id": "c1", "page_number": 3, "quote": "8.4 mm/s RMS"}]}
    actual = {"vibration": [{"chunk_id": "c1", "page_number": 3, "quote": actual_quote}]}
    result = extraction_metrics({"vibration": "8.4"}, {"vibration": "8.4"}, expected, actual)
    assert result.metrics["evidence_precision"] == precision
    assert result.metrics["evidence_recall"] == recall


@pytest.mark.parametrize(
    ("retrieved", "expected_hit", "expected_recall", "expected_mrr"),
    [
        (["a"], 1.0, 0.5, 1.0),
        (["x", "y", "a", "z", "b"], 1.0, 1.0, 1 / 3),
        (["x", "y"], 0.0, 0.0, 0.0),
    ],
    ids=["hit-at-1-multiple-expected", "hit-at-5-mrr-rank-over-1", "miss"],
)
def test_retrieval_chunk_hit_recall_and_mrr(
    retrieved: list[str],
    expected_hit: float,
    expected_recall: float,
    expected_mrr: float,
) -> None:
    result = retrieval_metrics(["a", "b"], [], retrieved, [])
    assert result.metrics["chunk_hit_at_k"] == expected_hit
    assert result.metrics["chunk_recall_at_k"] == expected_recall
    assert result.metrics["chunk_mrr"] == expected_mrr


def test_retrieval_document_metrics_are_separate() -> None:
    result = retrieval_metrics([], ["d1", "d2"], [], ["x", "d2"])
    assert result.metrics["document_hit_at_k"] == 1
    assert result.metrics["document_recall_at_k"] == 0.5
    assert result.metrics["document_mrr"] == 0.5
    assert result.metrics["chunk_hit_at_k"] == 0


def rag_result(**overrides: object) -> MetricResult:
    values = {
        "expected_support_status": "SUPPORTED",
        "actual_support_status": "SUPPORTED",
        "required_citation_chunk_ids": ["c1"],
        "forbidden_citation_chunk_ids": ["c9"],
        "citation_chunk_ids": ["c1"],
        "citation_validity": 1.0,
        "required_phrases": ["8.4 mm/s"],
        "forbidden_phrases": ["normal"],
        "answer_text": "Vibration was 8.4 mm/s.",
    }
    values.update(overrides)
    return rag_metrics(**values)  # type: ignore[arg-type]


def test_rag_correct_supported_answer_and_required_citation_phrase() -> None:
    result = rag_result()
    assert result.passed
    assert result.metrics["support_status_correct"]
    assert result.metrics["required_citations_present"]
    assert result.metrics["required_phrases_present"]


@pytest.mark.parametrize(
    ("overrides", "metric"),
    [
        ({"actual_support_status": "PARTIALLY_SUPPORTED"}, "support_status_correct"),
        ({"citation_chunk_ids": []}, "required_citations_present"),
        ({"citation_chunk_ids": ["c1", "c9"]}, "forbidden_citations_absent"),
        ({"citation_validity": 0.0}, "citation_validity"),
        ({"answer_text": "No measurement."}, "required_phrases_present"),
        ({"answer_text": "Normal at 8.4 mm/s."}, "forbidden_phrases_absent"),
    ],
    ids=[
        "incorrect-support",
        "required-citation-missing",
        "forbidden-citation-present",
        "citation-invalid",
        "required-phrase-missing",
        "forbidden-phrase-present",
    ],
)
def test_rag_failure_metrics(overrides: dict[str, object], metric: str) -> None:
    result = rag_result(**overrides)
    assert not result.passed
    assert not result.metrics[metric]


def test_rag_correct_insufficient_evidence() -> None:
    result = rag_result(
        expected_support_status="INSUFFICIENT_EVIDENCE",
        actual_support_status="INSUFFICIENT_EVIDENCE",
        required_citation_chunk_ids=[],
        citation_chunk_ids=[],
        required_phrases=[],
        answer_text=(
            "The available documents do not provide enough evidence to answer this question."
        ),
    )
    assert result.metrics["insufficient_evidence_correct"]
    assert result.metrics["safe_answer_behavior"]


def test_rag_hallucinated_support_when_insufficient_expected() -> None:
    result = rag_result(
        expected_support_status="INSUFFICIENT_EVIDENCE",
        actual_support_status="SUPPORTED",
        required_citation_chunk_ids=[],
        citation_chunk_ids=["c1"],
        required_phrases=[],
    )
    assert not result.metrics["insufficient_evidence_correct"]
    assert not result.passed


@pytest.mark.parametrize(
    ("before", "after", "expected_delta"),
    [(0.5, 0.8, 0.3), (0.8, 0.5, -0.3), (0.8, 0.8, 0.0)],
    ids=["positive-delta", "negative-delta", "no-change"],
)
def test_comparison_deltas(before: float, after: float, expected_delta: float) -> None:
    result = compare_values({"field_accuracy": before}, {"field_accuracy": after}, {})
    assert result["metrics"][0]["delta"] == pytest.approx(expected_delta)


@pytest.mark.parametrize(
    ("thresholds", "after", "expected"),
    [
        ({"minimum_field_accuracy": 0.8}, {"field_accuracy": 0.9}, "PASS"),
        (
            {"maximum_latency_regression_percent": 10},
            {"field_accuracy": 0.9, "average_latency_ms": 130, "total_tokens": 100},
            "WARNING",
        ),
        (
            {"maximum_token_regression_percent": 10},
            {"field_accuracy": 0.9, "average_latency_ms": 100, "total_tokens": 130},
            "WARNING",
        ),
        ({"minimum_field_accuracy": 0.8}, {"field_accuracy": 0.7}, "REGRESSION"),
    ],
    ids=["pass", "latency-regression-warning", "token-regression-warning", "quality-regression"],
)
def test_threshold_statuses(
    thresholds: dict[str, float], after: dict[str, float], expected: str
) -> None:
    before: dict[str, float | int | None] = {
        "field_accuracy": 0.8,
        "average_latency_ms": 100,
        "total_tokens": 100,
    }
    after_values = cast(dict[str, float | int | None], after)
    assert compare_values(before, after_values, thresholds)["status"] == expected
