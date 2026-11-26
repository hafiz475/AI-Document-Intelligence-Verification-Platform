import { apiRequest } from "./client";
import type { CurrentUser } from "./types";

export function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest("/api/v1/auth/me");
}

export function developmentLogin(): Promise<CurrentUser> {
  return apiRequest("/api/v1/auth/development/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function logout(): Promise<void> {
  return apiRequest("/api/v1/auth/logout", { method: "POST" });
}
