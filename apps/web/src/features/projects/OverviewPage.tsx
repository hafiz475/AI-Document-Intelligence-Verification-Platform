import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useProject, useProjectOverview } from "../hooks";

const humanEvent = (value: string) =>
  value.replaceAll(".", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const number = (value: number | null, suffix = "") =>
  value === null ? "Unknown" : `${value.toLocaleString()}${suffix}`;

export function OverviewPage() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const overview = useProjectOverview(projectId);
  const storageKey = `assureai:onboarding:${projectId}`;
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(storageKey) === "dismissed",
  );
  if (project.isLoading || overview.isLoading)
    return <LoadingState label="Building project overview…" />;
  if (project.isError) return <ErrorState error={project.error} />;
  if (overview.isError) return <ErrorState error={overview.error} />;
  if (!overview.data) return null;
  const { metrics, usage } = overview.data;
  const steps = [
    ["Create or select a project", true],
    ["Upload the first document", metrics.documents > 0],
    ["Wait for processing", metrics.documents_ready > 0],
    ["Run structured extraction", metrics.extraction_runs > 0],
    ["Review extracted fields", metrics.verified_fields > 0],
    ["Ask a grounded question", metrics.rag_questions > 0],
    ["Open the quality dashboard", false],
  ] as const;
  const cards = [
    ["Documents", metrics.documents],
    ["Ready", metrics.documents_ready],
    ["Failed", metrics.documents_failed],
    ["Extraction runs", metrics.extraction_runs],
    ["Awaiting review", metrics.fields_awaiting_review],
    ["Verified fields", metrics.verified_fields],
    ["Questions", metrics.rag_questions],
    ["Supported answers", metrics.supported_answers],
    ["Insufficient evidence", metrics.insufficient_evidence_answers],
  ] as const;
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Project overview</p>
          <h1>{project.data?.name}</h1>
          <p>
            {project.data?.description ||
              "Evidence-backed document intelligence workspace."}
          </p>
        </div>
        <Link className="button" to={`/app/projects/${projectId}/documents`}>
          Open documents
        </Link>
      </div>

      {!dismissed && (
        <section
          className="onboarding-card"
          aria-labelledby="onboarding-heading"
        >
          <div>
            <p className="eyebrow">First-run guide</p>
            <h2 id="onboarding-heading">Your path to a verified answer</h2>
          </div>
          <ol>
            {steps.map(([label, complete], index) => (
              <li className={complete ? "complete" : ""} key={label}>
                <span>{complete ? "✓" : index + 1}</span>
                {label}
              </li>
            ))}
          </ol>
          <div className="onboarding-actions">
            <Link to={`/app/projects/${projectId}/documents`}>
              Continue workflow
            </Link>
            <button
              className="link-button"
              onClick={() => {
                localStorage.setItem(storageKey, "dismissed");
                setDismissed(true);
              }}
              type="button"
            >
              Dismiss guide
            </button>
          </div>
        </section>
      )}

      <section aria-labelledby="metrics-heading">
        <div className="section-heading">
          <div>
            <h2 id="metrics-heading">Workspace health</h2>
            <p>Derived from persisted project records.</p>
          </div>
        </div>
        <div className="overview-grid">
          {cards.map(([label, value]) => (
            <article className="overview-card" key={label}>
              <strong>{value}</strong>
              <span>{label}</span>
            </article>
          ))}
          <article className="overview-card featured">
            <strong>
              {metrics.evaluation_pass_rate === null
                ? "Unknown"
                : `${(metrics.evaluation_pass_rate * 100).toFixed(1)}%`}
            </strong>
            <span>Evaluation pass rate</span>
          </article>
        </div>
      </section>

      <div className="dashboard-columns">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>AI usage</h2>
              <p>Unknown values stay unknown.</p>
            </div>
          </div>
          <dl className="usage-list">
            <div>
              <dt>Extraction tokens</dt>
              <dd>{number(usage.extraction_tokens)}</dd>
            </div>
            <div>
              <dt>RAG tokens</dt>
              <dd>{number(usage.rag_tokens)}</dd>
            </div>
            <div>
              <dt>Evaluation tokens</dt>
              <dd>{number(usage.evaluation_tokens)}</dd>
            </div>
            <div>
              <dt>Total known tokens</dt>
              <dd>{number(usage.total_tokens)}</dd>
            </div>
            <div>
              <dt>Average extraction latency</dt>
              <dd>{number(usage.average_provider_latency_ms, " ms")}</dd>
            </div>
            <div>
              <dt>Average retrieval latency</dt>
              <dd>{number(metrics.average_retrieval_latency_ms, " ms")}</dd>
            </div>
            <div>
              <dt>Average RAG latency</dt>
              <dd>{number(metrics.average_rag_latency_ms, " ms")}</dd>
            </div>
          </dl>
          {overview.data.provider_usage.length > 0 && (
            <div className="provider-list">
              {overview.data.provider_usage.map((item) => (
                <p key={`${item.operation}-${item.provider}-${item.model}`}>
                  <strong>{item.operation}</strong>
                  <span>
                    {item.provider} / {item.model}
                  </span>
                  <b>{item.requests}</b>
                </p>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Recent activity</h2>
              <p>Latest durable audit events.</p>
            </div>
          </div>
          {overview.data.recent_activity.length ? (
            <ol className="activity-list">
              {overview.data.recent_activity.map((item) => (
                <li key={item.id}>
                  <span className="activity-dot" aria-hidden="true" />
                  <div>
                    <strong>{humanEvent(item.event_type)}</strong>
                    <p>
                      {item.actor ?? "Background worker"} ·{" "}
                      <time dateTime={item.created_at}>
                        {new Date(item.created_at).toLocaleString()}
                      </time>
                    </p>
                  </div>
                  {item.event_type.includes("failed") && (
                    <StatusBadge status="FAILED" />
                  )}
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState
              title="No activity yet"
              detail="Upload a technical document to begin extracting and verifying information."
            />
          )}
        </section>
      </div>
    </section>
  );
}
