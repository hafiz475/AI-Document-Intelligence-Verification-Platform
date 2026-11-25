import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { RagQuestion } from "../api/types";
import { RagQuestionPanel } from "./RagQuestionPanel";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockResponses(...values: Array<{ body: unknown; status?: number }>) {
  const mock = vi.fn<typeof fetch>();
  for (const value of values) {
    mock.mockResolvedValueOnce(response(value.body, value.status));
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

function question(overrides: Partial<RagQuestion> = {}): RagQuestion {
  return {
    id: "question-1",
    project_id: "project-1",
    document_id: null,
    question: "What abnormal condition was detected?",
    status: "COMPLETED",
    retrieval_top_k: 5,
    provider: "development",
    model: "deterministic-rag-development-v1",
    prompt_version: {
      id: "prompt-1",
      version: 1,
      schema_version: "rag-answer-v1",
      created_at: "2026-11-25T10:00:00Z",
    },
    started_at: "2026-11-25T10:00:00Z",
    completed_at: "2026-11-25T10:00:01Z",
    latency_ms: 12,
    input_tokens: 40,
    output_tokens: 20,
    total_tokens: 60,
    error_message: null,
    answer: {
      id: "answer-1",
      answer_text:
        "The drive-end bearing vibration measured 8.4 mm/s RMS, above expected.",
      support_status: "SUPPORTED",
      confidence: null,
      citations: [
        {
          id: "citation-1",
          chunk_id: "chunk-1",
          document_id: "document-1",
          document_name: "pump-inspection.txt",
          page_number: 3,
          quote: "Drive-end bearing vibration measured 8.4 mm/s RMS.",
          rank: 1,
          similarity_score: 0.91234,
          created_at: "2026-11-25T10:00:01Z",
        },
      ],
      created_at: "2026-11-25T10:00:01Z",
    },
    retrieved_sources: [
      {
        chunk_id: "chunk-1",
        document_id: "document-1",
        document_name: "pump-inspection.txt",
        page_number: 3,
        rank: 1,
        similarity_score: 0.91234,
        content: "Drive-end bearing vibration measured 8.4 mm/s RMS.",
        embedding_provider: "development",
        embedding_model: "deterministic-development-v1",
      },
    ],
    created_at: "2026-11-25T10:00:00Z",
    updated_at: "2026-11-25T10:00:01Z",
    ...overrides,
  };
}

afterEach(() => vi.unstubAllGlobals());

it("submits a question and shows the queued loading state", async () => {
  const queued = question({ status: "QUEUED", answer: null });
  const fetchMock = mockResponses(
    { body: [] },
    { body: queued },
    { body: [queued] },
  );
  wrapper(<RagQuestionPanel projectId="project-1" />);
  fireEvent.change(
    await screen.findByPlaceholderText("What abnormal condition was detected?"),
    { target: { value: "What abnormal condition was detected?" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Ask AssureAI" }));
  expect(
    await screen.findByText("Question queued for grounded processing…"),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/projects/project-1/questions"),
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        question: "What abnormal condition was detected?",
        top_k: 5,
      }),
    }),
  );
}, 10_000);

it("renders a supported answer, multiple citations, and retrieved sources", async () => {
  const baseCitation = question().answer?.citations[0];
  if (!baseCitation) throw new Error("Test fixture citation is required.");
  const supported = question({
    answer: {
      ...question().answer!,
      citations: [
        baseCitation,
        {
          ...baseCitation,
          id: "citation-2",
          chunk_id: "chunk-2",
          document_name: "maintenance.txt",
          page_number: 4,
          rank: 2,
          quote: "Inspect alignment and lubrication before continued service.",
        },
      ],
    },
  });
  mockResponses({ body: [supported] });
  wrapper(<RagQuestionPanel projectId="project-1" />);
  expect((await screen.findAllByText("SUPPORTED")).length).toBeGreaterThan(0);
  expect(screen.getByText(/8.4 mm\/s RMS, above expected/)).toBeInTheDocument();
  expect(screen.getAllByText(/pump-inspection.txt/).length).toBeGreaterThan(0);
  expect(screen.getByText(/maintenance.txt/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Inspect all retrieved sources"));
  expect(
    screen.getAllByText("Drive-end bearing vibration measured 8.4 mm/s RMS.")
      .length,
  ).toBeGreaterThan(0);
});

it("renders insufficient evidence without citations", async () => {
  const insufficient = question({
    question: "What was the motor winding temperature?",
    answer: {
      ...question().answer!,
      answer_text:
        "The available documents do not provide enough evidence to answer this question.",
      support_status: "INSUFFICIENT_EVIDENCE",
      citations: [],
    },
  });
  mockResponses({ body: [insufficient] });
  wrapper(<RagQuestionPanel projectId="project-1" />);
  expect(
    (await screen.findAllByText("INSUFFICIENT EVIDENCE")).length,
  ).toBeGreaterThan(0);
  expect(
    screen.getByText(/No citations were accepted because/),
  ).toBeInTheDocument();
});

it("shows question history and reopens a result", async () => {
  const older = question({
    id: "question-older",
    question: "Older supported question",
  });
  const failed = question({
    id: "question-failed",
    question: "Provider failure question",
    status: "FAILED",
    answer: null,
    error_message: "Synthetic provider failure.",
  });
  mockResponses({ body: [failed, older] });
  wrapper(<RagQuestionPanel projectId="project-1" />);
  expect(
    await screen.findByText("Synthetic provider failure."),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: /Older supported question/ }),
  );
  expect(screen.getByText(/8.4 mm\/s RMS, above expected/)).toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /Older supported question/ }),
    ).toHaveAttribute("aria-pressed", "true"),
  );
});

it("shows a controlled API submission error", async () => {
  mockResponses(
    { body: [] },
    { body: { detail: "RAG provider is unavailable." }, status: 503 },
  );
  wrapper(<RagQuestionPanel projectId="project-1" />);
  fireEvent.change(
    await screen.findByPlaceholderText("What abnormal condition was detected?"),
    { target: { value: "Can this be answered?" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Ask AssureAI" }));
  expect(
    await screen.findByText("RAG provider is unavailable."),
  ).toBeInTheDocument();
});
