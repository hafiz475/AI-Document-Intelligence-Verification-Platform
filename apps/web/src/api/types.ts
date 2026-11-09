export type DocumentStatus =
  "UPLOADED" | "QUEUED" | "PROCESSING" | "READY" | "FAILED";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentRecord {
  id: string;
  project_id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  sha256_hash: string;
  status: DocumentStatus;
  page_count: number | null;
  character_count: number | null;
  processing_error: string | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  page_number: number | null;
  section: string | null;
  content: string;
  character_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ChunkList {
  items: DocumentChunk[];
  total: number;
  limit: number;
  offset: number;
}

export type ExtractionRunStatus =
  "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type ReviewStatus = "UNREVIEWED" | "VERIFIED" | "CORRECTED" | "REJECTED";

export type SupportStatus = "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED";

export type ExtractedValue = string | string[] | null;

export interface PromptVersion {
  id: string;
  version: number;
  schema_version: string;
  created_at: string;
}

export interface ExtractionEvidence {
  id: string;
  document_chunk_id: string;
  page_number: number | null;
  quote: string;
  created_at: string;
}

export interface ExtractedField {
  id: string;
  extraction_run_id: string;
  document_id: string;
  field_name: string;
  field_type: string;
  raw_value: ExtractedValue;
  normalized_value: ExtractedValue;
  missing_reason: string | null;
  corrected_value: ExtractedValue;
  review_status: ReviewStatus;
  support_status: SupportStatus;
  review_reason: string | null;
  reviewer: string | null;
  reviewed_at: string | null;
  evidence: ExtractionEvidence[];
  created_at: string;
  updated_at: string;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  extracted_field_id: string | null;
  metadata: Record<string, unknown>;
  reviewer: string | null;
  created_at: string;
}

export interface ExtractionRun {
  id: string;
  project_id: string;
  document_id: string;
  status: ExtractionRunStatus;
  provider: string;
  model: string;
  prompt_version: PromptVersion;
  started_at: string | null;
  completed_at: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  error_code: string | null;
  error_message: string | null;
  fields: ExtractedField[];
  audit_events: AuditEvent[];
  created_at: string;
  updated_at: string;
}

export interface FieldReview {
  decision: Exclude<ReviewStatus, "UNREVIEWED">;
  value?: string | string[];
  reason?: string;
}
