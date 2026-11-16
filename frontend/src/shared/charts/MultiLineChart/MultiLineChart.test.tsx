import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { I18nProvider } from "../../i18n";
import { MultiLineChart } from "./MultiLineChart";

type Point = {
  date: string;
  a: number;
  b: number;
};

const data: Point[] = [{ date: "2026-01-01", a: 100, b: 100 }];

const series = [
  { id: "a", name: "Alpha", color: "#22d3ee" },
  { id: "b", name: "Beta", color: "#f59e0b" }
];

function Wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider defaultLanguage="en">{children}</I18nProvider>;
}

describe("MultiLineChart", () => {
  it("renders multi-series chart", () => {
    render(<MultiLineChart data={data} series={series} xKey="date" title="Compare" />, { wrapper: Wrapper });

    expect(screen.getByRole("img", { name: /compare/i })).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("uses the lightweight svg graph engine for every series without recharts output", () => {
    render(<MultiLineChart data={data} series={series} xKey="date" title="Compare" />, { wrapper: Wrapper });

    const surface = screen.getByTestId("lightweight-chart-surface");

    expect(surface).toHaveAttribute("data-chart-engine", "lightweight-svg");
    expect(surface).toHaveAttribute("data-animation", "none");
    expect(screen.getByTestId("lightweight-line-a")).toBeInTheDocument();
    expect(screen.getByTestId("lightweight-line-b")).toBeInTheDocument();
    expect(document.querySelector(".recharts-surface")).not.toBeInTheDocument();
  });

  it("renders empty state when data is missing", () => {
    render(<MultiLineChart data={[]} series={series} xKey="date" title="Compare" />, { wrapper: Wrapper });

    expect(screen.getByText(/no chart data/i)).toBeInTheDocument();
  });
});
