const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "http://localhost:8000";

function errorMessage(payload: unknown, fallback: string): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "error" in payload &&
    typeof payload.error === "object" &&
    payload.error !== null &&
    "message" in payload.error &&
    typeof payload.error.message === "string"
  )
    return payload.error.message;
  if (typeof payload !== "object" || payload === null || !("detail" in payload))
    return fallback;
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (
    typeof detail === "object" &&
    detail !== null &&
    "message" in detail &&
    typeof detail.message === "string"
  ) {
    return detail.message;
  }
  return fallback;
}

function errorField(
  payload: unknown,
  field: "code" | "request_id",
): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "error" in payload &&
    typeof payload.error === "object" &&
    payload.error !== null &&
    field in payload.error
  ) {
    const envelope = payload.error as Record<string, unknown>;
    const value = envelope[field];
    return typeof value === "string" ? value : null;
  }
  return null;
}

export class ApiError extends Error {
  readonly category: string;
  readonly requestId: string | null;
  readonly status: number;
  readonly timestamp: string;

  constructor(
    message: string,
    status: number,
    code: string | null,
    requestId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
    this.timestamp = new Date().toISOString();
    this.category =
      code?.includes("AUTH") || status === 401 || status === 403
        ? "AUTHORIZATION"
        : code?.includes("CITATION")
          ? "CITATION_VALIDATION"
          : code?.includes("RAG")
            ? "RAG_PROVIDER"
            : code?.includes("EMBED")
              ? "EMBEDDING_PROVIDER"
              : code?.includes("RETRIEV")
                ? "RETRIEVAL"
                : code?.includes("EVALUATION")
                  ? "EVALUATION"
                  : status === 400 || status === 413 || status === 422
                    ? "UPLOAD_VALIDATION"
                    : status >= 500
                      ? "INTERNAL"
                      : (code ?? "DOCUMENT_PROCESSING");
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
  });
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(
      errorMessage(payload, `Request failed with status ${response.status}`),
      response.status,
      errorField(payload, "code"),
      errorField(payload, "request_id") ?? response.headers.get("x-request-id"),
    );
  }
  return response.json() as Promise<T>;
}
