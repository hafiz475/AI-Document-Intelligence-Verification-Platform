import { Link, Navigate, Route, Routes } from "react-router-dom";

import { DocumentDetailPage } from "./features/documents/DocumentDetailPage";
import { CreateProjectPage } from "./features/projects/CreateProjectPage";
import { ProjectDetailPage } from "./features/projects/ProjectDetailPage";
import { ProjectListPage } from "./features/projects/ProjectListPage";

function Layout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <nav aria-label="Primary navigation">
          <Link className="brand" to="/">
            <span aria-hidden="true">A</span>AssureAI
          </Link>
          <span className="milestone">Milestone 1 · Document ingestion</span>
        </nav>
      </header>
      <main className="container">
        <Routes>
          <Route element={<ProjectListPage />} path="/" />
          <Route element={<CreateProjectPage />} path="/projects/new" />
          <Route element={<ProjectDetailPage />} path="/projects/:projectId" />
          <Route
            element={<DocumentDetailPage />}
            path="/projects/:projectId/documents/:documentId"
          />
          <Route element={<Navigate replace to="/" />} path="*" />
        </Routes>
      </main>
      <footer>
        AssureAI · deterministic ingestion only · AI extraction and RAG are not
        enabled
      </footer>
    </div>
  );
}

export function App() {
  return <Layout />;
}
