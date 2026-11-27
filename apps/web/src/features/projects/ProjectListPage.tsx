import { Link } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useProjects } from "../hooks";

export function ProjectListPage() {
  const projects = useProjects();
  if (projects.isLoading) return <LoadingState label="Loading projects…" />;
  if (projects.isError) return <ErrorState error={projects.error} />;

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>Projects</h1>
          <p>Organize every document within an isolated assurance project.</p>
        </div>
        <Link className="button" to="/app/projects/new">
          Create project
        </Link>
      </div>
      {projects.data?.length ? (
        <div className="card-grid">
          {projects.data.map((project) => (
            <Link
              className="project-card"
              key={project.id}
              to={`/app/projects/${project.id}/overview`}
            >
              <div>
                <h2>{project.name}</h2>
                <p>{project.description || "No description provided."}</p>
              </div>
              <dl>
                <div>
                  <dt>Documents</dt>
                  <dd>{project.document_count}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{new Date(project.created_at).toLocaleDateString()}</dd>
                </div>
              </dl>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No projects yet"
          detail="Create a project, then upload a technical document to begin extracting and verifying information."
        />
      )}
    </section>
  );
}
