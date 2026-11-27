import { useState } from "react";
import { useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useAuditIndex } from "../hooks";

const PAGE_SIZE = 15;
const label = (value: string) =>
  value.replaceAll(".", " ").replace(/\b\w/g, (x) => x.toUpperCase());
export function AuditPage() {
  const { projectId = "" } = useParams();
  const [eventType, setEventType] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [offset, setOffset] = useState(0);
  const audit = useAuditIndex(projectId, {
    eventType,
    createdFrom: createdFrom || undefined,
    createdTo: createdTo ? `${createdTo}T23:59:59Z` : undefined,
    limit: PAGE_SIZE,
    offset,
  });
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Accountability</p>
          <h1>Audit</h1>
          <p>
            Project activity described for people, with request and trace
            references available for operations.
          </p>
        </div>
      </div>
      <div className="filter-bar">
        <label>
          Event
          <input
            placeholder="field.verified"
            value={eventType}
            onChange={(e) => {
              setEventType(e.target.value);
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
      {audit.isLoading && <LoadingState label="Loading audit trail…" />}
      {audit.isError && <ErrorState error={audit.error} />}{" "}
      {audit.data?.items.length ? (
        <div className="audit-list">
          {audit.data.items.map((item) => (
            <article key={item.id}>
              <div className="audit-symbol" aria-hidden="true">
                {item.event_type.startsWith("field")
                  ? "✓"
                  : item.event_type.startsWith("document")
                    ? "D"
                    : "•"}
              </div>
              <div>
                <h2>{label(item.event_type)}</h2>
                <p>
                  {item.actor ?? "Background worker"}
                  {item.target_type ? ` · ${item.target_type}` : ""}
                </p>
                <time dateTime={item.created_at}>
                  {new Date(item.created_at).toLocaleString()}
                </time>
                <details>
                  <summary>Operational references</summary>
                  <dl>
                    <div>
                      <dt>Request ID</dt>
                      <dd>{item.request_id ?? "Not applicable"}</dd>
                    </div>
                    <div>
                      <dt>Trace ID</dt>
                      <dd>{item.trace_id ?? "Not available"}</dd>
                    </div>
                  </dl>
                </details>
              </div>
            </article>
          ))}
        </div>
      ) : (
        !audit.isLoading && (
          <EmptyState
            title="No audit events"
            detail="Significant project actions will appear here without exposing document content or secrets."
          />
        )
      )}
      {audit.data && audit.data.total > PAGE_SIZE && (
        <div className="pagination">
          <button
            className="button secondary"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, audit.data.total)} of{" "}
            {audit.data.total}
          </span>
          <button
            className="button secondary"
            disabled={offset + PAGE_SIZE >= audit.data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
}
