import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorState } from "../../components/States";
import { useCreateProject } from "../hooks";

export function CreateProjectPage() {
  const create = useCreateProject();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const project = await create.mutateAsync({
      name,
      description: description || null,
    });
    void navigate(`/projects/${project.id}`);
  }

  return (
    <section className="narrow">
      <Link className="back-link" to="/">
        ← Projects
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">New workspace</p>
          <h1>Create project</h1>
          <p>Documents and processing results remain scoped to this project.</p>
        </div>
      </div>
      <form className="form-card" onSubmit={(event) => void submit(event)}>
        <label>
          Project name
          <input
            autoFocus
            maxLength={200}
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </label>
        <label>
          Description
          <textarea
            maxLength={4000}
            onChange={(event) => setDescription(event.target.value)}
            rows={5}
            value={description}
          />
        </label>
        {create.isError && <ErrorState error={create.error} />}
        <div className="form-actions">
          <Link className="button secondary" to="/">
            Cancel
          </Link>
          <button disabled={create.isPending || !name.trim()} type="submit">
            {create.isPending ? "Creating…" : "Create project"}
          </button>
        </div>
      </form>
    </section>
  );
}
