"""Deterministic evaluator v1 metrics and comparison rules."""

from dataclasses import dataclass
from typing import Any

EVALUATOR_VERSION = "v1"
INSUFFICIENT_EVIDENCE_ANSWER = (
    "The available documents do not provide enough evidence to answer this question."
)


@dataclass(frozen=True)
class MetricResult:
    score: float
    passed: bool
    metrics: dict[str, Any]


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def extraction_metrics(
    expected_fields: dict[str, Any],
    actual_fields: dict[str, Any],
    expected_evidence: dict[str, list[dict[str, Any]]] | None = None,
    actual_evidence: dict[str, list[dict[str, Any]]] | None = None,
) -> MetricResult:
    per_field: dict[str, dict[str, bool]] = {}
    exact_correct = 0
    normalized_correct = 0
    missing = 0
    for name, expected in expected_fields.items():
        actual = actual_fields.get(name)
        exact = actual == expected
        normalized = (
            normalize_text(actual) == normalize_text(expected)
            if isinstance(actual, str) and isinstance(expected, str)
            else exact
        )
        per_field[name] = {"exact_match": exact, "normalized_match": normalized}
        exact_correct += int(exact)
        normalized_correct += int(normalized)
        missing += int(actual is None)
    total = len(expected_fields)
    accuracy = normalized_correct / total if total else 0.0
    metrics: dict[str, Any] = {
        "field_exact_match": exact_correct / total if total else 0.0,
        "field_normalized_match": accuracy,
        "field_accuracy": accuracy,
        "correct_fields": normalized_correct,
        "total_fields": total,
        "missing_field_rate": missing / total if total else 0.0,
        "per_field": per_field,
    }
    if expected_evidence:
        expected_items = {
            (
                field,
                item["chunk_id"],
                item.get("page_number"),
                normalize_text(item.get("quote") or ""),
            )
            for field, items in expected_evidence.items()
            for item in items
        }
        actual_items = {
            (
                field,
                item["chunk_id"],
                item.get("page_number"),
                normalize_text(item.get("quote") or ""),
            )
            for field, items in (actual_evidence or {}).items()
            for item in items
        }
        correct = len(expected_items & actual_items)
        metrics["evidence_precision"] = correct / len(actual_items) if actual_items else 0.0
        metrics["evidence_recall"] = correct / len(expected_items) if expected_items else 1.0
    return MetricResult(score=accuracy, passed=accuracy == 1.0, metrics=metrics)


def retrieval_metrics(
    expected_chunk_ids: list[str],
    expected_document_ids: list[str],
    retrieved_chunk_ids: list[str],
    retrieved_document_ids: list[str],
    maximum_first_relevant_rank: int | None = None,
) -> MetricResult:
    def values(expected: list[str], retrieved: list[str]) -> tuple[float, float, float, int | None]:
        expected_set = set(expected)
        positions = [
            rank for rank, item_id in enumerate(retrieved, start=1) if item_id in expected_set
        ]
        first_rank = positions[0] if positions else None
        hit = float(first_rank is not None)
        recall = (
            len(expected_set.intersection(retrieved)) / len(expected_set) if expected_set else 0.0
        )
        mrr = 1.0 / first_rank if first_rank else 0.0
        return hit, recall, mrr, first_rank

    chunk_hit, chunk_recall, chunk_mrr, first_rank = values(expected_chunk_ids, retrieved_chunk_ids)
    document_hit, document_recall, document_mrr, document_first_rank = values(
        expected_document_ids, retrieved_document_ids
    )
    active_scores = []
    if expected_chunk_ids:
        active_scores.append((chunk_hit + chunk_recall + chunk_mrr) / 3)
    if expected_document_ids:
        active_scores.append((document_hit + document_recall + document_mrr) / 3)
    rank_ok = maximum_first_relevant_rank is None or (
        first_rank is not None and first_rank <= maximum_first_relevant_rank
    )
    score = sum(active_scores) / len(active_scores)
    return MetricResult(
        score=score,
        passed=all(value == 1.0 for value in active_scores) and rank_ok,
        metrics={
            "chunk_hit_at_k": chunk_hit,
            "chunk_recall_at_k": chunk_recall,
            "chunk_mrr": chunk_mrr,
            "chunk_first_relevant_rank": first_rank,
            "document_hit_at_k": document_hit,
            "document_recall_at_k": document_recall,
            "document_mrr": document_mrr,
            "document_first_relevant_rank": document_first_rank,
            "maximum_first_relevant_rank_met": rank_ok,
        },
    )


