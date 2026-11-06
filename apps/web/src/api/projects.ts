import { apiRequest } from "./client";
import type { Project } from "./types";

export function getProjects(): Promise<Project[]> {
  return apiRequest("/api/v1/projects");
}

export function getProject(projectId: string): Promise<Project> {
  return apiRequest(`/api/v1/projects/${projectId}`);
}

export function createProject(input: {
  name: string;
  description: string | null;
}): Promise<Project> {
  return apiRequest("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
