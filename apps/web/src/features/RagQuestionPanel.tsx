import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import type { RagQuestion, RagSupportStatus } from "../api/types";
import { ErrorState, LoadingState, StatusBadge } from "../components/States";
import { useCreateRagQuestion, useRagQuestions } from "./hooks";

function supportLabel(status: RagSupportStatus) {
  return status.replaceAll("_", " ");
}

function SupportBadge({ status }: { status: RagSupportStatus }) {
  return (
    <span className={"status status-" + status.toLowerCase()}>
      {supportLabel(status)}
    </span>
  );
}

function AnswerView({
  question,
  projectId,
}: {
  question: RagQuestion;
  projectId: string;
}) {
  if (question.status === "FAILED") {
    return (
      <div className="state-card error" role="alert">
        <h3>Question processing failed</h3>
        <p>
          {question.error_message ||
            "AssureAI could not produce a validated grounded answer."}
        </p>
      </div>
    );
  }
  if (["QUEUED", "PROCESSING"].includes(question.status)) {
    return (
      <LoadingState
        label={
          question.status === "QUEUED"
            ? "Question queued for grounded processing…"
            : "Retrieving evidence and validating citations…"
        }
      />
    );
  }
  if (!question.answer) return null;
  const answer = question.answer;

  return (
    <article className="rag-answer" aria-live="polite">
      <header>
        <div>
          <p className="eyebrow">Evidence-backed answer</p>
          <h3>{question.question}</h3>
        </div>
        <SupportBadge status={answer.support_status} />
      </header>
      <p className="answer-text">{answer.answer_text}</p>
      <p className="search-metadata">
        {question.provider} · {question.model} · prompt v
        {question.prompt_version.version}
        {question.latency_ms !== null
          ? " · " + question.latency_ms + " ms"
          : ""}
      </p>

      <section className="rag-citations" aria-labelledby="citation-heading">
        <h4 id="citation-heading">Validated citations</h4>
        {answer.citations.length ? (
          <ol>
            {answer.citations.map((citation) => (
              <li key={citation.id}>
                <details>
                  <summary>
                    {citation.document_name}
                    {citation.page_number !== null
                      ? " · page " + citation.page_number
                      : " · page unavailable"}
                    {" · rank " +
                      citation.rank +
                      " · similarity " +
                      citation.similarity_score.toFixed(4)}
                  </summary>
                  <blockquote>{citation.quote}</blockquote>
                  <Link
                    to={`/app/projects/${projectId}/documents/${citation.document_id}?tab=chunks#chunk-${citation.chunk_id}`}
                  >
                    Open exact source evidence
                  </Link>
                </details>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">
            No citations were accepted because the available evidence was
            insufficient.
          </p>
        )}
      </section>

      <details className="retrieved-sources">
        <summary>Inspect all retrieved sources</summary>
        {question.retrieved_sources.length ? (
          <ol>
            {question.retrieved_sources.map((source) => (
              <li key={source.chunk_id}>
                <header>
                  <strong>
                    {source.rank}. {source.document_name}
                  </strong>
                  <span>
                    {source.page_number !== null
                      ? "Page " + source.page_number
                      : "Page unavailable"}
                    {" · " + source.similarity_score.toFixed(4)}
                  </span>
                </header>
                <p>{source.content}</p>
                <code>{source.chunk_id}</code>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No evidence chunks were retrieved.</p>
        )}
      </details>
    </article>
  );
}

export function RagQuestionPanel({
  projectId,
  documentId,
}: {
  projectId: string;
  documentId?: string;
}) {
  const [questionText, setQuestionText] = useState("");
  const [topK, setTopK] = useState(5);
  const [supportStatus, setSupportStatus] = useState<RagSupportStatus | "">("");
  const [documentFilter, setDocumentFilter] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const questions = useRagQuestions(
    projectId,
    (documentId ?? documentFilter) || undefined,
    {
      supportStatus,
      createdFrom: createdFrom || undefined,
      createdTo: createdTo ? `${createdTo}T23:59:59Z` : undefined,
      limit: 26,
      offset,
    },
  );
  const create = useCreateRagQuestion(projectId, documentId);

  const selected =
    questions.data?.find((question) => question.id === selectedId) ??
    questions.data?.[0];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = questionText.trim();
    if (!value) return;
    create.mutate(
      { question: value, topK },
      {
        onSuccess: (created) => {
          setSelectedId(created.id);
          setQuestionText("");
        },
      },
    );
  }

  return (
    <section className="rag-panel" aria-labelledby="rag-heading">
      <div className="section-heading">
        <div>
          <h2 id="rag-heading">Ask AssureAI</h2>
          <p>
            Answers are generated only from retrieved project evidence and
            validated citations.
          </p>
        </div>
      </div>
      <form className="rag-form" onSubmit={submit}>
        <label>
          Question
          <textarea
            onChange={(event) => setQuestionText(event.target.value)}
            placeholder="What abnormal condition was detected?"
            required
            rows={3}
            value={questionText}
          />
        </label>
        <label>
          Sources
          <input
            aria-label="Maximum retrieved sources"
            max={10}
            min={1}
            onChange={(event) => setTopK(Number(event.target.value))}
            type="number"
            value={topK}
          />
        </label>
        <button disabled={create.isPending} type="submit">
          {create.isPending ? "Submitting…" : "Ask AssureAI"}
        </button>
      </form>
      {create.isError && <ErrorState error={create.error} />}
      <div className="filter-bar" aria-label="Question history filters">
        <label>
          Support status
          <select
            value={supportStatus}
            onChange={(event) => {
              setSupportStatus(event.target.value as RagSupportStatus | "");
              setOffset(0);
            }}
          >
            <option value="">All answers</option>
            <option value="SUPPORTED">SUPPORTED</option>
            <option value="PARTIALLY_SUPPORTED">PARTIALLY SUPPORTED</option>
            <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT EVIDENCE</option>
          </select>
        </label>
        {!documentId && (
          <label>
            Document ID
            <input
              value={documentFilter}
              onChange={(event) => {
                setDocumentFilter(event.target.value);
                setOffset(0);
              }}
              placeholder="All documents"
            />
          </label>
        )}
        <label>
          From
          <input
            type="date"
            value={createdFrom}
            onChange={(event) => {
              setCreatedFrom(event.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={createdTo}
            onChange={(event) => {
              setCreatedTo(event.target.value);
              setOffset(0);
            }}
          />
        </label>
      </div>
      {questions.isLoading && (
        <LoadingState label="Loading question history…" />
      )}
      {questions.isError && <ErrorState error={questions.error} />}
      {selected && <AnswerView projectId={projectId} question={selected} />}

      <div className="question-history">
        <h3>Question history</h3>
        {questions.data?.length ? (
          <ol>
            {questions.data.slice(0, 25).map((question) => (
              <li key={question.id}>
                <button
                  aria-pressed={selected?.id === question.id}
                  className="history-button"
                  onClick={() => setSelectedId(question.id)}
                  type="button"
                >
                  <span>{question.question}</span>
                  <span>
                    {question.answer ? (
                      <SupportBadge status={question.answer.support_status} />
                    ) : (
                      <StatusBadge status={question.status} />
                    )}
                    <time dateTime={question.created_at}>
                      {new Date(question.created_at).toLocaleString()}
                    </time>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        ) : (
          !questions.isLoading && (
            <p className="muted">No questions have been asked yet.</p>
          )
        )}
        {questions.data && (offset > 0 || questions.data.length > 25) && (
          <div className="pagination">
            <button
              className="button secondary"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 25))}
            >
              Previous
            </button>
            <span>
              Questions {offset + 1}–
              {offset + Math.min(25, questions.data.length)}
            </span>
            <button
              className="button secondary"
              disabled={questions.data.length <= 25}
              onClick={() => setOffset(offset + 25)}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
