import { apiRequest } from "./client";
import type {
  EmbeddingRun,
  RetrievalEvaluationRun,
  SemanticSearchResponse,
} from "./types";

export function getEmbeddingRuns(projectId: string, documentId: string) {
  return apiRequest<EmbeddingRun[]>(
    "/api/v1/projects/" +
      projectId +
      "/documents/" +
      documentId +
      "/embeddings",
  );
}

export function createEmbeddingRun(projectId: string, documentId: string) {
  return apiRequest<EmbeddingRun>(
    "/api/v1/projects/" +
      projectId +
      "/documents/" +
      documentId +
      "/embeddings",
    { method: "POST" },
  );
}

export function semanticSearch(
  projectId: string,
  query: string,
  topK: number,
  documentId?: string,
) {
  const path = documentId
    ? "/api/v1/projects/" + projectId + "/documents/" + documentId + "/search"
    : "/api/v1/projects/" + projectId + "/search";
  return apiRequest<SemanticSearchResponse>(path, {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

export function getRetrievalEvaluations(projectId: string) {
  return apiRequest<RetrievalEvaluationRun[]>(
    "/api/v1/projects/" + projectId + "/retrieval-evaluations",
  );
}
