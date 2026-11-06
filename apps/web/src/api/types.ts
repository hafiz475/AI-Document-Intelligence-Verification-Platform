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
