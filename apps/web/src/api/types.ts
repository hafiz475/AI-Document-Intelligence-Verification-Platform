export type DocumentStatus =
  "UPLOADED" | "QUEUED" | "PROCESSING" | "READY" | "FAILED";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  current_role: ProjectRole;
  created_at: string;
  updated_at: string;
}

export type ProjectRole = "OWNER" | "EDITOR" | "VIEWER";

export interface CurrentUser {
  id: string;
  external_subject: string;
  email: string | null;
  display_name: string | null;
}

export interface ProjectMembership {
  project_id: string;
  user: CurrentUser;
  role: ProjectRole;
  created_at: string;
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

export type EmbeddingRunStatus =
  "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface EmbeddingRun {
  id: string;
  project_id: string;
  document_id: string;
  status: EmbeddingRunStatus;
  provider: string;
  model: string;
  dimensions: number;
  embedding_version: string;
  chunks_total: number;
  chunks_embedded: number;
  latency_ms: number | null;
  input_tokens: number | null;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SemanticSearchResult {
  rank: number;
  document_id: string;
  document_name: string;
  chunk_id: string;
  chunk_index: number;
  page_number: number | null;
  content: string;
  similarity_score: number;
  metadata: Record<string, unknown>;
  embedding_model: string;
}

export interface SemanticSearchResponse {
  query: string;
  provider: string;
  model: string;
  dimensions: number;
  metric: "cosine_similarity";
  query_embedding_latency_ms: number;
  search_latency_ms: number;
  results: SemanticSearchResult[];
}

export interface RetrievalEvaluationCase {
  id: string;
  query: string;
  expected_chunk_ids: string[];
  retrieved_chunk_ids: string[];
  first_relevant_rank: number | null;
  hit: boolean;
  recall: number;
  reciprocal_rank: number;
}

export interface RetrievalEvaluationRun {
  id: string;
  project_id: string;
  embedding_provider: string;
  embedding_model: string;
  top_k: number;
  case_count: number;
  hit_rate: number;
  mean_reciprocal_rank: number;
  recall_at_k: number;
  started_at: string;
  completed_at: string;
  created_at: string;
  case_results: RetrievalEvaluationCase[];
}

export type RagQuestionStatus =
  "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type RagSupportStatus =
  "SUPPORTED" | "PARTIALLY_SUPPORTED" | "INSUFFICIENT_EVIDENCE";

export interface RagCitation {
  id: string;
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number | null;
  quote: string;
  rank: number;
  similarity_score: number;
  created_at: string;
}

export interface RagAnswer {
  id: string;
  answer_text: string;
  support_status: RagSupportStatus;
  confidence: number | null;
  citations: RagCitation[];
  created_at: string;
}

export interface RagRetrievedSource {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number | null;
  rank: number;
  similarity_score: number;
  content: string;
  embedding_provider: string;
  embedding_model: string;
}

export interface RagQuestion {
  id: string;
  project_id: string;
  document_id: string | null;
  question: string;
  status: RagQuestionStatus;
  retrieval_top_k: number;
  provider: string;
  model: string;
  prompt_version: PromptVersion;
  started_at: string | null;
  completed_at: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  error_message: string | null;
  answer: RagAnswer | null;
  retrieved_sources: RagRetrievedSource[];
  created_at: string;
  updated_at: string;
}

export type EvaluationType = "EXTRACTION" | "RETRIEVAL" | "RAG";
export type EvaluationRunStatus =
  "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
export type EvaluationResultStatus = "PASSED" | "FAILED" | "ERROR";

export interface EvaluationCase {
  id: string;
  dataset_id: string;
  name: string;
  input_json: Record<string, unknown>;
  expected_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EvaluationDataset {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  evaluation_type: EvaluationType;
  case_count: number;
  cases: EvaluationCase[];
  created_at: string;
  updated_at: string;
}

export interface EvaluationCaseResult {
  id: string;
  evaluation_run_id: string;
  evaluation_case_id: string;
  status: EvaluationResultStatus;
  score: number | null;
  metrics_json: Record<string, unknown>;
  case_snapshot_json: Record<string, unknown>;
  actual_output_json: Record<string, unknown>;
  error_message: string | null;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  created_at: string;
}

export interface EvaluationRun {
  id: string;
  project_id: string;
  dataset_id: string;
  evaluation_type: EvaluationType;
  status: EvaluationRunStatus;
  prompt_version_id: string | null;
  provider: string;
  model: string;
  embedding_provider: string | null;
  embedding_model: string | null;
  evaluator_version: string;
  configuration_json: Record<string, unknown>;
  aggregate_metrics_json: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  error_cases: number;
  average_score: number | null;
  average_latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  error_message: string | null;
  case_results: EvaluationCaseResult[];
  created_at: string;
  updated_at: string;
}

export interface MetricComparison {
  metric: string;
  run_a: number | null;
  run_b: number | null;
  delta: number | null;
}

export interface EvaluationComparison {
  run_a_id: string;
  run_b_id: string;
  dataset_id: string;
  embedding_compatible: boolean;
  status: "PASS" | "WARNING" | "REGRESSION";
  metrics: MetricComparison[];
  latency_regression_percent: number;
  token_regression_percent: number;
}

export interface UsageSummary {
  extraction_tokens: number | null;
  rag_tokens: number | null;
  evaluation_tokens: number | null;
  total_tokens: number | null;
  average_provider_latency_ms: number | null;
  records_with_token_usage: number;
}

export interface ProviderUsage {
  provider: string;
  model: string;
  operation: string;
  requests: number;
}

export interface OverviewMetrics {
  documents: number;
  documents_ready: number;
  documents_failed: number;
  extraction_runs: number;
  fields_awaiting_review: number;
  verified_fields: number;
  rag_questions: number;
  supported_answers: number;
  insufficient_evidence_answers: number;
  evaluation_pass_rate: number | null;
  average_retrieval_latency_ms: number | null;
  average_rag_latency_ms: number | null;
}

export interface ActivityItem {
  id: string;
  event_type: string;
  target_type: string | null;
  target_id: string | null;
  document_id: string | null;
  actor: string | null;
  created_at: string;
}

export interface ProjectOverview {
  metrics: OverviewMetrics;
  usage: UsageSummary;
  provider_usage: ProviderUsage[];
  recent_activity: ActivityItem[];
}

export interface DocumentIndex {
  items: DocumentRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewQueueItem {
  document_id: string;
  document_name: string;
  extraction_run_id: string;
  provider: string;
  model: string;
  field: ExtractedField;
}

export interface ReviewQueue {
  items: ReviewQueueItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProductAuditItem {
  id: string;
  event_type: string;
  actor: string | null;
  document_id: string | null;
  target_type: string | null;
  target_id: string | null;
  request_id: string | null;
  trace_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditIndex {
  items: ProductAuditItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentReport {
  document: DocumentRecord;
  latest_extraction: ExtractionRun | null;
  question_count: number;
  supported_answer_count: number;
  insufficient_answer_count: number;
}
