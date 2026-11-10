import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

const project = {
  id: "project-1",
  name: "Wind Farm Alpha",
  description: "Synthetic inspection workspace",
  document_count: 1,
  created_at: "2026-11-06T10:00:00Z",
  updated_at: "2026-11-06T10:00:00Z",
};

const baseDocument = {
  id: "document-1",
  project_id: "project-1",
  filename: "inspection.txt",
  mime_type: "text/plain",
  file_size: 120,
  sha256_hash: "abc",
  status: "READY",
  page_count: null,
  character_count: 120,
  processing_error: null,
  created_at: "2026-11-06T10:00:00Z",
  updated_at: "2026-11-06T10:01:00Z",
  processed_at: "2026-11-06T10:01:00Z",
} as const;

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

function renderApp(path = "/") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("renders the project list", async () => {
  mockResponses([project]);
  renderApp();
  expect(
    await screen.findByRole("heading", { name: "Wind Farm Alpha" }),
  ).toBeInTheDocument();
  expect(screen.getByText("1", { selector: "dd" })).toBeInTheDocument();
});

it("renders the create project form", () => {
  renderApp("/projects/new");
  expect(
    screen.getByRole("heading", { name: "Create project" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Project name")).toBeInTheDocument();
  expect(screen.getByLabelText("Description")).toBeInTheDocument();
});

it("shows the upload state after a document is selected", async () => {
  const pendingUpload = new Promise<Response>(() => undefined);
  const fetchMock = mockResponses(project, [], []);
  fetchMock.mockReturnValueOnce(pendingUpload);
  const view = renderApp("/projects/project-1");
  await screen.findByRole("heading", { name: "Wind Farm Alpha" });
  const input =
    view.container.querySelector<HTMLInputElement>('input[type="file"]');
  expect(input).not.toBeNull();
  fireEvent.change(input!, {
    target: {
      files: [new File(["report"], "report.txt", { type: "text/plain" })],
    },
  });
  expect(
    await screen.findByRole("button", { name: "Uploading…" }),
  ).toBeDisabled();
});

it("shows a processing state", async () => {
  mockResponses({
    ...baseDocument,
    status: "PROCESSING",
    character_count: null,
    processed_at: null,
  });
  renderApp("/projects/project-1/documents/document-1");
  expect(
    await screen.findByText("Extracting and chunking document…"),
  ).toBeInTheDocument();
  expect(screen.getByText("PROCESSING")).toBeInTheDocument();
});

it("shows extracted chunks for a ready document", async () => {
  mockResponses(baseDocument, [], [], {
    items: [
      {
        id: "chunk-1",
        document_id: "document-1",
        chunk_index: 0,
        page_number: null,
        section: "Text",
        content: "Blade condition is acceptable.",
        character_count: 30,
        metadata: {},
        created_at: "2026-11-06T10:01:00Z",
      },
    ],
    total: 1,
    limit: 100,
    offset: 0,
  });
  renderApp("/projects/project-1/documents/document-1");
  expect(
    await screen.findByText("Blade condition is acceptable."),
  ).toBeInTheDocument();
  expect(screen.getByText("READY")).toBeInTheDocument();
});

it("shows a safe failed state", async () => {
  mockResponses({
    ...baseDocument,
    status: "FAILED",
    processing_error: "The document could not be parsed.",
  });
  renderApp("/projects/project-1/documents/document-1");
  expect(
    await screen.findByRole("heading", { name: "Processing failed" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("The document could not be parsed."),
  ).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
});
