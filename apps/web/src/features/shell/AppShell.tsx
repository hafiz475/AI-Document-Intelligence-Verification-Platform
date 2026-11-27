import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../../components/States";
import { useProject } from "../hooks";

const navItems = [
  ["Overview", "overview"],
  ["Documents", "documents"],
  ["Search", "search"],
  ["Ask AssureAI", "ask"],
  ["Evaluations", "evaluations"],
  ["Review Queue", "review"],
  ["Audit", "audit"],
  ["Settings", "settings"],
];

export function AppFrame() {
  return (
    <div className="app-shell product-shell">
      <header className="topbar product-topbar">
        <nav aria-label="Application navigation">
          <Link className="brand" to="/app">
            <span aria-hidden="true">A</span>AssureAI
          </Link>
          <div className="topbar-links">
            <Link to="/">Product</Link>
            <Link to="/app">Projects</Link>
          </div>
        </nav>
      </header>
      <Outlet />
      <footer>
        AssureAI · evidence-backed document intelligence · measured, reviewable,
        auditable
      </footer>
    </div>
  );
}

export function ProjectShell() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  if (project.isLoading)
    return (
      <main className="container">
        <LoadingState label="Opening workspace…" />
      </main>
    );
  if (project.isError)
    return (
      <main className="container">
        <ErrorState error={project.error} />
      </main>
    );
  return (
    <div className="workspace-layout">
      <aside className="workspace-sidebar">
        <Link
          className="workspace-project"
          to={`/app/projects/${projectId}/overview`}
        >
          <small>PROJECT</small>
          <strong>{project.data?.name}</strong>
          <span>{project.data?.current_role}</span>
        </Link>
        <nav aria-label="Project workspace">
          {navItems.map(([label, path]) => (
            <NavLink
              key={path}
              to={`/app/projects/${projectId}/${path}`}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <Link className="back-link" to="/app">
          ← All projects
        </Link>
      </aside>
      <main className="workspace-main">
        <Outlet />
      </main>
    </div>
  );
}
