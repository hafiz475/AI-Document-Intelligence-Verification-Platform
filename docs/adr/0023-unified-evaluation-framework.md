# 0023: Unified evaluation framework

Status: Accepted

## Context

Extraction, retrieval, and RAG quality must be measured through the same persisted,
project-scoped lifecycle without creating evaluation-only AI implementations.

## Decision

Use EvaluationDataset, EvaluationCase, EvaluationRun, and EvaluationCaseResult. One
Dramatiq actor executes a run sequentially through the existing production services,
persists every case outcome, and aggregates deterministic metrics. Runs are limited to
200 cases by default (configurable from 1 to 500).

## Consequences

Quality evidence is queryable and reproducible. Evaluation creates normal product run
records and is intentionally throughput-limited for the demo.
