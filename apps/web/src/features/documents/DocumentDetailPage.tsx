import { Link, useParams, useSearchParams } from "react-router-dom";

import type { DocumentRecord, ExtractionRun } from "../../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import {
  useDocument,
  useDocumentChunks,
  useEmbeddingRuns,
  useExtractions,
  useProject,
} from "../hooks";
import { RagQuestionPanel } from "../RagQuestionPanel";
import { EmbeddingPanel } from "./EmbeddingPanel";
import { EvidenceReview } from "./EvidenceReview";
import { ExtractionPanel } from "./ExtractionPanel";

const tabs = [
  "overview",
  "extraction",
  "evidence",
  "ask",
  "chunks",
  "history",
] as const;
export function DocumentDetailPage() {
  const { projectId = "", documentId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const project = useProject(projectId);
  const document = useDocument(projectId, documentId);
  const tab = tabs.includes(params.get("tab") as (typeof tabs)[number])
    ? (params.get("tab") as (typeof tabs)[number])
    : "overview";
  const chunks = useDocumentChunks(
    projectId,
    documentId,
    document.data?.status === "READY" && ["chunks", "evidence"].includes(tab),
  );
  const extractions = useExtractions(
    projectId,
    documentId,
    document.data?.status === "READY" && tab === "history",
  );
  if (project.isLoading || document.isLoading)
    return <LoadingState label="Loading document workspace…" />;
  if (project.isError) return <ErrorState error={project.error} />;
  if (document.isError) return <ErrorState error={document.error} />;
  if (!document.data) return null;
  const item = document.data;
  const canEdit = project.data?.current_role !== "VIEWER";
  return (
    <section>
      <Link className="back-link" to={`/app/projects/${projectId}/documents`}>
        ← Documents
      </Link>
      <div className="page-heading document-heading">
        <div>
          <p className="eyebrow">Document workspace</p>
          <h1>{item.filename}</h1>
          <p>
            {item.mime_type} · uploaded{" "}
            {new Date(item.created_at).toLocaleString()}
          </p>
        </div>
        <div className="heading-actions">
          <StatusBadge status={item.status} />
          <Link
            className="button secondary"
            to={`/app/projects/${projectId}/documents/${documentId}/report`}
          >
            Review report
          </Link>
        </div>
      </div>
      <nav className="tab-list" aria-label="Document sections">
        {tabs.map((name) => (
          <button
            aria-current={tab === name ? "page" : undefined}
            className={tab === name ? "active" : ""}
            key={name}
            onClick={() => setParams({ tab: name })}
          >
            {name.charAt(0).toUpperCase() + name.slice(1)}
          </button>
        ))}
      </nav>
      {item.status !== "READY" ? (
        <ProcessingState status={item.status} error={item.processing_error} />
      ) : (
        <>
          {!canEdit && <p className="notice">Viewer access is read-only.</p>}
          {tab === "overview" && (
            <DocumentOverview
              item={item}
              canEdit={canEdit}
              documentId={documentId}
              projectId={projectId}
            />
          )}{" "}
          {tab === "extraction" && (
            <ExtractionPanel
              canEdit={canEdit}
              documentId={documentId}
              projectId={projectId}
            />
          )}{" "}
          {tab === "evidence" && (
            <EvidenceReview
              canEdit={canEdit}
              documentId={documentId}
              mimeType={item.mime_type}
              projectId={projectId}
            />
          )}{" "}
          {tab === "ask" && (
            <RagQuestionPanel documentId={documentId} projectId={projectId} />
          )}{" "}
          {tab === "chunks" && <ChunksView chunks={chunks} />}{" "}
          {tab === "history" && <HistoryView runs={extractions.data ?? []} />}
        </>
      )}
    </section>
  );
}
function ProcessingState({
  status,
  error,
}: {
  status: string;
  error: string | null;
}) {
  if (status === "FAILED")
    return (
      <div className="state-card error">
        <h2>Processing failed</h2>
        <p>{error || "The document could not be processed."}</p>
        <p>
          Check the file type and content, then upload a corrected source
          document.
        </p>
      </div>
    );
  return (
    <div className="processing-card">
      <h2>Processing document</h2>
      <div className="timeline">
        {[
          "Uploaded",
          "Queued",
          "Processing",
          "Chunked",
          "Embedded",
          "Ready",
        ].map((step, index) => (
          <div
            className={
              index <= (status === "UPLOADED" ? 0 : status === "QUEUED" ? 1 : 2)
                ? "active"
                : ""
            }
            key={step}
          >
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </div>
      <LoadingState
        label={
          status === "PROCESSING"
            ? "Extracting and chunking document…"
            : "Waiting for a worker…"
        }
      />
    </div>
  );
}
function DocumentOverview({
  item,
  projectId,
  documentId,
  canEdit,
}: {
  item: DocumentRecord;
  projectId: string;
  documentId: string;
  canEdit: boolean;
}) {
  const embeddings = useEmbeddingRuns(projectId, documentId, true);
  const embedded =
    embeddings.data?.some((run) => run.status === "COMPLETED") ?? false;
  return (
    <div>
      <dl className="metadata-grid">
        <div>
          <dt>Type</dt>
          <dd>{item.mime_type}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{item.file_size.toLocaleString()} bytes</dd>
        </div>
        <div>
          <dt>Pages</dt>
          <dd>{item.page_count ?? "Not available"}</dd>
        </div>
        <div>
          <dt>Characters</dt>
          <dd>{item.character_count?.toLocaleString() ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>Processed</dt>
          <dd>
            {item.processed_at
              ? new Date(item.processed_at).toLocaleString()
              : "Pending"}
          </dd>
        </div>
      </dl>
      <section className="processing-card">
        <h2>Document lifecycle</h2>
        <div className="timeline">
          {[
            "Uploaded",
            "Queued",
            "Processing",
            "Chunked",
            "Embedded",
            "Ready",
          ].map((step, index) => (
            <div
              className={step !== "Embedded" || embedded ? "active" : ""}
              key={step}
            >
              <span>{step !== "Embedded" || embedded ? "✓" : index + 1}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </section>
      <EmbeddingPanel
        canEdit={canEdit}
        documentId={documentId}
        projectId={projectId}
      />
    </div>
  );
}
function ChunksView({
  chunks,
}: {
  chunks: ReturnType<typeof useDocumentChunks>;
}) {
  if (chunks.isLoading) return <LoadingState label="Loading source chunks…" />;
  if (chunks.isError) return <ErrorState error={chunks.error} />;
  return chunks.data?.items.length ? (
    <div className="chunks">
      {chunks.data.items.map((chunk) => (
        <article className="chunk-card" id={`chunk-${chunk.id}`} key={chunk.id}>
          <header>
            <strong>Chunk {chunk.chunk_index + 1}</strong>
            <span>
              {chunk.page_number
                ? `Page ${chunk.page_number}`
                : (chunk.section ?? "Text context")}
            </span>
          </header>
          <p>{chunk.content}</p>
        </article>
      ))}
    </div>
  ) : (
    <EmptyState
      title="No chunks"
      detail="No extracted source chunks were returned."
    />
  );
}
function HistoryView({ runs }: { runs: ExtractionRun[] }) {
  return runs.length ? (
    <div className="timeline-list">
      {runs.map((run) => (
        <article key={run.id}>
          <StatusBadge status={run.status} />
          <div>
            <h2>Extraction · prompt v{run.prompt_version.version}</h2>
            <p>
              {run.provider} / {run.model} ·{" "}
              {new Date(run.created_at).toLocaleString()}
            </p>
          </div>
        </article>
      ))}
    </div>
  ) : (
    <EmptyState
      title="No processing history"
      detail="Extraction and review activity will appear after the first run."
    />
  );
}
