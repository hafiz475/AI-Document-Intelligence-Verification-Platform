import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ExtractedField, ExtractionRun } from "../../api/types";
import { ExtractionPanel } from "./ExtractionPanel";

const evidence = {
  id: "evidence-1",
  document_chunk_id: "chunk-1",
  page_number: 2,
  quote: "Asset ID: WT-204",
  created_at: "2026-11-07T10:01:00Z",
};

function field(overrides: Partial<ExtractedField> = {}): ExtractedField {
  return {
    id: "field-1",
    extraction_run_id: "run-1",
    document_id: "document-1",
    field_name: "asset_id",
    field_type: "string",
    raw_value: "WT-204",
    normalized_value: "WT-204",
    missing_reason: null,
    corrected_value: null,
    review_status: "UNREVIEWED",
    support_status: "SUPPORTED",
    review_reason: null,
    reviewer: null,
    reviewed_at: null,
    evidence: [evidence],
    created_at: "2026-11-07T10:01:00Z",
    updated_at: "2026-11-07T10:01:00Z",
    ...overrides,
  };
}

function run(overrides: Partial<ExtractionRun> = {}): ExtractionRun {
  return {
    id: "run-1",
    project_id: "project-1",
    document_id: "document-1",
    status: "COMPLETED",
    provider: "development",
    model: "deterministic-development-v1",
    prompt_version: {
      id: "prompt-1",
      version: 1,
      schema_version: "inspection-extraction-v1",
      created_at: "2026-11-07T10:00:00Z",
    },
    started_at: "2026-11-07T10:00:01Z",
    completed_at: "2026-11-07T10:00:02Z",
    latency_ms: 1,
    input_tokens: 100,
    output_tokens: 50,
    error_code: null,
    error_message: null,
    fields: [field()],
    audit_events: [],
    created_at: "2026-11-07T10:00:00Z",
    updated_at: "2026-11-07T10:00:02Z",
    ...overrides,
  };
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockResponses(...bodies: unknown[]) {
  const mock = vi.fn<typeof fetch>();
  for (const body of bodies) mock.mockResolvedValueOnce(response(body));
  vi.stubGlobal("fetch", mock);
  return mock;
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ExtractionPanel documentId="document-1" projectId="project-1" />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("starts an extraction and renders the queued state", async () => {
  const queued = run({ status: "QUEUED", fields: [] });
  mockResponses([], queued, [queued]);
  renderPanel();
  fireEvent.click(
    await screen.findByRole("button", { name: "Run AI Extraction" }),
  );
  expect(
    await screen.findByText("AI extraction queued..."),
  ).toBeInTheDocument();
});

it.each([
  ["QUEUED", "AI extraction queued..."],
  ["PROCESSING", "AI extraction processing..."],
] as const)("renders the %s state", async (status, label) => {
  mockResponses([run({ status, fields: [] })]);
  renderPanel();
  expect(await screen.findByText(label)).toBeInTheDocument();
  expect(screen.getAllByText(status).length).toBeGreaterThan(0);
});

it("renders a safe failed state", async () => {
  mockResponses([
    run({
      status: "FAILED",
      fields: [],
      error_code: "PROVIDER_ERROR",
      error_message: "Synthetic provider failure.",
    }),
  ]);
  renderPanel();
  expect(
    await screen.findByRole("heading", { name: "AI extraction failed" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Synthetic provider failure.")).toBeInTheDocument();
});

it("renders validated evidence, review badges, and extraction history", async () => {
  mockResponses([run()]);
  renderPanel();
  expect(await screen.findByText("WT-204")).toBeInTheDocument();
  expect(screen.getByText("SUPPORTED")).toBeInTheDocument();
  expect(screen.getByText("UNREVIEWED")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Evidence (1)"));
  expect(screen.getByText("Page 2")).toBeInTheDocument();
  expect(screen.getByText("Asset ID: WT-204")).toBeInTheDocument();
  expect(screen.getByText(/Run #1/)).toBeInTheDocument();
  expect(screen.getAllByText(/Prompt v1/).length).toBeGreaterThan(0);
});

it("verifies a field", async () => {
  const verified = field({ review_status: "VERIFIED" });
  mockResponses([run()], verified, [run({ fields: [verified] })]);
  renderPanel();
  fireEvent.click(await screen.findByRole("button", { name: "Verify" }));
  expect(await screen.findByText("VERIFIED")).toBeInTheDocument();
});

it("submits a correction without replacing the original display contract", async () => {
  const corrected = field({
    field_name: "model",
    raw_value: "NSR-4.2",
    normalized_value: "NSR-4.2",
    corrected_value: "NSR-4.2-CORRECTED",
    review_status: "CORRECTED",
  });
  const fetchMock = mockResponses(
    [
      run({
        fields: [
          field({
            field_name: "model",
            raw_value: "NSR-4.2",
            normalized_value: "NSR-4.2",
          }),
        ],
      }),
    ],
    corrected,
    [run({ fields: [corrected] })],
  );
  renderPanel();
  fireEvent.click(await screen.findByRole("button", { name: "Correct" }));
  fireEvent.change(screen.getByLabelText("Corrected value"), {
    target: { value: "NSR-4.2-CORRECTED" },
  });
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "Corrected from source evidence." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save correction" }));
  expect(await screen.findByText("CORRECTED")).toBeInTheDocument();
  const request = fetchMock.mock.calls[1]?.[1];
  expect(request?.body).toContain('"decision":"CORRECTED"');
});

it("rejects a field with a reason", async () => {
  const rejected = field({
    review_status: "REJECTED",
    review_reason: "Unsupported.",
  });
  const fetchMock = mockResponses([run()], rejected, [
    run({ fields: [rejected] }),
  ]);
  renderPanel();
  fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
  fireEvent.change(screen.getByLabelText("Rejection reason"), {
    target: { value: "Source does not support this value." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Confirm rejection" }));
  expect(await screen.findByText("REJECTED")).toBeInTheDocument();
  await waitFor(() => {
    expect(fetchMock.mock.calls[1]?.[1]?.body).toContain(
      '"decision":"REJECTED"',
    );
  });
});
