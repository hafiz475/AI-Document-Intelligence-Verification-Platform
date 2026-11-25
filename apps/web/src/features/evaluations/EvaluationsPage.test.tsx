import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { EvaluationDataset, EvaluationRun } from "../../api/types";
import {
  useCompareEvaluationRuns,
  useCreateEvaluationDataset,
  useCreateEvaluationRun,
  useEvaluationDatasets,
  useEvaluationRuns,
  useSaveEvaluationCase,
} from "../hooks";
import { EvaluationsPage } from "./EvaluationsPage";

vi.mock("../hooks", () => ({
  useCompareEvaluationRuns: vi.fn(),
  useCreateEvaluationDataset: vi.fn(),
  useCreateEvaluationRun: vi.fn(),
  useEvaluationDatasets: vi.fn(),
  useEvaluationRuns: vi.fn(),
  useSaveEvaluationCase: vi.fn(),
}));

const evaluationCase = {
  id: "case-1",
  dataset_id: "dataset-1",
  name: "Supported vibration case",
  input_json: { question: "What vibration was measured?" },
  expected_json: { support_status: "SUPPORTED" },
  metadata_json: {},
  created_at: "2026-11-25T10:00:00Z",
  updated_at: "2026-11-25T10:00:00Z",
};

const dataset: EvaluationDataset = {
  id: "dataset-1",
  project_id: "project-1",
  name: "Synthetic RAG quality",
  description: null,
  evaluation_type: "RAG",
  case_count: 1,
  cases: [evaluationCase],
  created_at: "2026-11-25T10:00:00Z",
  updated_at: "2026-11-25T10:00:00Z",
};

function run(
  evaluationType: EvaluationRun["evaluation_type"] = "RAG",
  status: EvaluationRun["status"] = "COMPLETED",
): EvaluationRun {
  const metrics =
    evaluationType === "EXTRACTION"
      ? { field_accuracy: 0.92, missing_field_rate: 0.08 }
      : evaluationType === "RETRIEVAL"
        ? { chunk_hit_at_k: 1, chunk_recall_at_k: 0.8, chunk_mrr: 0.5 }
        : {
            support_status_correct: 1,
            citation_validity: 1,
            insufficient_evidence_correct: 1,
          };
  return {
    id: `run-${evaluationType.toLowerCase()}-${status.toLowerCase()}`,
    project_id: "project-1",
    dataset_id: "dataset-1",
    evaluation_type: evaluationType,
    status,
    prompt_version_id: evaluationType === "RETRIEVAL" ? null : "prompt-v1",
    provider: "development",
    model: "deterministic-development-v1",
    embedding_provider: evaluationType === "EXTRACTION" ? null : "development",
    embedding_model:
      evaluationType === "EXTRACTION" ? null : "deterministic-development-v1",
    evaluator_version: "v1",
    configuration_json: { top_k: 5 },
    aggregate_metrics_json: metrics,
    started_at: "2026-11-25T10:00:00Z",
    completed_at: status === "COMPLETED" ? "2026-11-25T10:00:01Z" : null,
    total_cases: 1,
    passed_cases: status === "COMPLETED" ? 1 : 0,
    failed_cases: 0,
    error_cases: 0,
    average_score: 0.9,
    average_latency_ms: 120,
    input_tokens: 20,
    output_tokens: 10,
    total_tokens: 30,
    error_message:
      status === "FAILED" ? "Synthetic infrastructure failure." : null,
    case_results:
      status === "COMPLETED"
        ? [
            {
              id: "result-1",
              evaluation_run_id: "run-rag-completed",
              evaluation_case_id: "case-1",
              status: "PASSED",
              score: 1,
              metrics_json: metrics,
              case_snapshot_json: {
                name: "Supported vibration case",
                input: evaluationCase.input_json,
                expected: evaluationCase.expected_json,
              },
              actual_output_json: {
                answer: "Vibration was 8.4 mm/s RMS.",
                citations: [{ chunk_id: "chunk-1" }],
              },
              error_message: null,
              latency_ms: 120,
              input_tokens: 20,
              output_tokens: 10,
              total_tokens: 30,
              created_at: "2026-11-25T10:00:01Z",
            },
          ]
        : [],
    created_at: "2026-11-25T10:00:00Z",
    updated_at: "2026-11-25T10:00:01Z",
  };
}

const createDatasetMutate = vi.fn();
const saveCaseMutate = vi.fn();
const createRunMutate = vi.fn();
const compareMutate = vi.fn();

