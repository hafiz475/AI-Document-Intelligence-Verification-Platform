import { Link, useParams } from "react-router-dom";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useDocumentReport } from "../hooks";
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
export function DocumentReportPage() {
  const { projectId = "", documentId = "" } = useParams();
  const report = useDocumentReport(projectId, documentId);
  if (report.isLoading)
    return <LoadingState label="Preparing authenticated review report…" />;
  if (report.isError) return <ErrorState error={report.error} />;
  if (!report.data) return null;
  const run = report.data.latest_extraction;
  const counts =
    run?.fields.reduce(
      (x, f) => ({ ...x, [f.review_status]: (x[f.review_status] ?? 0) + 1 }),
      {} as Record<string, number>,
    ) ?? {};
  return (
    <article className="report-page">
      <header className="report-header">
        <div>
          <p className="eyebrow">Authenticated review report</p>
          <h1>{report.data.document.filename}</h1>
          <p>
            Generated from current project-scoped records ·{" "}
            {new Date().toLocaleString()}
          </p>
        </div>
        <div className="report-actions">
          <Link
            className="button secondary"
            to={`/app/projects/${projectId}/documents/${documentId}`}
          >
            Back to workspace
          </Link>
          <button onClick={() => window.print()}>Print report</button>
        </div>
      </header>
      <dl className="metadata-grid">
        <div>
          <dt>Document status</dt>
          <dd>
            <StatusBadge status={report.data.document.status} />
          </dd>
        </div>
        <div>
          <dt>Uploaded</dt>
          <dd>{new Date(report.data.document.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Extraction</dt>
          <dd>{run?.status ?? "Not run"}</dd>
        </div>
        <div>
          <dt>Verified</dt>
          <dd>{counts.VERIFIED ?? 0}</dd>
        </div>
        <div>
          <dt>Corrected</dt>
          <dd>{counts.CORRECTED ?? 0}</dd>
        </div>
        <div>
          <dt>Rejected</dt>
          <dd>{counts.REJECTED ?? 0}</dd>
        </div>
      </dl>
      {run ? (
        <>
          <section className="report-section">
            <h2>Extraction provenance</h2>
            <p>
              {run.provider} / {run.model} · prompt v
              {run.prompt_version.version} · {run.latency_ms ?? "Unknown"} ms ·{" "}
              {run.input_tokens === null || run.output_tokens === null
                ? "Token usage unknown"
                : `${run.input_tokens + run.output_tokens} tokens`}
            </p>
          </section>
          <section className="report-section">
            <h2>Reviewed fields and evidence</h2>
            {run.fields.map((field) => (
              <article className="report-field" key={field.id}>
                <header>
                  <div>
                    <small>{field.field_name.replaceAll("_", " ")}</small>
                    <strong>
                      {show(field.corrected_value ?? field.normalized_value)}
                    </strong>
                  </div>
                  <StatusBadge status={field.review_status} />
                </header>
                {field.review_status === "CORRECTED" && (
                  <p>
                    <b>Original AI value:</b> {show(field.normalized_value)}
                    <br />
                    <b>Reason:</b> {field.review_reason}
                  </p>
                )}
                {field.evidence.map((e) => (
                  <blockquote key={e.id}>
                    {e.page_number ? `Page ${e.page_number}: ` : ""}
                    {e.quote}
                  </blockquote>
                ))}
              </article>
            ))}
          </section>
        </>
      ) : (
        <EmptyState
          title="No extraction report yet"
          detail="Run structured extraction before producing a field-level review report."
        />
      )}
      <section className="report-section">
        <h2>Grounded Q&A summary</h2>
        <p>
          {report.data.question_count} questions ·{" "}
          {report.data.supported_answer_count} supported answers ·{" "}
          {report.data.insufficient_answer_count} insufficient-evidence answers
        </p>
      </section>
    </article>
  );
}
