import { apiRequest } from "./client";
import type { RagQuestion } from "./types";

export function getQuestions(projectId: string, documentId?: string) {
  const query = documentId
    ? "?document_id=" + encodeURIComponent(documentId)
    : "";
  return apiRequest<RagQuestion[]>(
    "/api/v1/projects/" + projectId + "/questions" + query,
  );
}

export function createQuestion(
  projectId: string,
  question: string,
  topK: number,
  documentId?: string,
) {
  const path = documentId
    ? "/api/v1/projects/" +
      projectId +
      "/documents/" +
      documentId +
      "/questions"
    : "/api/v1/projects/" + projectId + "/questions";
  return apiRequest<RagQuestion>(path, {
    method: "POST",
    body: JSON.stringify({ question, top_k: topK }),
  });
}
