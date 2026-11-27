import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { FileUpload } from "../../components/FileUpload";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useDocumentIndex, useProject, useUploadDocument } from "../hooks";

const PAGE_SIZE = 10;
const formatBytes = (value: number) =>
  value < 1024
    ? `${value} B`
    : value < 1048576
      ? `${(value / 1024).toFixed(1)} KB`
      : `${(value / 1048576).toFixed(1)} MB`;

export function DocumentsPage() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const upload = useUploadDocument(projectId);
  const [status, setStatus] = useState("");
  const [mimeType, setMimeType] = useState("");
  const [offset, setOffset] = useState(0);
  const documents = useDocumentIndex(projectId, {
    status,
    mimeType,
    limit: PAGE_SIZE,
    offset,
  });
  const canEdit = project.data?.current_role !== "VIEWER";
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Document intelligence</p>
          <h1>Documents</h1>
          <p>
            Upload, process, and open source material for extraction and
            evidence review.
          </p>
        </div>
      </div>
      {canEdit ? (
        <FileUpload
          busy={upload.isPending}
          onUpload={(file) => upload.mutate(file)}
        />
      ) : (
        <p className="notice">Viewer access is read-only.</p>
      )}
      {upload.isError && <ErrorState error={upload.error} />}
      {upload.isSuccess && (
        <p className="notice" role="status">
          Upload accepted. Processing has been queued.
        </p>
      )}
      <div className="filter-bar" aria-label="Document filters">
        <label>
          Status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            {["UPLOADED", "QUEUED", "PROCESSING", "READY", "FAILED"].map(
              (x) => (
                <option key={x}>{x}</option>
              ),
            )}
          </select>
        </label>
        <label>
          File type
          <select
            value={mimeType}
            onChange={(e) => {
              setMimeType(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All types</option>
            <option value="application/pdf">PDF</option>
            <option value="application/vnd.openxmlformats-officedocument.wordprocessingml.document">
              DOCX
            </option>
            <option value="text/plain">TXT</option>
          </select>
        </label>
      </div>
      {documents.isLoading && <LoadingState label="Loading documents…" />}
      {documents.isError && <ErrorState error={documents.error} />}
      {documents.data?.items.length ? (
        <>
          <div className="document-grid">
            {documents.data.items.map((doc) => (
              <article className="document-card" key={doc.id}>
                <div className="document-icon" aria-hidden="true">
                  {doc.mime_type === "application/pdf"
                    ? "PDF"
                    : doc.mime_type === "text/plain"
                      ? "TXT"
                      : "DOCX"}
                </div>
                <div>
                  <h2>{doc.filename}</h2>
                  <p>
                    {formatBytes(doc.file_size)} · uploaded{" "}
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                  {doc.processing_error && (
                    <p className="field-error">{doc.processing_error}</p>
                  )}
                </div>
                <StatusBadge status={doc.status} />
                <Link
                  className="button secondary"
                  to={`/app/projects/${projectId}/documents/${doc.id}`}
                >
                  Open workspace
                </Link>
              </article>
            ))}
          </div>
          <div className="pagination" aria-label="Document pages">
            <button
              className="button secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <span>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, documents.data.total)}{" "}
              of {documents.data.total}
            </span>
            <button
              className="button secondary"
              disabled={offset + PAGE_SIZE >= documents.data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      ) : (
        !documents.isLoading && (
          <EmptyState
            title="No documents yet"
            detail="Upload a technical document to begin extracting and verifying information."
          />
        )
      )}
    </section>
  );
}
