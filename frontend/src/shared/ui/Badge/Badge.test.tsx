import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { I18nProvider } from "../../i18n";
import { Badge } from "./Badge";

function Wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider defaultLanguage="en">{children}</I18nProvider>;
}

describe("Badge", () => {
  it("renders status badge with visible text", () => {
    render(<Badge status="running" label="Scoring now" />, { wrapper: Wrapper });

    expect(screen.getByRole("status")).toHaveTextContent("Scoring now");
  });

  it("spins the running icon only for running status", () => {
    const { rerender } = render(<Badge status="running" label="Scoring now" />, { wrapper: Wrapper });

    const runningIcon = screen.getByRole("status").querySelector("svg");
    expect(runningIcon?.className.baseVal).toContain("spin");

    rerender(<Badge status="queued" label="Queued" />);

    const queuedIcon = screen.getByRole("status").querySelector("svg");
    expect(queuedIcon?.className.baseVal ?? "").not.toContain("spin");
  });
});
