import { Link, useParams } from "react-router-dom";

import { FileUpload } from "../../components/FileUpload";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import { useDocuments, useProject, useUploadDocument } from "../hooks";
import { RetrievalEvaluationPanel } from "../RetrievalEvaluationPanel";
import { SemanticSearchPanel } from "../SemanticSearchPanel";

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const documents = useDocuments(projectId);
  const upload = useUploadDocument(projectId);

  if (project.isLoading) return <LoadingState label="Loading project…" />;
  if (project.isError) return <ErrorState error={project.error} />;

  return (
    <section>
      <Link className="back-link" to="/">
        ← Projects
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Project</p>
          <h1>{project.data?.name}</h1>
          <p>{project.data?.description || "No description provided."}</p>
        </div>
        <div className="metric">
          <strong>{project.data?.document_count}</strong>
          <span>documents</span>
        </div>
      </div>
      <FileUpload
        busy={upload.isPending}
        onUpload={(file) => upload.mutate(file)}
      />
      {upload.isError && <ErrorState error={upload.error} />}
      {upload.isSuccess && (
        <p className="notice" role="status">
          Upload accepted. Processing has been queued.
        </p>
      )}

      <SemanticSearchPanel projectId={projectId} />

      <div className="section-heading">
        <h2>Documents</h2>
        <p>Processing status refreshes automatically.</p>
      </div>
      {documents.isLoading && <LoadingState label="Loading documents…" />}
      {documents.isError && <ErrorState error={documents.error} />}
      {documents.data?.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {documents.data.map((document) => (
                <tr key={document.id}>
                  <td>{document.filename}</td>
                  <td>{document.mime_type.split("/").at(-1)}</td>
                  <td>{formatBytes(document.file_size)}</td>
                  <td>
                    <StatusBadge status={document.status} />
                  </td>
                  <td>{new Date(document.created_at).toLocaleString()}</td>
                  <td>
                    <Link
                      to={`/projects/${projectId}/documents/${document.id}`}
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !documents.isLoading && (
          <EmptyState
            title="No documents"
            detail="Upload a PDF, DOCX, or TXT file to begin processing."
          />
        )
      )}
      <RetrievalEvaluationPanel projectId={projectId} />
    </section>
  );
}