function arrange(
  availableRuns: EvaluationRun[] = [run()],
  comparisonData: object | undefined = undefined,
) {
  vi.mocked(useEvaluationDatasets).mockReturnValue({
    data: [dataset],
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useEvaluationRuns).mockReturnValue({
    data: availableRuns,
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useCreateEvaluationDataset).mockReturnValue({
    mutate: createDatasetMutate,
    isPending: false,
    isError: false,
  } as never);
  vi.mocked(useSaveEvaluationCase).mockReturnValue({
    mutate: saveCaseMutate,
    isPending: false,
    isError: false,
  } as never);
  vi.mocked(useCreateEvaluationRun).mockReturnValue({
    mutate: createRunMutate,
    isPending: false,
    isError: false,
  } as never);
  vi.mocked(useCompareEvaluationRuns).mockReturnValue({
    mutate: compareMutate,
    isPending: false,
    isError: false,
    data: comparisonData,
  } as never);
  render(
    <MemoryRouter initialEntries={["/projects/project-1/evaluations"]}>
      <Routes>
        <Route
          element={<EvaluationsPage />}
          path="/projects/:projectId/evaluations"
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

it("renders the dataset list", () => {
  arrange();
  expect(screen.getByRole("heading", { name: "Datasets" })).toBeInTheDocument();
  expect(screen.getAllByText("Synthetic RAG quality").length).toBeGreaterThan(
    0,
  );
});

it("renders dataset detail", () => {
  arrange();
  expect(screen.getByText("RAG dataset detail")).toBeInTheDocument();
  expect(screen.getByText("1 / 200 cases")).toBeInTheDocument();
});

it("renders a case and expected data", () => {
  arrange();
  expect(
    screen.getAllByText("Supported vibration case").length,
  ).toBeGreaterThan(0);
  expect(screen.getAllByText(/support_status/).length).toBeGreaterThan(0);
});

it("creates a run", () => {
  arrange();
  fireEvent.click(screen.getByRole("button", { name: "Run evaluation" }));
  expect(createRunMutate).toHaveBeenCalledWith(
    { dataset_id: "dataset-1", top_k: 5 },
    expect.any(Object),
  );
});

it("shows processing state", () => {
  arrange([run("RAG", "PROCESSING")]);
  fireEvent.click(screen.getByRole("button", { name: "RAG" }));
  expect(screen.getByRole("status")).toHaveTextContent(
    "processing sequentially",
  );
});

it("shows a completed run summary", () => {
  arrange();
  fireEvent.click(screen.getByRole("button", { name: "RAG" }));
  expect(screen.getByLabelText("Run detail")).toHaveTextContent("v1");
  expect(screen.getByLabelText("Run detail")).toHaveTextContent("COMPLETED");
});

it("shows extraction metrics", () => {
  arrange([run("EXTRACTION")]);
  fireEvent.click(screen.getByRole("button", { name: "EXTRACTION" }));
  expect(screen.getByLabelText("EXTRACTION metrics")).toHaveTextContent(
    "Field Accuracy",
  );
});

it("shows retrieval metrics", () => {
  arrange([run("RETRIEVAL")]);
  fireEvent.click(screen.getByRole("button", { name: "RETRIEVAL" }));
  expect(screen.getByLabelText("RETRIEVAL metrics")).toHaveTextContent(
    "Chunk Recall At K",
  );
});

it("shows RAG and citation metrics", () => {
  arrange();
  fireEvent.click(screen.getByRole("button", { name: "RAG" }));
  expect(screen.getByLabelText("RAG metrics")).toHaveTextContent(
    "Citation Validity",
  );
});

it("renders comparison deltas", () => {
  arrange([run(), { ...run(), id: "run-b" }], {
    status: "PASS",
    metrics: [
      { metric: "citation_validity", run_a: 0.8, run_b: 1, delta: 0.2 },
    ],
    run_a_id: "run-a",
    run_b_id: "run-b",
    dataset_id: "dataset-1",
    embedding_compatible: true,
    latency_regression_percent: 0,
    token_regression_percent: 0,
  });
  expect(screen.getByText("Regression status: PASS")).toBeInTheDocument();
  expect(screen.getByText("+0.200")).toBeInTheDocument();
});

it("renders regression state without relying on color", () => {
  arrange([run(), { ...run(), id: "run-b" }], {
    status: "REGRESSION",
    metrics: [],
    run_a_id: "run-a",
    run_b_id: "run-b",
    dataset_id: "dataset-1",
    embedding_compatible: true,
    latency_regression_percent: 0,
    token_regression_percent: 0,
  });
  expect(screen.getByText("Regression status: REGRESSION")).toBeInTheDocument();
});

it("renders case result inspection details", () => {
  arrange();
  fireEvent.click(screen.getByRole("button", { name: "RAG" }));
  expect(screen.getByText(/8.4 mm\/s RMS/)).toBeInTheDocument();
  expect(screen.getByText("120 ms - 30 tokens")).toBeInTheDocument();
});

it("renders a failed run safely", () => {
  arrange([run("RAG", "FAILED")]);
  fireEvent.click(screen.getByRole("button", { name: "RAG" }));
  expect(
    screen.getByText("Synthetic infrastructure failure."),
  ).toBeInTheDocument();
});
