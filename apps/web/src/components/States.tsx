import type { DocumentStatus } from "../api/types";

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

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={`status status-${status.toLowerCase()}`}>{status}</span>
  );
}
