import { apiRequest } from "./client";
import type { ExtractedField, ExtractionRun, FieldReview } from "./types";

function basePath(projectId: string, documentId: string): string {
  return `/api/v1/projects/${projectId}/documents/${documentId}/extractions`;
}

export function createExtraction(
  projectId: string,
  documentId: string,
): Promise<ExtractionRun> {
  return apiRequest(basePath(projectId, documentId), { method: "POST" });
}

export function getExtractions(
  projectId: string,
  documentId: string,
): Promise<ExtractionRun[]> {
  return apiRequest(basePath(projectId, documentId));
}

export function getExtraction(
  projectId: string,
  documentId: string,
  runId: string,
): Promise<ExtractionRun> {
  return apiRequest(`${basePath(projectId, documentId)}/${runId}`);
}

export function reviewField(
  projectId: string,
  documentId: string,
  runId: string,
  fieldId: string,
  review: FieldReview,
): Promise<ExtractedField> {
  return apiRequest(
    `${basePath(projectId, documentId)}/${runId}/fields/${fieldId}/review`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(review),
    },
  );
}
