import { render, screen } from "@testing-library/react";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title, description, and action", () => {
    render(
      <EmptyState
        title="No submissions"
        description="Upload a starter strategy first."
        action={<button>Upload</button>}
      />
    );

    expect(screen.getByText("No submissions")).toBeInTheDocument();
    expect(screen.getByText("Upload a starter strategy first.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /upload/i })).toBeInTheDocument();
  });
});
