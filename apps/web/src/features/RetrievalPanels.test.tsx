import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type {
  EmbeddingRun,
  RetrievalEvaluationRun,
  SemanticSearchResponse,
} from "../api/types";
import { EmbeddingPanel } from "./documents/EmbeddingPanel";
import { RetrievalEvaluationPanel } from "./RetrievalEvaluationPanel";
import { SemanticSearchPanel } from "./SemanticSearchPanel";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockResponses(...values: unknown[]) {
  const mock = vi.fn<typeof fetch>();
  for (const value of values) {
    if (
      typeof value === "object" &&
      value !== null &&
      "body" in value &&
      "status" in value
    ) {
      mock.mockResolvedValueOnce(response(value.body, value.status as number));
    } else {
      mock.mockResolvedValueOnce(response(value));
    }
  }
  vi.stubGlobal("fetch", mock);
  return mock;
}

function wrapper(children: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>,
  );
}

function embedding(overrides: Partial<EmbeddingRun> = {}): EmbeddingRun {
  return {
    id: "embedding-run-1",
    project_id: "project-1",
    document_id: "document-1",
    status: "COMPLETED",
    provider: "development",
    model: "deterministic-development-v1",
    dimensions: 64,
    embedding_version: "development-hash-v1",
    chunks_total: 3,
    chunks_embedded: 3,
    latency_ms: 2,
    input_tokens: null,
    started_at: "2026-11-10T10:00:00Z",
    completed_at: "2026-11-10T10:00:01Z",
    error_code: null,
    error_message: null,
    created_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-10T10:00:01Z",
    ...overrides,
  };
}

const searchResult: SemanticSearchResponse = {
  query: "gearbox vibration",
  provider: "development",
  model: "deterministic-development-v1",
  dimensions: 64,
  metric: "cosine_similarity",
  query_embedding_latency_ms: 1,
  search_latency_ms: 3,
  results: [
    {
      rank: 1,
      document_id: "document-1",
      document_name: "inspection.txt",
      chunk_id: "chunk-1",
      chunk_index: 2,
      page_number: 3,
      content: "Abnormal gearbox vibration was detected.",
      similarity_score: 0.91234,
      metadata: {},
      embedding_model: "deterministic-development-v1",
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

it("shows embedding NOT_GENERATED and starts generation", async () => {
  const queued = embedding({
    status: "QUEUED",
    chunks_embedded: 0,
    completed_at: null,
  });
  mockResponses([], queued, [queued]);
  wrapper(<EmbeddingPanel documentId="document-1" projectId="project-1" />);
  expect(await screen.findByText("NOT_GENERATED")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Generate Embeddings" }));
  expect(await screen.findByText("QUEUED")).toBeInTheDocument();
});

it.each([
  ["PROCESSING", "PROCESSING"],
  ["COMPLETED", "READY"],
] as const)("renders %s embedding state", async (status, expected) => {
  mockResponses([embedding({ status })]);
  wrapper(<EmbeddingPanel documentId="document-1" projectId="project-1" />);
  expect(await screen.findByText(expected)).toBeInTheDocument();
  expect(screen.getByText("3 / 3")).toBeInTheDocument();
});

it("renders failed embedding state", async () => {
  mockResponses([
    embedding({
      status: "FAILED",
      chunks_embedded: 0,
      error_message: "Synthetic provider failure.",
    }),
  ]);
  wrapper(<EmbeddingPanel documentId="document-1" projectId="project-1" />);
  expect(await screen.findByText("FAILED")).toBeInTheDocument();
  expect(screen.getByText("Synthetic provider failure.")).toBeInTheDocument();
});

it("renders ranked project semantic search evidence", async () => {
  mockResponses(searchResult);
  wrapper(<SemanticSearchPanel projectId="project-1" />);
  fireEvent.change(
    screen.getByPlaceholderText("Ask what evidence exists in these documents…"),
    { target: { value: "gearbox vibration" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));
  expect(await screen.findByText(/1\. inspection\.txt/i)).toBeInTheDocument();
  expect(
    screen.getByText("Abnormal gearbox vibration was detected."),
  ).toBeInTheDocument();
  expect(screen.getByText("Score 0.9123")).toBeInTheDocument();
  expect(screen.getByText(/no generated answer/i)).toBeInTheDocument();
});

it("uses document-scoped semantic search endpoint", async () => {
  const fetchMock = mockResponses(searchResult);
  wrapper(
    <SemanticSearchPanel documentId="document-1" projectId="project-1" />,
  );
  fireEvent.change(
    screen.getByPlaceholderText("Ask what evidence exists in these documents…"),
    { target: { value: "blade damage" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));
  await screen.findByText("Score 0.9123");
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/projects/project-1/documents/document-1/search"),
    expect.objectContaining({ method: "POST" }),
  );
});

it("renders empty search results", async () => {
  mockResponses({ ...searchResult, results: [] });
  wrapper(<SemanticSearchPanel projectId="project-1" />);
  fireEvent.change(
    screen.getByPlaceholderText("Ask what evidence exists in these documents…"),
    { target: { value: "hydraulic leak" } },
  );
  fireEvent.submit(screen.getByRole("button", { name: "Search evidence" }));
  expect(await screen.findByText("No matching evidence")).toBeInTheDocument();
});

it("renders missing compatible embeddings error", async () => {
  mockResponses({
    body: { detail: "No compatible embeddings exist for this search scope." },
    status: 409,
  });
  wrapper(<SemanticSearchPanel projectId="project-1" />);
  fireEvent.change(
    screen.getByPlaceholderText("Ask what evidence exists in these documents…"),
    { target: { value: "gearbox" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));
  expect(
    await screen.findByText(
      "No compatible embeddings exist for this search scope.",
    ),
  ).toBeInTheDocument();
});

it("renders retrieval evaluation metrics and cases", async () => {
  const evaluation: RetrievalEvaluationRun = {
    id: "evaluation-1",
    project_id: "project-1",
    embedding_provider: "development",
    embedding_model: "deterministic-development-v1",
    top_k: 5,
    case_count: 1,
    hit_rate: 1,
    mean_reciprocal_rank: 0.5,
    recall_at_k: 1,
    started_at: "2026-11-10T10:00:00Z",
    completed_at: "2026-11-10T10:00:01Z",
    created_at: "2026-11-10T10:00:01Z",
    case_results: [
      {
        id: "case-1",
        query: "gearbox vibration",
        expected_chunk_ids: ["chunk-1"],
        retrieved_chunk_ids: ["chunk-2", "chunk-1"],
        first_relevant_rank: 2,
        hit: true,
        recall: 1,
        reciprocal_rank: 0.5,
      },
    ],
  };
  mockResponses([evaluation]);
  wrapper(<RetrievalEvaluationPanel projectId="project-1" />);
  expect(await screen.findByText("100.0%")).toBeInTheDocument();
  expect(screen.getByText("0.500")).toBeInTheDocument();
  expect(screen.getByText("PASS")).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
});
