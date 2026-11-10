import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState } from "../components/States";
import { useSemanticSearch } from "./hooks";

export function SemanticSearchPanel({
  projectId,
  documentId,
}: {
  projectId: string;
  documentId?: string;
}) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const search = useSemanticSearch(projectId, documentId);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized) search.mutate({ query: normalized, topK });
  }

  return (
    <section
      className="semantic-search"
      aria-labelledby={documentId ? "document-search" : "project-search"}
    >
      <div className="section-heading">
        <div>
          <h2 id={documentId ? "document-search" : "project-search"}>
            {documentId ? "Search this document" : "Semantic evidence search"}
          </h2>
          <p>Search only—no generated answer or LLM interpretation.</p>
        </div>
      </div>
      <form className="search-form" onSubmit={submit}>
        <label>
          <span className="sr-only">Evidence query</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask what evidence exists in these documents…"
            value={query}
          />
        </label>
        <label>
          <span>Top results</span>
          <input
            max={20}
            min={1}
            onChange={(event) => setTopK(Number(event.target.value))}
            type="number"
            value={topK}
          />
        </label>
        <button
          className="button"
          disabled={!query.trim() || search.isPending}
          type="submit"
        >
          {search.isPending ? "Searching…" : "Search evidence"}
        </button>
      </form>
      {search.isError && <ErrorState error={search.error} />}
      {search.data && (
        <div className="search-results" aria-live="polite">
          <p className="search-metadata">
            Cosine similarity · {search.data.provider}/{search.data.model} ·{" "}
            {search.data.search_latency_ms} ms
          </p>
          {search.data.results.length ? (
            <ol>
              {search.data.results.map((result) => (
                <li key={result.chunk_id}>
                  <header>
                    <strong>
                      {result.rank}. {result.document_name}
                    </strong>
                    <span>Score {result.similarity_score.toFixed(4)}</span>
                  </header>
                  <p>
                    {result.page_number
                      ? "Page " + result.page_number
                      : "Chunk " + (result.chunk_index + 1)}
                  </p>
                  <blockquote>{result.content}</blockquote>
                  <Link
                    to={
                      "/projects/" +
                      projectId +
                      "/documents/" +
                      result.document_id +
                      "#chunk-" +
                      result.chunk_id
                    }
                  >
                    Open source chunk
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState
              title="No matching evidence"
              detail="No compatible chunks matched this search."
            />
          )}
        </div>
      )}
    </section>
  );
}
