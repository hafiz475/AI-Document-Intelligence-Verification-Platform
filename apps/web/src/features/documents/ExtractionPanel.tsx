import { type FormEvent, useState } from "react";

import type {
  ExtractedField,
  ExtractedValue,
  ExtractionRun,
  FieldReview,
} from "../../api/types";
import { ErrorState, LoadingState, StatusBadge } from "../../components/States";
import { useCreateExtraction, useExtractions, useReviewField } from "../hooks";

function fieldLabel(name: string): string {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function displayValue(value: ExtractedValue): string {
  if (Array.isArray(value)) return value.join("; ");
  return value ?? "Not found";
}

function FieldCard({
  field,
  runId,
  projectId,
  documentId,
  canEdit,
}: {
  field: ExtractedField;
  runId: string;
  projectId: string;
  documentId: string;
  canEdit: boolean;
}) {
  const review = useReviewField(projectId, documentId);
  const [mode, setMode] = useState<"correct" | "reject" | null>(null);
  const [value, setValue] = useState(
    displayValue(field.normalized_value) === "Not found"
      ? ""
      : displayValue(field.normalized_value),
  );
  const [reason, setReason] = useState("");
  const effectiveValue =
    field.review_status === "CORRECTED"
      ? field.corrected_value
      : field.normalized_value;

  function submit(reviewPayload: FieldReview) {
    review.mutate(
      { runId, fieldId: field.id, review: reviewPayload },
      { onSuccess: () => setMode(null) },
    );
  }

  function submitCorrection(event: FormEvent) {
    event.preventDefault();
    const corrected =
      field.field_type === "string_list"
        ? value
            .split("\\n")
            .map((item) => item.trim())
            .filter(Boolean)
        : value.trim();
    submit({
      decision: "CORRECTED",
      value: corrected,
      reason,
    });
  }

  function submitRejection(event: FormEvent) {
    event.preventDefault();
    submit({ decision: "REJECTED", reason });
  }

  return (
    <article className="extraction-field">
      <header>
        <div>
          <p className="field-label">{fieldLabel(field.field_name)}</p>
          <p className="field-value">{displayValue(effectiveValue)}</p>
          {field.review_status === "CORRECTED" && (
            <p className="muted">
              <strong>Original AI value:</strong>{" "}
              {displayValue(field.normalized_value)}
            </p>
          )}
          {field.missing_reason && (
            <p className="muted">Missing: {field.missing_reason}</p>
          )}
        </div>
        <div className="badge-group">
          <StatusBadge status={field.support_status} />
          <StatusBadge status={field.review_status} />
        </div>
      </header>

      {field.evidence.length > 0 ? (
        <details className="evidence-view">
          <summary>Evidence ({field.evidence.length})</summary>
          {field.evidence.map((evidence) => (
            <div className="evidence-item" key={evidence.id}>
              <strong>
                {evidence.page_number
                  ? `Page ${evidence.page_number}`
                  : "Source chunk"}
              </strong>
              <code>{evidence.document_chunk_id}</code>
              <blockquote>{evidence.quote}</blockquote>
            </div>
          ))}
        </details>
      ) : (
        <p className="muted">No validated evidence.</p>
      )}

      {canEdit && field.review_status === "UNREVIEWED" && (
        <div className="review-actions">
          <button
            disabled={review.isPending}
            onClick={() => submit({ decision: "VERIFIED" })}
            type="button"
          >
            Verify
          </button>
          <button
            className="button secondary"
            disabled={review.isPending}
            onClick={() => {
              setMode("correct");
              setReason("");
            }}
            type="button"
          >
            Correct
          </button>
          <button
            className="button danger"
            disabled={review.isPending}
            onClick={() => {
              setMode("reject");
              setReason("");
            }}
            type="button"
          >
            Reject
          </button>
        </div>
      )}

      {mode === "correct" && (
        <form className="review-form" onSubmit={submitCorrection}>
          <label>
            Corrected value
            <textarea
              onChange={(event) => setValue(event.target.value)}
              required
              rows={field.field_type === "string_list" ? 4 : 2}
              value={value}
            />
          </label>
          <label>
            Reason
            <textarea
              onChange={(event) => setReason(event.target.value)}
              required
              rows={2}
              value={reason}
            />
          </label>
          <div className="review-actions">
            <button disabled={review.isPending} type="submit">
              Save correction
            </button>
            <button
              className="button secondary"
              onClick={() => setMode(null)}
              type="button"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {mode === "reject" && (
        <form className="review-form" onSubmit={submitRejection}>
          <label>
            Rejection reason
            <textarea
              onChange={(event) => setReason(event.target.value)}
              required
              rows={2}
              value={reason}
            />
          </label>
          <div className="review-actions">
            <button disabled={review.isPending} type="submit">
              Confirm rejection
            </button>
            <button
              className="button secondary"
              onClick={() => setMode(null)}
              type="button"
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

function ExtractionResult({
  run,
  projectId,
  documentId,
  canEdit,
}: {
  run: ExtractionRun;
  projectId: string;
  documentId: string;
  canEdit: boolean;
}) {
  if (run.status === "QUEUED") {
    return <LoadingState label="AI extraction queued..." />;
  }
  if (run.status === "PROCESSING") {
    return <LoadingState label="AI extraction processing..." />;
  }
  if (run.status === "FAILED") {
    return (
      <div className="state-card error" role="alert">
        <h3>AI extraction failed</h3>
        <p>{run.error_message || "The extraction could not be completed."}</p>
      </div>
    );
  }
  return (
    <div className="extraction-fields">
      {run.fields.map((field) => (
        <FieldCard
          canEdit={canEdit}
          documentId={documentId}
          field={field}
          key={field.id}
          projectId={projectId}
          runId={run.id}
        />
      ))}
    </div>
  );
}

export function ExtractionPanel({
  projectId,
  documentId,
  canEdit = true,
}: {
  projectId: string;
  documentId: string;
  canEdit?: boolean;
}) {
  const extractions = useExtractions(projectId, documentId, true);
  const create = useCreateExtraction(projectId, documentId);
  const latest = extractions.data?.[0];
  const active = latest && ["QUEUED", "PROCESSING"].includes(latest.status);

  return (
    <section className="ai-extraction">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Structured extraction</p>
          <h2>AI Extraction</h2>
        </div>
        {canEdit && (
          <button
            disabled={Boolean(active) || create.isPending}
            onClick={() => create.mutate()}
            type="button"
          >
            {create.isPending ? "Queuing..." : "Run AI Extraction"}
          </button>
        )}
      </div>
      {create.isError && <ErrorState error={create.error} />}
      {extractions.isLoading && (
        <LoadingState label="Loading extraction history..." />
      )}
      {extractions.isError && <ErrorState error={extractions.error} />}
      {!extractions.isLoading && !latest && (
        <p className="state-card">
          No AI extraction has been run for this document.
        </p>
      )}
      {latest && (
        <div className="latest-extraction">
          <div className="run-heading">
            <div>
              <strong>Latest run</strong>
              <span>
                Prompt v{latest.prompt_version.version} · {latest.provider} /{" "}
                {latest.model}
              </span>
            </div>
            <StatusBadge status={latest.status} />
          </div>
          <dl className="extraction-summary" aria-label="Extraction summary">
            <div>
              <dt>Total fields</dt>
              <dd>{latest.fields.length}</dd>
            </div>
            <div>
              <dt>Evidence-backed</dt>
              <dd>
                {
                  latest.fields.filter((field) => field.evidence.length > 0)
                    .length
                }
              </dd>
            </div>
            <div>
              <dt>Missing</dt>
              <dd>
                {
                  latest.fields.filter(
                    (field) => field.normalized_value === null,
                  ).length
                }
              </dd>
            </div>
            <div>
              <dt>Verified</dt>
              <dd>
                {
                  latest.fields.filter(
                    (field) => field.review_status === "VERIFIED",
                  ).length
                }
              </dd>
            </div>
            <div>
              <dt>Corrected</dt>
              <dd>
                {
                  latest.fields.filter(
                    (field) => field.review_status === "CORRECTED",
                  ).length
                }
              </dd>
            </div>
            <div>
              <dt>Rejected</dt>
              <dd>
                {
                  latest.fields.filter(
                    (field) => field.review_status === "REJECTED",
                  ).length
                }
              </dd>
            </div>
            <div>
              <dt>Latency</dt>
              <dd>
                {latest.latency_ms === null
                  ? "Unknown"
                  : `${latest.latency_ms} ms`}
              </dd>
            </div>
            <div>
              <dt>Tokens</dt>
              <dd>
                {latest.input_tokens === null || latest.output_tokens === null
                  ? "Unknown"
                  : latest.input_tokens + latest.output_tokens}
              </dd>
            </div>
          </dl>
          <ExtractionResult
            canEdit={canEdit}
            documentId={documentId}
            projectId={projectId}
            run={latest}
          />
        </div>
      )}
      {extractions.data && extractions.data.length > 0 && (
        <div className="extraction-history">
          <h3>Extraction history</h3>
          <ol>
            {extractions.data.map((run, index) => (
              <li key={run.id}>
                <span>
                  Run #{extractions.data.length - index} · Prompt v
                  {run.prompt_version.version}
                </span>
                <StatusBadge status={run.status} />
                <time dateTime={run.created_at}>
                  {new Date(run.created_at).toLocaleString()}
                </time>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
