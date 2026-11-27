import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { ErrorState, LoadingState } from "../../components/States";
import { useProject } from "../hooks";
import { MemberManagement } from "./MemberManagement";

interface SecurityConfig {
  storage_provider: string;
  storage_container: string | null;
  secret_store_provider: string;
  malware_scanner: string;
  secret_values_exposed: boolean;
}
export function SettingsPage() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const config = useQuery({
    queryKey: ["projects", projectId, "security-config"],
    queryFn: () =>
      apiRequest<SecurityConfig>(
        `/api/v1/projects/${projectId}/security/config`,
      ),
    enabled: project.data?.current_role === "OWNER",
  });
  if (project.isLoading) return <LoadingState />;
  return (
    <section>
      <div className="page-heading product-heading">
        <div>
          <p className="eyebrow">Project administration</p>
          <h1>Settings</h1>
          <p>
            Membership, storage posture, and backend-only secret configuration.
          </p>
        </div>
      </div>
      {project.data?.current_role !== "OWNER" ? (
        <p className="notice">
          Only project owners can view or change administrative settings.
        </p>
      ) : (
        <>
          {config.isLoading && (
            <LoadingState label="Loading security posture…" />
          )}
          {config.isError && <ErrorState error={config.error} />}{" "}
          {config.data && (
            <dl className="metadata-grid">
              <div>
                <dt>Storage</dt>
                <dd>{config.data.storage_provider}</dd>
              </div>
              <div>
                <dt>Secret store</dt>
                <dd>{config.data.secret_store_provider}</dd>
              </div>
              <div>
                <dt>Malware scanner</dt>
                <dd>{config.data.malware_scanner}</dd>
              </div>
              <div>
                <dt>Secret values</dt>
                <dd>
                  {config.data.secret_values_exposed
                    ? "Exposed"
                    : "Never returned"}
                </dd>
              </div>
            </dl>
          )}
          <MemberManagement projectId={projectId} />
        </>
      )}
    </section>
  );
}
