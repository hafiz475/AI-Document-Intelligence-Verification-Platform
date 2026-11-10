import { ErrorState, LoadingState, StatusBadge } from "../../components/States";
import { useCreateEmbeddingRun, useEmbeddingRuns } from "../hooks";

export function EmbeddingPanel({
  projectId,
  documentId,
}: {
  projectId: string;
  documentId: string;
}) {
  const runs = useEmbeddingRuns(projectId, documentId, true);
  const create = useCreateEmbeddingRun(projectId, documentId);
  const latest = runs.data?.[0];
  const active = latest && ["QUEUED", "PROCESSING"].includes(latest.status);
  const displayStatus =
    latest?.status === "COMPLETED" ? "READY" : latest?.status;

  return (
    <section className="embedding-panel" aria-labelledby="embeddings-heading">
      <div className="section-heading">
        <div>
          <h2 id="embeddings-heading">Embeddings</h2>
          <p>Vector generation is explicit and does not alter source chunks.</p>
        </div>
        <button
          className="button"
          disabled={Boolean(active) || create.isPending}
          onClick={() => create.mutate()}
          type="button"
        >
          {latest?.status === "COMPLETED"
            ? "Re-generate Embeddings"
            : "Generate Embeddings"}
        </button>
      </div>
      {runs.isLoading && <LoadingState label="Loading embedding status…" />}
      {runs.isError && <ErrorState error={runs.error} />}
      {create.isError && <ErrorState error={create.error} />}
      {!runs.isLoading && !latest && (
        <div className="embedding-summary">
          <StatusBadge status="NOT_GENERATED" />
          <p>No vectors have been generated for this document.</p>
        </div>
      )}
      {latest && (
        <div className="embedding-summary">
          <StatusBadge status={displayStatus ?? latest.status} />
          <dl>
            <div>
              <dt>Provider / model</dt>
              <dd>
                {latest.provider} / {latest.model}
              </dd>
            </div>
            <div>
              <dt>Chunks embedded</dt>
              <dd>
                {latest.chunks_embedded} / {latest.chunks_total}
              </dd>
            </div>
            <div>
              <dt>Dimensions</dt>
              <dd>{latest.dimensions}</dd>
            </div>
            <div>
              <dt>Last generated</dt>
              <dd>
                {latest.completed_at
                  ? new Date(latest.completed_at).toLocaleString()
                  : "Pending"}
              </dd>
            </div>
          </dl>
          {latest.status === "FAILED" && (
            <p className="error-text">
              {latest.error_message || "Embedding generation failed."}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
