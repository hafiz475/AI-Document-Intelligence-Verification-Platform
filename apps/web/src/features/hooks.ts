import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createProject, getProject, getProjects } from "../api/projects";
import {
  getDocument,
  getDocumentChunks,
  getDocuments,
  uploadDocument,
} from "../api/documents";
import {
  createExtraction,
  getExtractions,
  reviewField,
} from "../api/extractions";
import {
  createEmbeddingRun,
  getEmbeddingRuns,
  getRetrievalEvaluations,
  semanticSearch,
} from "../api/retrieval";
import type { FieldReview } from "../api/types";
import { createQuestion, getQuestions } from "../api/questions";
import type { QuestionFilters } from "../api/questions";
import type { RagQuestion } from "../api/types";
import {
  compareEvaluationRuns,
  createEvaluationCase,
  createEvaluationDataset,
  createEvaluationRun,
  getEvaluationDatasets,
  getEvaluationRuns,
  updateEvaluationCase,
} from "../api/evaluations";
import type { CaseInput, DatasetInput, RunInput } from "../api/evaluations";
import type { EvaluationRunFilters } from "../api/evaluations";
import {
  getAuditIndex,
  getDocumentIndex,
  getDocumentReport,
  getProjectOverview,
  getReviewQueue,
} from "../api/product";
import type {
  AuditFilters,
  DocumentFilters,
  ReviewFilters,
} from "../api/product";

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: getProjects });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => getProject(projectId),
  });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => client.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useDocuments(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "documents"],
    queryFn: () => getDocuments(projectId),
    refetchInterval: (query) => {
      const active = query.state.data?.some((document) =>
        ["UPLOADED", "QUEUED", "PROCESSING"].includes(document.status),
      );
      return active ? 2_000 : false;
    },
  });
}

export function useUploadDocument(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadDocument(projectId, file),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: ["projects", projectId, "documents"],
      });
      void client.invalidateQueries({ queryKey: ["projects", projectId] });
    },
  });
}

export function useDocument(projectId: string, documentId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "documents", documentId],
    queryFn: () => getDocument(projectId, documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["UPLOADED", "QUEUED", "PROCESSING"].includes(status)
        ? 2_000
        : false;
    },
  });
}

export function useDocumentChunks(
  projectId: string,
  documentId: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["projects", projectId, "documents", documentId, "chunks"],
    queryFn: () => getDocumentChunks(projectId, documentId),
    enabled,
  });
}

export function useExtractions(
  projectId: string,
  documentId: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["projects", projectId, "documents", documentId, "extractions"],
    queryFn: () => getExtractions(projectId, documentId),
    enabled,
    refetchInterval: (query) => {
      const active = query.state.data?.some((run) =>
        ["QUEUED", "PROCESSING"].includes(run.status),
      );
      return active ? 2_000 : false;
    },
  });
}

export function useCreateExtraction(projectId: string, documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => createExtraction(projectId, documentId),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: [
          "projects",
          projectId,
          "documents",
          documentId,
          "extractions",
        ],
      });
      void client.invalidateQueries({
        queryKey: ["projects", projectId, "review-queue"],
      });
      void client.invalidateQueries({
        queryKey: ["projects", projectId, "overview"],
      });
    },
  });
}

export function useReviewField(projectId: string, documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      fieldId,
      review,
    }: {
      runId: string;
      fieldId: string;
      review: FieldReview;
    }) => reviewField(projectId, documentId, runId, fieldId, review),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: [
          "projects",
          projectId,
          "documents",
          documentId,
          "extractions",
        ],
      });
      void client.invalidateQueries({
        queryKey: ["projects", projectId, "review-queue"],
      });
      void client.invalidateQueries({
        queryKey: ["projects", projectId, "overview"],
      });
      void client.invalidateQueries({
        queryKey: ["projects", projectId, "audit-events"],
      });
    },
  });
}

export function useEmbeddingRuns(
  projectId: string,
  documentId: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["projects", projectId, "documents", documentId, "embeddings"],
    queryFn: () => getEmbeddingRuns(projectId, documentId),
    enabled,
    refetchInterval: (query) => {
      const active = query.state.data?.some((run) =>
        ["QUEUED", "PROCESSING"].includes(run.status),
      );
      return active ? 2_000 : false;
    },
  });
}

