import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { ExtractionRun } from "../../api/types";
import { useDocumentChunks, useExtractions, useReviewField } from "../hooks";
import { EvidenceReview } from "./EvidenceReview";

vi.mock("../hooks", () => ({
  useDocumentChunks: vi.fn(),
  useExtractions: vi.fn(),
  useReviewField: vi.fn(),
}));

const run: ExtractionRun = {
  id: "run-1",
  project_id: "project-1",
  document_id: "document-1",
  status: "COMPLETED",
  provider: "development",
  model: "deterministic-development-v1",
  prompt_version: {
    id: "prompt-1",
    version: 1,
    schema_version: "inspection-v1",
    created_at: "2026-11-20T10:00:00Z",
  },
  started_at: "2026-11-20T10:00:00Z",
  completed_at: "2026-11-20T10:00:01Z",
  latency_ms: 10,
  input_tokens: 50,
  output_tokens: 20,
  error_code: null,
  error_message: null,
  fields: [
    {
      id: "field-1",
      extraction_run_id: "run-1",
      document_id: "document-1",
      field_name: "abnormal_vibration",
      field_type: "string",
      raw_value: "8.4 mm/s",
      normalized_value: "8.4 mm/s",
      missing_reason: null,
      corrected_value: "8.4 mm/s RMS",
      review_status: "CORRECTED",
      support_status: "SUPPORTED",
      review_reason: "Kept the unit qualifier from the source.",
      reviewer: "Demo Owner",
      reviewed_at: "2026-11-20T10:05:00Z",
      evidence: [
        {
          id: "evidence-1",
          document_chunk_id: "chunk-1",
          page_number: null,
          quote: "vibration measured 8.4 mm/s RMS",
          created_at: "2026-11-20T10:00:01Z",
        },
      ],
      created_at: "2026-11-20T10:00:01Z",
      updated_at: "2026-11-20T10:05:00Z",
    },
  ],
  audit_events: [],
  created_at: "2026-11-20T10:00:00Z",
  updated_at: "2026-11-20T10:05:00Z",
};

const chunks = {
  items: [
    {
      id: "chunk-1",
      document_id: "document-1",
      chunk_index: 0,
      page_number: null,
      section: "Inspection finding",
      content:
        "Drive-end bearing vibration measured 8.4 mm/s RMS during the loaded test.",
      character_count: 76,
      metadata: {},
      created_at: "2026-11-20T10:00:00Z",
    },
  ],
  total: 1,
  limit: 100,
  offset: 0,
};

function arrange(chunkData: typeof chunks = chunks) {
  vi.mocked(useExtractions).mockReturnValue({
    data: [run],
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useDocumentChunks).mockReturnValue({
    data: chunkData,
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useReviewField).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as never);
  return render(
    <MemoryRouter initialEntries={["/?tab=evidence"]}>
      <EvidenceReview
        canEdit
        documentId="document-1"
        mimeType="text/plain"
        projectId="project-1"
      />
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

it("links a field to and highlights its exact authorized evidence", () => {
  arrange();
  expect(screen.getByText("vibration measured 8.4 mm/s RMS").tagName).toBe(
    "MARK",
  );
  expect(screen.getByText("Evidence link validated")).toBeInTheDocument();
});

it("retains the original AI value after a human correction", () => {
  arrange();
  expect(screen.getByText("ORIGINAL AI VALUE")).toBeInTheDocument();
  expect(screen.getByText("8.4 mm/s")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "8.4 mm/s RMS" }),
  ).toBeInTheDocument();
});

it("does not invent a page number for TXT evidence", () => {
  arrange();
  expect(screen.getByText("Text context")).toBeInTheDocument();
  expect(screen.queryByText(/^Page /)).not.toBeInTheDocument();
});

it("does not render evidence from a different document chunk", () => {
  arrange({
    ...chunks,
    items: [
      { ...chunks.items[0]!, id: "foreign-chunk", document_id: "document-2" },
    ],
  });
  expect(
    screen.getByText(/authorized source context is unavailable/i),
  ).toBeInTheDocument();
  expect(screen.queryByText(/Drive-end bearing/)).not.toBeInTheDocument();
});

it("keeps review actions inaccessible after the field is already reviewed", () => {
  arrange();
  fireEvent.click(screen.getByRole("button", { name: /abnormal vibration/i }));
  expect(
    screen.queryByRole("button", { name: "Verify field" }),
  ).not.toBeInTheDocument();
});
