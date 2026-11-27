export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="state-card" role="status">
      {label}
    </p>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message =
    error instanceof Error ? error.message : "Something went wrong.";
  if (error instanceof ApiError) {
    return (
      <div className="state-card error" role="alert">
        <h2>{error.category.replaceAll("_", " ")}</h2>
        <p>{message}</p>
        <small>
          Request ID: {error.requestId ?? "Not available"} ·{" "}
          {new Date(error.timestamp).toLocaleString()}
        </small>
        <p>
          Recommended next step: verify access and input, then retry. Contact an
          operator with the request ID if the failure persists.
        </p>
      </div>
    );
  }
  return (
    <p className="state-card error" role="alert">
      {message}
    </p>
  );
}

export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="state-card">
      <h2>{title}</h2>
      <p>{detail}</p>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`status status-${status.toLowerCase()}`}>{status}</span>
  );
}
import { ApiError } from "../api/client";
