import { Link, useParams } from "react-router-dom";

import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useDocument, useDocumentChunks } from "../hooks";

export function DocumentDetailPage() {
  const { projectId = "", documentId = "" } = useParams();
  const document = useDocument(projectId, documentId);
  const chunks = useDocumentChunks(
    projectId,
    documentId,
    document.data?.status === "READY",
  );

  if (document.isLoading) return <LoadingState label="Loading document…" />;
  if (document.isError) return <ErrorState error={document.error} />;
  if (!document.data) return null;
  const item = document.data;

  return (
    <section>
      <Link className="back-link" to={`/projects/${projectId}`}>
        ← Project
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Document</p>
          <h1>{item.filename}</h1>
          <p>Uploaded {new Date(item.created_at).toLocaleString()}</p>
        </div>
        <StatusBadge status={item.status} />
      </div>
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
          <dd>{item.character_count?.toLocaleString() ?? "Pending"}</dd>
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
      {["UPLOADED", "QUEUED", "PROCESSING"].includes(item.status) && (
        <LoadingState
          label={
            item.status === "PROCESSING"
              ? "Extracting and chunking document…"
              : "Waiting for a worker…"
          }
        />
      )}
      {item.status === "FAILED" && (
        <div className="state-card error">
          <h2>Processing failed</h2>
          <p>
            {item.processing_error || "The document could not be processed."}
          </p>
        </div>
      )}
      {item.status === "READY" && (
        <div>
          <div className="section-heading">
            <h2>Extracted chunks</h2>
            <p>{chunks.data?.total ?? 0} deterministic text chunks</p>
          </div>
          {chunks.isLoading && <LoadingState label="Loading extracted text…" />}
          {chunks.isError && <ErrorState error={chunks.error} />}
          {chunks.data?.items.length ? (
            <div className="chunks">
              {chunks.data.items.map((chunk) => (
                <article className="chunk-card" key={chunk.id}>
                  <header>
                    <strong>Chunk {chunk.chunk_index + 1}</strong>
                    <span>
                      {chunk.page_number
                        ? `Page ${chunk.page_number}`
                        : chunk.section}
                    </span>
                  </header>
                  <p>{chunk.content}</p>
                </article>
              ))}
            </div>
          ) : (
            !chunks.isLoading && (
              <EmptyState
                title="No chunks"
                detail="No extracted text chunks were returned."
              />
            )
          )}
        </div>
      )}
    </section>
  );
}