def rag_metrics(
    *,
    expected_support_status: str,
    actual_support_status: str,
    required_citation_chunk_ids: list[str],
    forbidden_citation_chunk_ids: list[str],
    citation_chunk_ids: list[str],
    citation_validity: float,
    required_phrases: list[str],
    forbidden_phrases: list[str],
    answer_text: str,
) -> MetricResult:
    citation_set = set(citation_chunk_ids)
    answer = normalize_text(answer_text)
    checks: dict[str, bool | float] = {
        "support_status_correct": actual_support_status == expected_support_status,
        "required_citations_present": set(required_citation_chunk_ids) <= citation_set,
        "forbidden_citations_absent": not bool(set(forbidden_citation_chunk_ids) & citation_set),
        "citation_validity": citation_validity,
        "required_phrases_present": all(
            normalize_text(phrase) in answer for phrase in required_phrases
        ),
        "forbidden_phrases_absent": all(
            normalize_text(phrase) not in answer for phrase in forbidden_phrases
        ),
    }
    insufficient_expected = expected_support_status == "INSUFFICIENT_EVIDENCE"
    checks["insufficient_evidence_correct"] = (
        actual_support_status == "INSUFFICIENT_EVIDENCE" and not citation_chunk_ids
        if insufficient_expected
        else True
    )
    checks["safe_answer_behavior"] = (
        not citation_chunk_ids
        and actual_support_status == "INSUFFICIENT_EVIDENCE"
        and answer == normalize_text(INSUFFICIENT_EVIDENCE_ANSWER)
        if insufficient_expected
        else True
    )
    boolean_values = [value for value in checks.values() if isinstance(value, bool)]
    score = (sum(boolean_values) + citation_validity) / (len(boolean_values) + 1)
    return MetricResult(
        score=score,
        passed=all(boolean_values) and citation_validity == 1.0,
        metrics={**checks, "groundedness": citation_validity},
    )


def aggregate_metrics(case_metrics: list[dict[str, Any]]) -> dict[str, float]:
    numeric: dict[str, list[float]] = {}
    for metrics in case_metrics:
        for key, value in metrics.items():
            if isinstance(value, bool | int | float):
                numeric.setdefault(key, []).append(float(value))
    return {key: sum(values) / len(values) for key, values in sorted(numeric.items()) if values}


def compare_values(
    run_a: dict[str, float | int | None],
    run_b: dict[str, float | int | None],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    metrics: list[dict[str, float | str | None]] = []
    for name in sorted(set(run_a) | set(run_b)):
        a = run_a.get(name)
        b = run_b.get(name)
        metrics.append(
            {
                "metric": name,
                "run_a": float(a) if a is not None else None,
                "run_b": float(b) if b is not None else None,
                "delta": float(b) - float(a) if a is not None and b is not None else None,
            }
        )
    quality_regression = any(
        float(run_b.get(name.removeprefix("minimum_")) or 0.0) < minimum
        for name, minimum in thresholds.items()
        if name.startswith("minimum_") and (name.removeprefix("minimum_") in run_b)
    )
    latency_limit = thresholds.get("maximum_latency_regression_percent")
    token_limit = thresholds.get("maximum_token_regression_percent")

    def regression_percent(name: str) -> float:
        before = float(run_a.get(name) or 0.0)
        after = float(run_b.get(name) or 0.0)
        if before:
            return (after - before) / before * 100
        return 0.0 if after == 0 else 100.0

    latency_warning = (
        latency_limit is not None and regression_percent("average_latency_ms") > latency_limit
    )
    token_warning = token_limit is not None and regression_percent("total_tokens") > token_limit
    status = (
        "REGRESSION"
        if quality_regression
        else ("WARNING" if latency_warning or token_warning else "PASS")
    )
    return {
        "status": status,
        "metrics": metrics,
        "latency_regression_percent": regression_percent("average_latency_ms"),
        "token_regression_percent": regression_percent("total_tokens"),
    }
