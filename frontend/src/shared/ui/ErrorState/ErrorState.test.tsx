import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { I18nProvider } from "../../i18n";
import { ErrorState } from "./ErrorState";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <I18nProvider defaultLanguage="en">{children}</I18nProvider>;
}

describe("ErrorState", () => {
  it("renders title, message, and calls retry", async () => {
    const retry = vi.fn();
    render(<ErrorState title="Could not load" message="Runner unavailable" onRetry={retry} />, {
      wrapper: Wrapper
    });

    expect(screen.getByText("Could not load")).toBeInTheDocument();
    expect(screen.getByText("Runner unavailable")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
