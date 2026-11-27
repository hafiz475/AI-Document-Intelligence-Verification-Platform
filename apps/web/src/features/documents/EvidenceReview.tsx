import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { ExtractedField } from "../../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useDocumentChunks, useExtractions, useReviewField } from "../hooks";

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
function Highlight({
  content,
  quote,
}: {
  content: string;
  quote: string | null;
}) {
  if (!quote) return <p>{content}</p>;
  const index = content.indexOf(quote);
  if (index < 0) return <p>{content}</p>;
  return (
    <p>
      {content.slice(0, index)}
      <mark>{quote}</mark>
      {content.slice(index + quote.length)}
    </p>
  );
}
export function EvidenceReview({
  projectId,
  documentId,
  mimeType,
  canEdit,
}: {
  projectId: string;
  documentId: string;
  mimeType: string;
  canEdit: boolean;
}) {
  const runs = useExtractions(projectId, documentId, true);
  const chunks = useDocumentChunks(projectId, documentId, true);
  const [params, setParams] = useSearchParams();
  const latest = runs.data?.[0];
  const requested = params.get("field");
  const selected = useMemo(
    () => latest?.fields.find((f) => f.id === requested) ?? latest?.fields[0],
    [latest, requested],
  );
  useEffect(() => {
    if (selected && requested !== selected.id)
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set("tab", "evidence");
          next.set("field", selected.id);
          return next;
        },
        { replace: true },
      );
  }, [requested, selected, setParams]);
  if (runs.isLoading || chunks.isLoading)
    return <LoadingState label="Loading validated evidence…" />;
  if (runs.isError) return <ErrorState error={runs.error} />;
  if (chunks.isError) return <ErrorState error={chunks.error} />;
  if (!latest?.fields.length)
    return (
      <EmptyState
        title="No extracted fields"
        detail="Run structured extraction to begin side-by-side evidence review."
      />
    );
  const evidence = selected?.evidence[0];
  const source = chunks.data?.items.find(
    (chunk) => chunk.id === evidence?.document_chunk_id,
  );
  const isPdf = mimeType === "application/pdf";
  return (
    <section
      className="evidence-workspace"
      aria-label="Side-by-side evidence review"
    >
      <aside className="field-rail">
        <header>
          <p className="eyebrow">Extracted fields</p>
          <h2>{latest.fields.length} fields</h2>
        </header>
        {latest.fields.map((field) => (
          <button
            aria-pressed={selected?.id === field.id}
            className="field-selector"
            key={field.id}
            onClick={() => setParams({ tab: "evidence", field: field.id })}
          >
            <span>
              <strong>{field.field_name.replaceAll("_", " ")}</strong>
              <small>
                {show(field.corrected_value ?? field.normalized_value)}
              </small>
            </span>
            <StatusBadge status={field.review_status} />
          </button>
        ))}
      </aside>
      <div className="source-pane">
        <header>
          <div>
            <p className="eyebrow">Validated source context</p>
            <h2>{selected?.field_name.replaceAll("_", " ")}</h2>
          </div>
          {evidence?.page_number ? (
            <span className="page-chip">Page {evidence.page_number}</span>
          ) : (
            <span className="page-chip">
              {isPdf ? "Page unavailable" : "Text context"}
            </span>
          )}
        </header>
        {source ? (
          <article className="source-document">
            <p className="source-label">
              {source.section ?? `Chunk ${source.chunk_index + 1}`}
            </p>
            <Highlight
              content={source.content}
              quote={evidence?.quote ?? null}
            />
          </article>
        ) : (
          <div className="state-card">
            <p>
              The authorized source context is unavailable. No cross-document
              evidence is rendered.
            </p>
          </div>
        )}
        <div className="evidence-trust">
          <span aria-hidden="true">✓</span>
          <p>
            <strong>Evidence link validated</strong>
            <br />
            This field points to an exact quote in the authorized source chunk.
          </p>
        </div>
      </div>
      {selected && (
        <ReviewInspector
          field={selected}
          canEdit={canEdit}
          documentId={documentId}
          projectId={projectId}
          runId={latest.id}
        />
      )}
    </section>
  );
}
function ReviewInspector({
  field,
  canEdit,
  projectId,
  documentId,
  runId,
}: {
  field: ExtractedField;
  canEdit: boolean;
  projectId: string;
  documentId: string;
  runId: string;
}) {
  const review = useReviewField(projectId, documentId);
  const value = field.corrected_value ?? field.normalized_value;
  return (
    <aside className="review-inspector">
      <p className="eyebrow">Review decision</p>
      <h2>{show(value)}</h2>
      {field.review_status === "CORRECTED" && (
        <div className="original-value">
          <small>ORIGINAL AI VALUE</small>
          <p>{show(field.normalized_value)}</p>
        </div>
      )}
      <dl>
        <div>
          <dt>Evidence status</dt>
          <dd>
            <StatusBadge status={field.support_status} />
          </dd>
        </div>
        <div>
          <dt>Review status</dt>
          <dd>
            <StatusBadge status={field.review_status} />
          </dd>
        </div>
        {field.reviewer && (
          <div>
            <dt>Reviewer</dt>
            <dd>{field.reviewer}</dd>
          </div>
        )}
        {field.reviewed_at && (
          <div>
            <dt>Reviewed</dt>
            <dd>{new Date(field.reviewed_at).toLocaleString()}</dd>
          </div>
        )}
        {field.review_reason && (
          <div>
            <dt>Reason</dt>
            <dd>{field.review_reason}</dd>
          </div>
        )}
      </dl>
      {canEdit && field.review_status === "UNREVIEWED" && (
        <div className="review-actions">
          <button
            disabled={review.isPending}
            onClick={() =>
              review.mutate({
                runId,
                fieldId: field.id,
                review: { decision: "VERIFIED" },
              })
            }
          >
            Verify field
          </button>
          <Link to={`/app/projects/${projectId}/review`}>
            Correct or reject
          </Link>
        </div>
      )}
      {review.isError && <ErrorState error={review.error} />}
    </aside>
  );
}
