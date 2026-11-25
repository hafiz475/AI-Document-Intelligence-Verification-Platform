import { FormEvent, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type {
  EvaluationCase,
  EvaluationRun,
  EvaluationType,
} from "../../api/types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
} from "../../components/States";
import {
  useCompareEvaluationRuns,
  useCreateEvaluationDataset,
  useCreateEvaluationRun,
  useEvaluationDatasets,
  useEvaluationRuns,
  useSaveEvaluationCase,
} from "../hooks";

const templates: Record<EvaluationType, { input: object; expected: object }> = {
  EXTRACTION: {
    input: { document_id: "" },
    expected: { expected_fields: { asset_id: "WT-204" } },
  },
  RETRIEVAL: {
    input: { query: "", document_id: null },
    expected: { expected_chunk_ids: [], expected_document_ids: [] },
  },
  RAG: {
    input: { question: "", document_id: null },
    expected: {
      support_status: "SUPPORTED",
      required_citation_chunk_ids: [],
      forbidden_citation_chunk_ids: [],
      required_phrases: [],
      forbidden_phrases: [],
    },
  },
};

const pretty = (value: unknown) => JSON.stringify(value, null, 2);
const label = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const metric = (value: unknown) => {
  if (value === null) return "-";
  if (typeof value !== "number") {
    return typeof value === "string" || typeof value === "boolean"
      ? String(value)
      : pretty(value);
  }
  return value >= 0 && value <= 1
    ? `${(value * 100).toFixed(1)}%`
    : value.toFixed(1);
};

