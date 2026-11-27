import { Navigate, Route, Routes } from "react-router-dom";

import { AuthGate } from "./features/auth/AuthGate";
import { DocumentDetailPage } from "./features/documents/DocumentDetailPage";
import { DocumentReportPage } from "./features/documents/DocumentReportPage";
import { EvaluationsPage } from "./features/evaluations/EvaluationsPage";
import { LandingPage } from "./features/landing/LandingPage";
import { AskPage } from "./features/projects/AskPage";
import { AuditPage } from "./features/projects/AuditPage";
import { CreateProjectPage } from "./features/projects/CreateProjectPage";
import { DocumentsPage } from "./features/projects/DocumentsPage";
import { OverviewPage } from "./features/projects/OverviewPage";
import { ProjectListPage } from "./features/projects/ProjectListPage";
import { ReviewQueuePage } from "./features/projects/ReviewQueuePage";
import { SearchPage } from "./features/projects/SearchPage";
import { SettingsPage } from "./features/projects/SettingsPage";
import { AppFrame, ProjectShell } from "./features/shell/AppShell";

function AuthenticatedFrame() {
  return (
    <AuthGate>
      <AppFrame />
    </AuthGate>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<LandingPage />} path="/" />
      <Route element={<AuthenticatedFrame />} path="/app">
        <Route element={<ProjectListPage />} index />
        <Route element={<CreateProjectPage />} path="projects/new" />
        <Route element={<ProjectShell />} path="projects/:projectId">
          <Route element={<Navigate replace to="overview" />} index />
          <Route element={<OverviewPage />} path="overview" />
          <Route element={<DocumentsPage />} path="documents" />
          <Route
            element={<DocumentReportPage />}
            path="documents/:documentId/report"
          />
          <Route
            element={<DocumentDetailPage />}
            path="documents/:documentId"
          />
          <Route element={<SearchPage />} path="search" />
          <Route element={<AskPage />} path="ask" />
          <Route element={<EvaluationsPage />} path="evaluations" />
          <Route element={<ReviewQueuePage />} path="review" />
          <Route element={<AuditPage />} path="audit" />
          <Route element={<SettingsPage />} path="settings" />
        </Route>
      </Route>
      <Route element={<Navigate replace to="/app" />} path="/projects/*" />
      <Route element={<Navigate replace to="/" />} path="*" />
    </Routes>
  );
}
