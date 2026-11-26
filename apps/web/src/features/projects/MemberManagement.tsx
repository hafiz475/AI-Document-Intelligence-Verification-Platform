import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addMember,
  changeMemberRole,
  getMembers,
  removeMember,
} from "../../api/members";
import type { ProjectRole } from "../../api/types";
import { ErrorState, LoadingState } from "../../components/States";

export function MemberManagement({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => getMembers(projectId),
  });
  const [subject, setSubject] = useState("");
  const [role, setRole] = useState<ProjectRole>("VIEWER");
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["members", projectId] });
  const add = useMutation({
    mutationFn: () => addMember(projectId, { external_subject: subject, role }),
    onSuccess: () => {
      setSubject("");
      void refresh();
    },
  });
  const change = useMutation({
    mutationFn: ({
      userId,
      nextRole,
    }: {
      userId: string;
      nextRole: ProjectRole;
    }) => changeMemberRole(projectId, userId, nextRole),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (userId: string) => removeMember(projectId, userId),
    onSuccess: refresh,
  });

  if (members.isLoading) return <LoadingState label="Loading members..." />;
  if (members.isError) return <ErrorState error={members.error} />;
  return (
    <section className="evaluation-card">
      <h2>Project members</h2>
      <form
        className="inline-evaluation-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          add.mutate();
        }}
      >
        <label>
          Identity subject
          <input
            required
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
        </label>
        <label>
          Role
          <select
            value={role}
            onChange={(event) => setRole(event.target.value as ProjectRole)}
          >
            <option>VIEWER</option>
            <option>EDITOR</option>
            <option>OWNER</option>
          </select>
        </label>
        <button disabled={add.isPending}>Add member</button>
      </form>
      {add.isError && <ErrorState error={add.error} />}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Member</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.data?.map((member) => (
              <tr key={member.user.id}>
                <td>
                  {member.user.display_name ?? member.user.external_subject}
                </td>
                <td>
                  <select
                    aria-label={`Role for ${member.user.external_subject}`}
                    value={member.role}
                    onChange={(event) =>
                      change.mutate({
                        userId: member.user.id,
                        nextRole: event.target.value as ProjectRole,
                      })
                    }
                  >
                    <option>VIEWER</option>
                    <option>EDITOR</option>
                    <option>OWNER</option>
                  </select>
                </td>
                <td>
                  <button
                    className="button danger"
                    onClick={() => remove.mutate(member.user.id)}
                    type="button"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(change.isError || remove.isError) && (
        <ErrorState error={change.error ?? remove.error} />
      )}
    </section>
  );
}
