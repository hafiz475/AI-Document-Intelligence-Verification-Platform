import { apiRequest } from "./client";
import type { ChunkList, DocumentRecord } from "./types";

export function getDocuments(projectId: string): Promise<DocumentRecord[]> {
  return apiRequest(`/api/v1/projects/${projectId}/documents`);
}

export function getDocument(
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  return apiRequest(`/api/v1/projects/${projectId}/documents/${documentId}`);
}

export function getDocumentChunks(
  projectId: string,
  documentId: string,
): Promise<ChunkList> {
  return apiRequest(
    `/api/v1/projects/${projectId}/documents/${documentId}/chunks?limit=100`,
  );
}

export function uploadDocument(
  projectId: string,
  file: File,
): Promise<DocumentRecord> {
  const body = new FormData();
  body.append("file", file);
  return apiRequest(`/api/v1/projects/${projectId}/documents`, {
    method: "POST",
    body,
  });
}
