import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useRetrievalEvaluations } from "./hooks";

export function RetrievalEvaluationPanel({ projectId }: { projectId: string }) {
  const evaluations = useRetrievalEvaluations(projectId);
  const latest = evaluations.data?.[0];

  return (
    <section
      className="retrieval-evaluation"
      aria-labelledby="retrieval-evaluation-heading"
    >
      <div className="section-heading">
        <div>
          <h2 id="retrieval-evaluation-heading">Retrieval evaluation</h2>
          <p>Deterministic retrieval metrics from stored ranked results.</p>
        </div>
      </div>
      {evaluations.isLoading && (
        <LoadingState label="Loading retrieval metrics…" />
      )}
      {evaluations.isError && <ErrorState error={evaluations.error} />}
      {!evaluations.isLoading && !latest && (
        <EmptyState
          title="No evaluation runs"
          detail="Run the checked-in retrieval cases through the API to populate metrics."
        />
      )}
      {latest && (
        <>
          <div className="evaluation-metrics">
            <div>
              <strong>{(latest.hit_rate * 100).toFixed(1)}%</strong>
              <span>Hit@{latest.top_k}</span>
            </div>
            <div>
              <strong>{latest.mean_reciprocal_rank.toFixed(3)}</strong>
              <span>MRR</span>
            </div>
            <div>
              <strong>{latest.recall_at_k.toFixed(3)}</strong>
              <span>Recall@{latest.top_k}</span>
            </div>
          </div>
          <p>
            {latest.embedding_provider}/{latest.embedding_model} ·{" "}
            {latest.case_count} cases
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Expected</th>
                  <th>Retrieved</th>
                  <th>First rank</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {latest.case_results.map((item) => (
                  <tr key={item.id}>
                    <td>{item.query}</td>
                    <td>{item.expected_chunk_ids.join(", ")}</td>
                    <td>{item.retrieved_chunk_ids.join(", ")}</td>
                    <td>{item.first_relevant_rank ?? "—"}</td>
                    <td>{item.hit ? "PASS" : "FAIL"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
