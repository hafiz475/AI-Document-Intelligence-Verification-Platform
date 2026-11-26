import { Link, Navigate, Route, Routes } from "react-router-dom";

import { DocumentDetailPage } from "./features/documents/DocumentDetailPage";
import { CreateProjectPage } from "./features/projects/CreateProjectPage";
import { ProjectDetailPage } from "./features/projects/ProjectDetailPage";
import { ProjectListPage } from "./features/projects/ProjectListPage";
import { EvaluationsPage } from "./features/evaluations/EvaluationsPage";
import { AuthGate } from "./features/auth/AuthGate";

function Layout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <nav aria-label="Primary navigation">
          <Link className="brand" to="/">
            <span aria-hidden="true">A</span>AssureAI
          </Link>
          <span className="milestone">Milestone 6 · Production hardening</span>
        </nav>
      </header>
      <main className="container">
        <Routes>
          <Route element={<ProjectListPage />} path="/" />
          <Route element={<CreateProjectPage />} path="/projects/new" />
          <Route element={<ProjectDetailPage />} path="/projects/:projectId" />
          <Route
            element={<EvaluationsPage />}
            path="/projects/:projectId/evaluations"
          />
          <Route
            element={<DocumentDetailPage />}
            path="/projects/:projectId/documents/:documentId"
          />
          <Route element={<Navigate replace to="/" />} path="*" />
        </Routes>
      </main>
      <footer>
        AssureAI · evidence-first document intelligence · quality is measured,
        versioned, and reproducible
      </footer>
    </div>
  );
}

export function App() {
  return (
    <AuthGate>
      <Layout />
    </AuthGate>
  );
}