function RunMetrics({ run }: { run: EvaluationRun }) {
  return (
    <section aria-label={`${run.evaluation_type} metrics`}>
      <h3>{run.evaluation_type} metrics</h3>
      <div className="evaluation-metrics">
        {Object.entries(run.aggregate_metrics_json).map(([name, value]) => (
          <div key={name}>
            <strong>{metric(value)}</strong>
            <span>{label(name)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function CaseEditor({
  projectId,
  datasetId,
  evaluationType,
  editing,
  onDone,
}: {
  projectId: string;
  datasetId: string;
  evaluationType: EvaluationType;
  editing: EvaluationCase | null;
  onDone: () => void;
}) {
  const save = useSaveEvaluationCase(projectId);
  const [name, setName] = useState(editing?.name ?? "");
  const [input, setInput] = useState(
    pretty(editing?.input_json ?? templates[evaluationType].input),
  );
  const [expected, setExpected] = useState(
    pretty(editing?.expected_json ?? templates[evaluationType].expected),
  );
  const [parseError, setParseError] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      save.mutate(
        {
          datasetId,
          caseId: editing?.id,
          payload: {
            name,
            input_json: JSON.parse(input) as Record<string, unknown>,
            expected_json: JSON.parse(expected) as Record<string, unknown>,
            metadata_json: editing?.metadata_json ?? {},
          },
        },
        { onSuccess: onDone },
      );
      setParseError("");
    } catch {
      setParseError("Input and expected values must be valid JSON objects.");
    }
  }

  return (
    <form className="evaluation-form" onSubmit={submit}>
      <h3>{editing ? "Edit evaluation case" : "Add evaluation case"}</h3>
      <label>
        Case name
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label>
        Input JSON
        <textarea
          rows={7}
          value={input}
          onChange={(event) => setInput(event.target.value)}
        />
      </label>
      <label>
        Expected JSON
        <textarea
          rows={8}
          value={expected}
          onChange={(event) => setExpected(event.target.value)}
        />
      </label>
      {(parseError || save.isError) && (
        <p className="error-text" role="alert">
          {parseError || save.error?.message}
        </p>
      )}
      <div className="form-actions">
        {editing && (
          <button className="button secondary" onClick={onDone} type="button">
            Cancel edit
          </button>
        )}
        <button className="button" disabled={save.isPending}>
          {save.isPending ? "Saving..." : "Save case"}
        </button>
      </div>
    </form>
  );
}

export function EvaluationsPage() {
  const { projectId = "" } = useParams();
  const datasets = useEvaluationDatasets(projectId);
  const runs = useEvaluationRuns(projectId);
  const createDataset = useCreateEvaluationDataset(projectId);
  const createRun = useCreateEvaluationRun(projectId);
  const comparison = useCompareEvaluationRuns(projectId);
  const [datasetId, setDatasetId] = useState("");
  const [runId, setRunId] = useState("");
  const [editing, setEditing] = useState<EvaluationCase | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [datasetType, setDatasetType] = useState<EvaluationType>("EXTRACTION");
  const [topK, setTopK] = useState(5);
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");

  const activeDatasetId = datasetId || datasets.data?.[0]?.id || "";
  const dataset = datasets.data?.find((item) => item.id === activeDatasetId);
  const run = runs.data?.find((item) => item.id === runId);
  const completed =
    runs.data?.filter((item) => item.status === "COMPLETED") ?? [];
  const filteredRuns = useMemo(
    () =>
      runs.data?.filter(
        (item) =>
          (!typeFilter || item.evaluation_type === typeFilter) &&
          (!statusFilter || item.status === statusFilter) &&
          (!modelFilter ||
            `${item.provider}/${item.model}/${item.prompt_version_id ?? ""}`
              .toLowerCase()
              .includes(modelFilter.toLowerCase())),
      ) ?? [],
    [runs.data, typeFilter, statusFilter, modelFilter],
  );

  if (datasets.isLoading || runs.isLoading)
    return <LoadingState label="Loading evaluations..." />;
  if (datasets.isError) return <ErrorState error={datasets.error} />;
  if (runs.isError) return <ErrorState error={runs.error} />;

  return (
    <section>
      <Link className="back-link" to={`/projects/${projectId}`}>
        Back to project
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Milestone 5</p>
          <h1>Evaluations</h1>
          <p>
            Measured, versioned quality for extraction, retrieval, and grounded
            answers.
          </p>
        </div>
      </div>

      <div className="evaluation-grid">
        <form
          className="evaluation-card evaluation-form"
          onSubmit={(event) => {
            event.preventDefault();
            createDataset.mutate(
              { name: datasetName, evaluation_type: datasetType },
              {
                onSuccess: (created) => {
                  setDatasetName("");
                  setDatasetId(created.id);
                },
              },
            );
          }}
        >
          <h2>Create dataset</h2>
          <label>
            Dataset name
            <input
              required
              value={datasetName}
              onChange={(event) => setDatasetName(event.target.value)}
            />
          </label>
          <label>
            Evaluation type
            <select
              value={datasetType}
              onChange={(event) =>
                setDatasetType(event.target.value as EvaluationType)
              }
            >
              <option value="EXTRACTION">Extraction</option>
              <option value="RETRIEVAL">Retrieval</option>
              <option value="RAG">RAG</option>
            </select>
          </label>
          <button className="button" disabled={createDataset.isPending}>
            Create dataset
          </button>
          {createDataset.isError && <ErrorState error={createDataset.error} />}
        </form>

        <section className="evaluation-card">
          <h2>Datasets</h2>
          {datasets.data?.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Cases</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.data.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <button
                          className="link-button"
                          onClick={() => setDatasetId(item.id)}
                          type="button"
                        >
                          {item.name}
                        </button>
                      </td>
                      <td>{item.evaluation_type}</td>
                      <td>{item.case_count}</td>
                      <td>{new Date(item.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No evaluation datasets"
              detail="Create a typed dataset to begin."
            />
          )}
        </section>
      </div>

      {dataset && (
        <section className="evaluation-card">
          <div className="section-heading">
            <div>
              <h2>{dataset.name}</h2>
              <p>{dataset.evaluation_type} dataset detail</p>
            </div>
            <strong>{dataset.case_count} / 200 cases</strong>
          </div>
          {dataset.cases.length ? (
            <div className="case-list">
              {dataset.cases.map((item) => (
                <details key={item.id}>
                  <summary>{item.name}</summary>
                  <div className="case-json-grid">
                    <div>
                      <h4>Input</h4>
                      <pre>{pretty(item.input_json)}</pre>
                    </div>
                    <div>
                      <h4>Expected</h4>
                      <pre>{pretty(item.expected_json)}</pre>
                    </div>
                  </div>
                  <button
                    className="button secondary"
                    onClick={() => setEditing(item)}
                    type="button"
                  >
                    Edit case
                  </button>
                </details>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No cases"
              detail="Add the first typed case below."
            />
          )}
          <CaseEditor
            key={`${dataset.id}:${editing?.id ?? "new"}`}
            projectId={projectId}
            datasetId={dataset.id}
            evaluationType={dataset.evaluation_type}
            editing={editing}
            onDone={() => setEditing(null)}
          />
        </section>
      )}

      <section className="evaluation-card">
        <h2>Create evaluation run</h2>
        <form
          className="inline-evaluation-form"
          onSubmit={(event) => {
            event.preventDefault();
            createRun.mutate(
              { dataset_id: activeDatasetId, top_k: topK },
              { onSuccess: (created) => setRunId(created.id) },
            );
          }}
        >
          <label>
            Dataset
            <select
              required
              value={activeDatasetId}
              onChange={(event) => setDatasetId(event.target.value)}
            >
              <option value="">Select dataset</option>
              {datasets.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Top K
            <input
              min={1}
              max={20}
              type="number"
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
          </label>
          <button
            className="button"
            disabled={!activeDatasetId || createRun.isPending}
          >
            {createRun.isPending ? "Queueing..." : "Run evaluation"}
          </button>
        </form>
        <p className="search-metadata">
          Provider, model, prompt, embeddings, workflow, and evaluator v1 are
          captured automatically.
        </p>
        {createRun.isError && <ErrorState error={createRun.error} />}
      </section>

      <section className="evaluation-card">
        <h2>Evaluation history</h2>
        <div
          className="evaluation-filters"
          aria-label="Evaluation history filters"
        >
          <select
            aria-label="Filter by evaluation type"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="">All types</option>
            <option>EXTRACTION</option>
            <option>RETRIEVAL</option>
            <option>RAG</option>
          </select>
          <select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All statuses</option>
            <option>QUEUED</option>
            <option>PROCESSING</option>
            <option>COMPLETED</option>
            <option>FAILED</option>
          </select>
          <input
            aria-label="Filter by provider, model, or prompt"
            placeholder="Provider, model, or prompt"
            value={modelFilter}
            onChange={(event) => setModelFilter(event.target.value)}
          />
        </div>
        {filteredRuns.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Provider / model</th>
                  <th>Pass</th>
                  <th>Score</th>
                  <th>Latency</th>
                  <th>Tokens</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <button
                        className="link-button"
                        onClick={() => setRunId(item.id)}
                        type="button"
                      >
                        {item.evaluation_type}
                      </button>
                    </td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td>
                      {item.provider} / {item.model}
                    </td>
                    <td>
                      {item.passed_cases}/{item.total_cases}
                    </td>
                    <td>{metric(item.average_score)}</td>
                    <td>
                      {item.average_latency_ms === null
                        ? "-"
                        : `${item.average_latency_ms.toFixed(0)} ms`}
                    </td>
                    <td>{item.total_tokens ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No matching runs"
            detail="Create a run or adjust filters."
          />
        )}
      </section>

      {run && (
        <section className="evaluation-card" aria-label="Run detail">
          <div className="section-heading">
            <h2>Run detail</h2>
            <StatusBadge status={run.status} />
          </div>
          {["QUEUED", "PROCESSING"].includes(run.status) ? (
            <p className="notice" role="status">
              Evaluation is processing sequentially...
            </p>
          ) : run.status === "FAILED" ? (
            <ErrorState
              error={new Error(run.error_message ?? "Evaluation failed.")}
            />
          ) : (
            <RunMetrics run={run} />
          )}
          <dl className="provenance-list">
            <div>
              <dt>Evaluator</dt>
              <dd>{run.evaluator_version}</dd>
            </div>
            <div>
              <dt>Prompt</dt>
              <dd>{run.prompt_version_id ?? "Not applicable"}</dd>
            </div>
            <div>
              <dt>Embedding</dt>
              <dd>
                {run.embedding_provider
                  ? `${run.embedding_provider} / ${run.embedding_model}`
                  : "Not applicable"}
              </dd>
            </div>
            <div>
              <dt>Errors</dt>
              <dd>{run.error_cases}</dd>
            </div>
          </dl>
          <div className="case-list">
            {run.case_results.map((result) => (
              <details key={result.id}>
                <summary>
                  {typeof result.case_snapshot_json.name === "string"
                    ? result.case_snapshot_json.name
                    : "Case"}{" "}
                  - {result.status}
                </summary>
                <p>
                  {result.latency_ms} ms -{" "}
                  {result.total_tokens ?? "No token data"} tokens
                </p>
                {result.error_message && (
                  <p className="error-text">{result.error_message}</p>
                )}
                <div className="case-json-grid">
                  <div>
                    <h4>Expected</h4>
                    <pre>{pretty(result.case_snapshot_json.expected)}</pre>
                  </div>
                  <div>
                    <h4>Actual</h4>
                    <pre>{pretty(result.actual_output_json)}</pre>
                  </div>
                  <div>
                    <h4>Metrics</h4>
                    <pre>{pretty(result.metrics_json)}</pre>
                  </div>
                </div>
              </details>
            ))}
          </div>
        </section>
      )}

      <section className="evaluation-card">
        <h2>Compare completed runs</h2>
        <form
          className="inline-evaluation-form"
          onSubmit={(event) => {
            event.preventDefault();
            comparison.mutate({ runAId: runA, runBId: runB });
          }}
        >
          <label>
            Run A
            <select
              required
              value={runA}
              onChange={(event) => setRunA(event.target.value)}
            >
              <option value="">Select</option>
              {completed.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.evaluation_type} - {item.model} - {item.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Run B
            <select
              required
              value={runB}
              onChange={(event) => setRunB(event.target.value)}
            >
              <option value="">Select</option>
              {completed.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.evaluation_type} - {item.model} - {item.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button"
            disabled={!runA || !runB || comparison.isPending}
          >
            Compare runs
          </button>
        </form>
        {comparison.isError && <ErrorState error={comparison.error} />}
        {comparison.data && (
          <div>
            <p
              className={`comparison-status ${comparison.data.status.toLowerCase()}`}
            >
              Regression status: {comparison.data.status}
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Run A</th>
                    <th>Run B</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.data.metrics.map((item) => (
                    <tr key={item.metric}>
                      <td>{label(item.metric)}</td>
                      <td>{metric(item.run_a)}</td>
                      <td>{metric(item.run_b)}</td>
                      <td>
                        {item.delta === null
                          ? "-"
                          : `${item.delta > 0 ? "+" : ""}${item.delta.toFixed(3)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </section>
  );
}
