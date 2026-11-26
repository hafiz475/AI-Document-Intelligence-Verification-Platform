import { apiRequest } from "./client";
import type { ProjectMembership, ProjectRole } from "./types";

export function getMembers(projectId: string): Promise<ProjectMembership[]> {
  return apiRequest(`/api/v1/projects/${projectId}/members`);
}

export function addMember(
  projectId: string,
  input: {
    external_subject: string;
    email?: string;
    display_name?: string;
    role: ProjectRole;
  },
): Promise<ProjectMembership> {
  return apiRequest(`/api/v1/projects/${projectId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function changeMemberRole(
  projectId: string,
  userId: string,
  role: ProjectRole,
): Promise<ProjectMembership> {
  return apiRequest(`/api/v1/projects/${projectId}/members/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
}

export function removeMember(projectId: string, userId: string): Promise<void> {
  return apiRequest(`/api/v1/projects/${projectId}/members/${userId}`, {
    method: "DELETE",
  });
}
