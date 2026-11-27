import { apiRequest } from "./client";
import type { RagQuestion, RagSupportStatus } from "./types";

export interface QuestionFilters {
  supportStatus?: RagSupportStatus | "";
  createdFrom?: string;
  createdTo?: string;
  limit?: number;
  offset?: number;
}

export function getQuestions(
  projectId: string,
  documentId?: string,
  filters: QuestionFilters = {},
) {
  const params = new URLSearchParams();
  if (documentId) params.set("document_id", documentId);
  if (filters.supportStatus)
    params.set("support_status", filters.supportStatus);
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.createdTo) params.set("created_to", filters.createdTo);
  params.set("limit", String(filters.limit ?? 26));
  params.set("offset", String(filters.offset ?? 0));
  const query = `?${params.toString()}`;
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
