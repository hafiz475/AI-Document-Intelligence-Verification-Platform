import { apiRequest } from "./client";
import type {
  EvaluationCase,
  EvaluationComparison,
  EvaluationDataset,
  EvaluationRun,
  EvaluationType,
} from "./types";

export interface DatasetInput {
  name: string;
  description?: string;
  evaluation_type: EvaluationType;
}

export interface CaseInput {
  name: string;
  input_json: Record<string, unknown>;
  expected_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
}

export interface RunInput {
  dataset_id: string;
  prompt_version_id?: string;
  provider?: string;
  model?: string;
  embedding_provider?: string;
  embedding_model?: string;
  top_k: number;
}

export function getEvaluationDatasets(projectId: string) {
  return apiRequest<EvaluationDataset[]>(
    `/api/v1/projects/${projectId}/evaluation-datasets`,
  );
}

export function createEvaluationDataset(
  projectId: string,
  payload: DatasetInput,
) {
  return apiRequest<EvaluationDataset>(
    `/api/v1/projects/${projectId}/evaluation-datasets`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function createEvaluationCase(
  projectId: string,
  datasetId: string,
  payload: CaseInput,
) {
  return apiRequest<EvaluationCase>(
    `/api/v1/projects/${projectId}/evaluation-datasets/${datasetId}/cases`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function updateEvaluationCase(
  projectId: string,
  datasetId: string,
  caseId: string,
  payload: CaseInput,
) {
  return apiRequest<EvaluationCase>(
    `/api/v1/projects/${projectId}/evaluation-datasets/${datasetId}/cases/${caseId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export interface EvaluationRunFilters {
  evaluationType?: string;
  status?: string;
  providerModel?: string;
  limit?: number;
  offset?: number;
}

export function getEvaluationRuns(
  projectId: string,
  filters: EvaluationRunFilters = {},
) {
  const params = new URLSearchParams();
  if (filters.evaluationType)
    params.set("evaluation_type", filters.evaluationType);
  if (filters.status) params.set("status", filters.status);
  if (filters.providerModel)
    params.set("provider_model", filters.providerModel);
  params.set("limit", String(filters.limit ?? 51));
  params.set("offset", String(filters.offset ?? 0));
  return apiRequest<EvaluationRun[]>(
    `/api/v1/projects/${projectId}/evaluation-runs?${params.toString()}`,
  );
}

export function createEvaluationRun(projectId: string, payload: RunInput) {
  return apiRequest<EvaluationRun>(
    `/api/v1/projects/${projectId}/evaluation-runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function compareEvaluationRuns(
  projectId: string,
  runAId: string,
  runBId: string,
) {
  return apiRequest<EvaluationComparison>(
    `/api/v1/projects/${projectId}/evaluation-comparisons`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_a_id: runAId,
        run_b_id: runBId,
        thresholds: {
          minimum_pass_rate: 0.8,
          maximum_latency_regression_percent: 20,
          maximum_token_regression_percent: 20,
        },
      }),
    },
  );
}
