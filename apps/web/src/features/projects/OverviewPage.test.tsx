import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ProjectOverview } from "../../api/types";
import { useProject, useProjectOverview } from "../hooks";
import { OverviewPage } from "./OverviewPage";

vi.mock("../hooks", () => ({
  useProject: vi.fn(),
  useProjectOverview: vi.fn(),
}));

const emptyOverview: ProjectOverview = {
  metrics: {
    documents: 0,
    documents_ready: 0,
    documents_failed: 0,
    extraction_runs: 0,
    fields_awaiting_review: 0,
    verified_fields: 0,
    rag_questions: 0,
    supported_answers: 0,
    insufficient_evidence_answers: 0,
    evaluation_pass_rate: null,
    average_retrieval_latency_ms: null,
    average_rag_latency_ms: null,
  },
  usage: {
    extraction_tokens: null,
    rag_tokens: null,
    evaluation_tokens: null,
    total_tokens: null,
    average_provider_latency_ms: null,
    records_with_token_usage: 0,
  },
  provider_usage: [],
  recent_activity: [],
};

function arrange(overview: ProjectOverview = emptyOverview) {
  vi.mocked(useProject).mockReturnValue({
    data: {
      id: "project-1",
      name: "Industrial Equipment Inspection Demo",
      description: "Synthetic deterministic workspace",
      document_count: overview.metrics.documents,
      current_role: "OWNER",
      created_at: "2026-11-20T10:00:00Z",
      updated_at: "2026-11-20T10:00:00Z",
    },
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useProjectOverview).mockReturnValue({
    data: overview,
    isLoading: false,
    isError: false,
  } as never);
  return render(
    <MemoryRouter initialEntries={["/app/projects/project-1/overview"]}>
      <Routes>
        <Route
          path="/app/projects/:projectId/overview"
          element={<OverviewPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

it("shows a zero-data dashboard and keeps unmeasured values unknown", () => {
  arrange();
  expect(
    screen.getByText("Industrial Equipment Inspection Demo"),
  ).toBeInTheDocument();
  expect(screen.getAllByText("Unknown").length).toBeGreaterThanOrEqual(6);
  expect(
    screen.getByRole("heading", { name: "No activity yet" }),
  ).toBeInTheDocument();
});

it("renders persisted mixed-status aggregates and usage", () => {
  arrange({
    ...emptyOverview,
    metrics: {
      ...emptyOverview.metrics,
      documents: 3,
      documents_ready: 2,
      documents_failed: 1,
      extraction_runs: 4,
      fields_awaiting_review: 7,
      verified_fields: 5,
      rag_questions: 2,
      supported_answers: 1,
      insufficient_evidence_answers: 1,
      evaluation_pass_rate: 0.75,
      average_retrieval_latency_ms: 9,
      average_rag_latency_ms: 18,
    },
    usage: {
      extraction_tokens: 100,
      rag_tokens: 40,
      evaluation_tokens: 60,
      total_tokens: 200,
      average_provider_latency_ms: 12,
      records_with_token_usage: 4,
    },
  });
  expect(screen.getByText("75.0%")).toBeInTheDocument();
  expect(screen.getByText("200")).toBeInTheDocument();
  expect(screen.getByText("18 ms")).toBeInTheDocument();
});

it("makes onboarding dismissible and resumable", () => {
  const view = arrange();
  expect(
    screen.getByRole("heading", { name: "Your path to a verified answer" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dismiss guide" }));
  expect(
    screen.queryByRole("heading", { name: "Your path to a verified answer" }),
  ).not.toBeInTheDocument();
  view.unmount();
  arrange();
  expect(
    screen.queryByRole("heading", { name: "Your path to a verified answer" }),
  ).not.toBeInTheDocument();
});
