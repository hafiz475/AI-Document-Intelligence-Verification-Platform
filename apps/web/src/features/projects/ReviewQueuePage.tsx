import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { ReviewQueueItem, ReviewStatus } from "../../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useReviewField, useReviewQueue } from "../hooks";

const PAGE_SIZE = 10;
const show = (value: unknown) => {
  if (value === null || value === undefined) return "Not found";
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  )
    return String(value);
  return JSON.stringify(value);
};

function QueueCard({
  item,
  projectId,
}: {
  item: ReviewQueueItem;
  projectId: string;
}) {
  const review = useReviewField(projectId, item.document_id);
  const [mode, setMode] = useState<"correct" | "reject" | null>(null);
  const [value, setValue] = useState(show(item.field.normalized_value));
  const [reason, setReason] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mode === "correct")
      review.mutate({
        runId: item.extraction_run_id,
        fieldId: item.field.id,
        review: { decision: "CORRECTED", value, reason },
      });
    else
      review.mutate({
        runId: item.extraction_run_id,
        fieldId: item.field.id,
        review: { decision: "REJECTED", reason },
      });
  };
  return (
    <article className="review-queue-card">
      <header>
        <div>
          <p className="eyebrow">{item.document_name}</p>
          <h2>{item.field.field_name.replaceAll("_", " ")}</h2>
        </div>
        <div className="badge-group">
          <StatusBadge status={item.field.support_status} />
          <StatusBadge status={item.field.review_status} />
        </div>
      </header>
      <div className="review-value-grid">
        <div>
          <small>AI VALUE</small>
          <strong>{show(item.field.normalized_value)}</strong>
        </div>
        <div>
          <small>EVIDENCE</small>
          {item.field.evidence[0] ? (
            <blockquote>{item.field.evidence[0].quote}</blockquote>
          ) : (
            <span>No validated evidence</span>
          )}
        </div>
      </div>
      <p className="muted">
        {item.provider} / {item.model}
      </p>
      <div className="review-actions">
        <button
          disabled={review.isPending}
          onClick={() =>
            review.mutate({
              runId: item.extraction_run_id,
              fieldId: item.field.id,
              review: { decision: "VERIFIED" },
            })
          }
        >
          Verify
        </button>
        <button className="button secondary" onClick={() => setMode("correct")}>
          Correct
        </button>
        <button className="button danger" onClick={() => setMode("reject")}>
          Reject
        </button>
        <Link
          to={`/app/projects/${projectId}/documents/${item.document_id}?tab=evidence&field=${item.field.id}`}
        >
          Open evidence
        </Link>
      </div>
      {mode && (
        <form className="review-form" onSubmit={submit}>
          {mode === "correct" && (
            <label>
              Corrected value
              <textarea
                required
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </label>
          )}
          <label>
            {mode === "correct" ? "Correction reason" : "Rejection reason"}
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="review-actions">
            <button disabled={review.isPending}>Save review</button>
            <button
              className="button secondary"
              type="button"
              onClick={() => setMode(null)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      {review.isError && <ErrorState error={review.error} />}
    </article>
  );
}

export function ReviewQueuePage() {
  const { projectId = "" } = useParams();
  const [status, setStatus] = useState<ReviewStatus>("UNREVIEWED");
  const [fieldName, setFieldName] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [offset, setOffset] = useState(0);
  const queue = useReviewQueue(projectId, {
    status,
    fieldName,
    documentId,
    createdFrom: createdFrom || undefined,
    createdTo: createdTo ? `${createdTo}T23:59:59Z` : undefined,
    limit: PAGE_SIZE,
    offset,
  });
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Human verification</p>
          <h1>Review Queue</h1>
          <p>
            Verify, correct, or reject fields across project documents without
            losing the original AI value.
          </p>
        </div>
      </div>
      <div className="filter-bar">
        <label>
          Review status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as ReviewStatus);
              setOffset(0);
            }}
          >
            {["UNREVIEWED", "VERIFIED", "CORRECTED", "REJECTED"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Field name
          <input
            placeholder="asset_id"
            value={fieldName}
            onChange={(e) => {
              setFieldName(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Document ID
          <input
            placeholder="Document identifier"
            value={documentId}
            onChange={(e) => {
              setDocumentId(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          From
          <input
            type="date"
            value={createdFrom}
            onChange={(e) => {
              setCreatedFrom(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={createdTo}
            onChange={(e) => {
              setCreatedTo(e.target.value);
              setOffset(0);
            }}
          />
        </label>
      </div>
      {queue.isLoading && <LoadingState label="Loading review queue…" />}
      {queue.isError && <ErrorState error={queue.error} />}
      <div className="review-queue">
        {queue.data?.items.map((item) => (
          <QueueCard item={item} key={item.field.id} projectId={projectId} />
        ))}
      </div>
      {queue.data && !queue.data.items.length && (
        <EmptyState
          title="Review queue is clear"
          detail="No fields match the selected review status and filters."
        />
      )}
      {queue.data && queue.data.total > PAGE_SIZE && (
        <div className="pagination">
          <button
            className="button secondary"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, queue.data.total)} of{" "}
            {queue.data.total}
          </span>
          <button
            className="button secondary"
            disabled={offset + PAGE_SIZE >= queue.data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
}
