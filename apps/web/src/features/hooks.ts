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
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: [
          "projects",
          projectId,
          "documents",
          documentId,
          "extractions",
        ],
      }),
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
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: [
          "projects",
          projectId,
          "documents",
          documentId,
          "extractions",
        ],
      }),
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
