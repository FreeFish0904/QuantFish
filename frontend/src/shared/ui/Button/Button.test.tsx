import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Button } from "./Button";

describe("Button", () => {
  it("renders children and responds to clicks", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click me</Button>);

    await userEvent.click(screen.getByRole("button", { name: /click me/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("supports ghost variant", () => {
    render(<Button variant="ghost">Ghost</Button>);
    expect(screen.getByRole("button", { name: /ghost/i })).toBeInTheDocument();
  });
});
