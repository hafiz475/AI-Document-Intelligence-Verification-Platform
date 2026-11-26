import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

const project = {
  id: "project-1",
  name: "Wind Farm Alpha",
  description: "Synthetic inspection workspace",
  document_count: 1,
  current_role: "OWNER",
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
  mock.mockResolvedValueOnce(
    response({
      id: "user-1",
      external_subject: "test-owner",
      email: "owner@example.test",
      display_name: "Test Owner",
    }),
  );
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

it("shows the development sign-in screen when the session is missing", async () => {
  const mock = vi.fn<typeof fetch>().mockResolvedValueOnce(
    response(
      {
        error: {
          code: "AUTHENTICATION_REQUIRED",
          message: "Authentication is required.",
          request_id: "request-1",
        },
      },
      401,
    ),
  );
  vi.stubGlobal("fetch", mock);
  renderApp();
  expect(
    await screen.findByRole("heading", { name: "Sign in to AssureAI" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Sign in to demo" }),
  ).toBeInTheDocument();
});

it("establishes a development session without browser token storage", async () => {
  const user = {
    id: "user-1",
    external_subject: "demo-owner",
    email: null,
    display_name: "Demo Owner",
  };
  const mock = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(
      response({ detail: "Authentication is required." }, 401),
    )
    .mockResolvedValueOnce(response(user))
    .mockResolvedValueOnce(response([]));
  vi.stubGlobal("fetch", mock);
  renderApp();
  fireEvent.click(
    await screen.findByRole("button", { name: "Sign in to demo" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Projects" }),
  ).toBeInTheDocument();
  expect(mock.mock.calls[1]?.[1]).toMatchObject({
    credentials: "include",
    method: "POST",
  });
});

it("renders the create project form", async () => {
  mockResponses();
  renderApp("/projects/new");
  expect(
    await screen.findByRole("heading", { name: "Create project" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Project name")).toBeInTheDocument();
  expect(screen.getByLabelText("Description")).toBeInTheDocument();
});

it("shows the upload state after a document is selected", async () => {
  const pendingUpload = new Promise<Response>(() => undefined);
  const fetchMock = mockResponses(project, [], [], [], []);
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
  mockResponses(project, {
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
  mockResponses(project, baseDocument, [], [], [], {
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
  mockResponses(project, {
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
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
});

it("renders document operations read-only for a viewer", async () => {
  mockResponses(
    { ...project, current_role: "VIEWER" },
    { ...baseDocument, status: "READY" },
    [],
    [],
    { items: [], total: 0, limit: 100, offset: 0 },
  );
  renderApp("/projects/project-1/documents/document-1");
  expect(
    await screen.findByText("Viewer access is read-only."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Run AI Extraction" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Generate Embeddings" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Semantic Search" }),
  ).not.toBeInTheDocument();
});