export function useCreateEmbeddingRun(projectId: string, documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => createEmbeddingRun(projectId, documentId),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: [
          "projects",
          projectId,
          "documents",
          documentId,
          "embeddings",
        ],
      }),
  });
}

export function useSemanticSearch(projectId: string, documentId?: string) {
  return useMutation({
    mutationFn: ({ query, topK }: { query: string; topK: number }) =>
      semanticSearch(projectId, query, topK, documentId),
  });
}

export function useRetrievalEvaluations(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "retrieval-evaluations"],
    queryFn: () => getRetrievalEvaluations(projectId),
  });
}

export function useRagQuestions(
  projectId: string,
  documentId?: string,
  filters: QuestionFilters = {},
) {
  return useQuery({
    queryKey: [
      "projects",
      projectId,
      "questions",
      documentId ?? "project",
      filters,
    ],
    queryFn: () => getQuestions(projectId, documentId, filters),
    refetchInterval: (query) => {
      const active = query.state.data?.some((question) =>
        ["QUEUED", "PROCESSING"].includes(question.status),
      );
      return active ? 2_000 : false;
    },
  });
}

export function useCreateRagQuestion(projectId: string, documentId?: string) {
  const client = useQueryClient();
  const queryKey = [
    "projects",
    projectId,
    "questions",
    documentId ?? "project",
  ];
  return useMutation({
    mutationFn: ({ question, topK }: { question: string; topK: number }) =>
      createQuestion(projectId, question, topK, documentId),
    onSuccess: (created) => {
      client.setQueryData<RagQuestion[]>(queryKey, (current = []) => [
        created,
        ...current.filter((item) => item.id !== created.id),
      ]);
      void client.invalidateQueries({ queryKey });
    },
  });
}

export function useEvaluationDatasets(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "evaluation-datasets"],
    queryFn: () => getEvaluationDatasets(projectId),
  });
}

export function useCreateEvaluationDataset(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: DatasetInput) =>
      createEvaluationDataset(projectId, payload),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["projects", projectId, "evaluation-datasets"],
      }),
  });
}

export function useSaveEvaluationCase(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      datasetId,
      caseId,
      payload,
    }: {
      datasetId: string;
      caseId?: string;
      payload: CaseInput;
    }) =>
      caseId
        ? updateEvaluationCase(projectId, datasetId, caseId, payload)
        : createEvaluationCase(projectId, datasetId, payload),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["projects", projectId, "evaluation-datasets"],
      }),
  });
}

export function useEvaluationRuns(
  projectId: string,
  filters: EvaluationRunFilters = {},
) {
  return useQuery({
    queryKey: ["projects", projectId, "evaluation-runs", filters],
    queryFn: () => getEvaluationRuns(projectId, filters),
    refetchInterval: (query) =>
      query.state.data?.some((run) =>
        ["QUEUED", "PROCESSING"].includes(run.status),
      )
        ? 2_000
        : false,
  });
}

export function useCreateEvaluationRun(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: RunInput) => createEvaluationRun(projectId, payload),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["projects", projectId, "evaluation-runs"],
      }),
  });
}

export function useCompareEvaluationRuns(projectId: string) {
  return useMutation({
    mutationFn: ({ runAId, runBId }: { runAId: string; runBId: string }) =>
      compareEvaluationRuns(projectId, runAId, runBId),
  });
}

export function useProjectOverview(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "overview"],
    queryFn: () => getProjectOverview(projectId),
  });
}

export function useDocumentIndex(projectId: string, filters: DocumentFilters) {
  return useQuery({
    queryKey: ["projects", projectId, "document-index", filters],
    queryFn: () => getDocumentIndex(projectId, filters),
  });
}

export function useReviewQueue(projectId: string, filters: ReviewFilters) {
  return useQuery({
    queryKey: ["projects", projectId, "review-queue", filters],
    queryFn: () => getReviewQueue(projectId, filters),
  });
}

export function useAuditIndex(projectId: string, filters: AuditFilters) {
  return useQuery({
    queryKey: ["projects", projectId, "audit-events", filters],
    queryFn: () => getAuditIndex(projectId, filters),
  });
}

export function useDocumentReport(projectId: string, documentId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "documents", documentId, "report"],
    queryFn: () => getDocumentReport(projectId, documentId),
  });
}
