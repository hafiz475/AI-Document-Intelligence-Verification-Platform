import { FormEvent, type ReactNode, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { developmentLogin, getCurrentUser, logout } from "../../api/auth";
import { LoadingState } from "../../components/States";

export function AuthGate({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const currentUser = useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    retry: false,
  });
  const login = useMutation({
    mutationFn: developmentLogin,
    onSuccess: (user) => client.setQueryData(["current-user"], user),
  });
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      client.clear();
      void currentUser.refetch();
    },
  });
  const [submitted, setSubmitted] = useState(false);

  if (currentUser.isLoading)
    return <LoadingState label="Checking session..." />;
  if (currentUser.isError || !currentUser.data) {
    return (
      <main className="container narrow">
        <form
          className="form-card"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            setSubmitted(true);
            login.mutate();
          }}
        >
          <p className="eyebrow">Development authentication</p>
          <h1>Sign in to AssureAI</h1>
          <p>
            This demo uses a clearly labelled local identity. Production uses
            validated OIDC identity tokens and never stores provider tokens in
            browser storage.
          </p>
          <button disabled={login.isPending} type="submit">
            {login.isPending ? "Signing in..." : "Sign in to demo"}
          </button>
          {submitted && login.isError && (
            <p className="field-error" role="alert">
              {login.error.message}
            </p>
          )}
        </form>
      </main>
    );
  }

  return (
    <>
      <div className="session-bar">
        <span>
          {currentUser.data.display_name ?? currentUser.data.external_subject}
        </span>
        <button
          disabled={signOut.isPending}
          onClick={() => signOut.mutate()}
          type="button"
        >
          Log out
        </button>
      </div>
      {children}
    </>
  );
}
