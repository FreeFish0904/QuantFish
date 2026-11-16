import { render, screen } from "@testing-library/react";

import { Card } from "./Card";

describe("Card", () => {
  it("renders children and optional header", () => {
    render(
      <Card header={<span>Header</span>}>
        <p>Body content</p>
      </Card>
    );

    expect(screen.getByText("Header")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });
});
