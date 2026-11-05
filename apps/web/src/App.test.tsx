import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

describe("App", () => {
  it("states the honest foundation status and next capability", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: /technical evidence/i })).toBeInTheDocument();
    expect(screen.getByText("Milestone 0 foundation")).toBeInTheDocument();
    expect(screen.getByText("Document intake", { selector: "h3" })).toBeInTheDocument();
  });
});
