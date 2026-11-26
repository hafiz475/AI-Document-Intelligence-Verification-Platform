# AssureAI API

All `/api/v1` routes except the development login/logout adapter require a valid signed
session or OIDC bearer token. Project routes enforce OWNER/EDITOR/VIEWER membership
server-side. Errors use `{ "error": { "code", "message", "request_id" } }`.

Identity and membership endpoints:

- `POST /api/v1/auth/development/login` (development/demo only)
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET/POST /api/v1/projects/{project_id}/members` (OWNER)
- `PATCH/DELETE /api/v1/projects/{project_id}/members/{user_id}` (OWNER)
- `GET /api/v1/projects/{project_id}/security/config` (OWNER; status only, no values)

The interactive OpenAPI document is served at `/docs`. All document, retrieval, and
question resources are project scoped.

## Create a project question

`POST /api/v1/projects/{project_id}/questions`

For document-only retrieval, use
`POST /api/v1/projects/{project_id}/documents/{document_id}/questions`.

Request:

```json
{
  "question": "What abnormal condition was detected?",
  "top_k": 5
}
```

`question` is 1-4,000 characters after trimming. `top_k` defaults to 5 and accepts
1-10. A valid request returns HTTP 202 with a QUEUED question. Processing is asynchronous
through Dramatiq so provider latency does not hold an API request open.

## List and inspect questions

- `GET /api/v1/projects/{project_id}/questions`
- `GET /api/v1/projects/{project_id}/questions?document_id={document_id}`
- `GET /api/v1/projects/{project_id}/questions/{question_id}`

Question responses include:

- queue status and safe error message
- question and project/document scope
- provider, model, immutable prompt version, latency, and available token usage
- answer text and SUPPORTED, PARTIALLY_SUPPORTED, or INSUFFICIENT_EVIDENCE
- validated citations with document, page, rank, similarity, quote, and chunk ID
- every retrieved source, including uncited sources, with embedding provenance

Example completed answer:

```json
{
  "status": "COMPLETED",
  "answer": {
    "answer_text": "The drive-end bearing vibration measured 8.4 mm/s RMS.",
    "support_status": "SUPPORTED",
    "confidence": null,
    "citations": [
      {
        "document_name": "pump-inspection.txt",
        "page_number": 3,
        "rank": 1,
        "similarity_score": 0.91,
        "quote": "Observation: Drive-end bearing vibration measured 8.4 mm/s RMS.",
        "chunk_id": "..."
      }
    ]
  },
  "retrieved_sources": []
}
```

No numeric confidence is returned because M4 does not derive a calibrated value.

An unsupported question completes safely:

```json
{
  "status": "COMPLETED",
  "answer": {
    "answer_text": "The available documents do not provide enough evidence to answer this question.",
    "support_status": "INSUFFICIENT_EVIDENCE",
    "confidence": null,
    "citations": []
  }
}
```

## Controlled failures

- 404: the project, document, or question does not exist in the requested project
- 422: invalid question or top-k
- 503: embedding or answer generation is disabled, or queue submission failed
- FAILED question: retrieval unavailable, provider failure, invalid structured output,
  or citation validation failure

Raw provider errors and stack traces are not returned. A FAILED question never exposes
an unvalidated answer.

## Unified evaluation

All evaluation resources are project scoped:

- POST/GET /api/v1/projects/{project_id}/evaluation-datasets
- GET /api/v1/projects/{project_id}/evaluation-datasets/{dataset_id}
- POST/GET /api/v1/projects/{project_id}/evaluation-datasets/{dataset_id}/cases
- PATCH /api/v1/projects/{project_id}/evaluation-datasets/{dataset_id}/cases/{case_id}
- POST/GET /api/v1/projects/{project_id}/evaluation-runs
- GET /api/v1/projects/{project_id}/evaluation-runs/{run_id}
- POST /api/v1/projects/{project_id}/evaluation-comparisons

Dataset types are EXTRACTION, RETRIEVAL, and RAG. Case input and expected JSON are
validated against the selected type and all document/chunk references must belong to the
project. A run request selects dataset_id, optional prompt/provider/model/embedding
provenance, and top_k (1-20). The deployment rejects unconfigured providers and fixed
development-model substitutions.

Runs return QUEUED, PROCESSING, COMPLETED, or FAILED plus counts, average score/latency,
available token totals, aggregate metrics, exact configuration, evaluator version, and
PASSED/FAILED/ERROR case results. Each result includes the immutable case snapshot,
actual output, metrics, latency, available tokens, and a safe error.

Comparison requires two completed runs from the same dataset:

    {
      "run_a_id": "...",
      "run_b_id": "...",
      "thresholds": {
        "minimum_pass_rate": 0.9,
        "maximum_latency_regression_percent": 20,
        "maximum_token_regression_percent": 25
      },
      "allow_incompatible_embeddings": false
    }

The response contains every metric's run A value, run B value, delta, embedding
compatibility, and advisory PASS, WARNING, or REGRESSION status.
