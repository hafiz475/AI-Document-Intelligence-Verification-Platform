import { apiRequest } from "./client";
import type {
  AuditIndex,
  DocumentIndex,
  DocumentReport,
  ProjectOverview,
  ReviewQueue,
  ReviewStatus,
} from "./types";

function queryString(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const value = params.toString();
  return value ? `?${value}` : "";
}

export function getProjectOverview(
  projectId: string,
): Promise<ProjectOverview> {
  return apiRequest(`/api/v1/projects/${projectId}/overview`);
}

export interface DocumentFilters {
  status?: string;
  mimeType?: string;
  createdFrom?: string;
  createdTo?: string;
  limit?: number;
  offset?: number;
}

export function getDocumentIndex(
  projectId: string,
  filters: DocumentFilters,
): Promise<DocumentIndex> {
  return apiRequest(
    `/api/v1/projects/${projectId}/document-index${queryString({
      status: filters.status,
      mime_type: filters.mimeType,
      created_from: filters.createdFrom,
      created_to: filters.createdTo,
      limit: filters.limit ?? 25,
      offset: filters.offset ?? 0,
    })}`,
  );
}

export interface ReviewFilters {
  status?: ReviewStatus;
  documentId?: string;
  fieldName?: string;
  createdFrom?: string;
  createdTo?: string;
  limit?: number;
  offset?: number;
}

export function getReviewQueue(
  projectId: string,
  filters: ReviewFilters,
): Promise<ReviewQueue> {
  return apiRequest(
    `/api/v1/projects/${projectId}/review-queue${queryString({
      status: filters.status,
      document_id: filters.documentId,
      field_name: filters.fieldName,
      created_from: filters.createdFrom,
      created_to: filters.createdTo,
      limit: filters.limit ?? 25,
      offset: filters.offset ?? 0,
    })}`,
  );
}

export interface AuditFilters {
  eventType?: string;
  actorUserId?: string;
  documentId?: string;
  createdFrom?: string;
  createdTo?: string;
  limit?: number;
  offset?: number;
}

export function getAuditIndex(
  projectId: string,
  filters: AuditFilters,
): Promise<AuditIndex> {
  return apiRequest(
    `/api/v1/projects/${projectId}/audit-events${queryString({
      event_type: filters.eventType,
      actor_user_id: filters.actorUserId,
      document_id: filters.documentId,
      created_from: filters.createdFrom,
      created_to: filters.createdTo,
      limit: filters.limit ?? 25,
      offset: filters.offset ?? 0,
    })}`,
  );
}

export function getDocumentReport(
  projectId: string,
  documentId: string,
): Promise<DocumentReport> {
  return apiRequest(
    `/api/v1/projects/${projectId}/documents/${documentId}/report`,
  );
}
