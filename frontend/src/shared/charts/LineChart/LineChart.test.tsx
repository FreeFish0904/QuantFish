import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { I18nProvider } from "../../i18n";
import { LineChart } from "./LineChart";

type Point = {
  date: string;
  value: number;
};

const points: Point[] = [
  { date: "2026-01-01", value: 100 },
  { date: "2026-02-01", value: 110 }
];

function Wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider defaultLanguage="en">{children}</I18nProvider>;
}

describe("LineChart", () => {
  it("renders chart with title and empty state", () => {
    const { rerender } = render(<LineChart data={points} xKey="date" yKey="value" color="#22d3ee" title="Equity" />, {
      wrapper: Wrapper
    });

    expect(screen.getByRole("img", { name: /equity/i })).toBeInTheDocument();

    rerender(<LineChart data={[]} xKey="date" yKey="value" color="#22d3ee" title="Equity" />);
    expect(screen.getByText(/no chart data/i)).toBeInTheDocument();
  });

  it("uses the lightweight svg graph engine without recharts output", () => {
    render(<LineChart data={points} xKey="date" yKey="value" color="#22d3ee" title="Equity" />, {
      wrapper: Wrapper
    });

    const surface = screen.getByTestId("lightweight-chart-surface");

    expect(surface).toHaveAttribute("data-chart-engine", "lightweight-svg");
    expect(surface).toHaveAttribute("data-animation", "none");
    expect(screen.getByTestId("lightweight-line-value")).toBeInTheDocument();
    expect(document.querySelector(".recharts-surface")).not.toBeInTheDocument();
  });
});
