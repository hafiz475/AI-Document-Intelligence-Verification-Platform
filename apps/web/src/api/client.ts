const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "http://localhost:8000";

function errorMessage(payload: unknown, fallback: string): string {
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

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(
      errorMessage(payload, `Request failed with status ${response.status}`),
    );
  }
  return response.json() as Promise<T>;
}
