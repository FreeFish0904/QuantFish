import { fireEvent, render, screen } from "@testing-library/react";

import { LightweightSvgChart } from "./LightweightSvgChart";

const data = [
  { date: "2026", value: 0 },
  { date: "2027", value: 1 }
];

describe("LightweightSvgChart", () => {
  it("does not stretch x-axis labels with non-uniform svg scaling", () => {
    render(
      <LightweightSvgChart
        data={data}
        height={180}
        series={[{ color: "#22d3ee", dataKey: "value", name: "Value", type: "line" }]}
        xKey="date"
        yDomain={[0, 1]}
      />
    );

    const surface = screen.getByTestId("lightweight-chart-surface");
    const svg = surface.querySelector("svg");

    expect(svg).not.toHaveAttribute("preserveAspectRatio", "none");
    expect(screen.getByText("2026")).toBeInTheDocument();
    expect(screen.getByText("2027")).toBeInTheDocument();
  });

  it("flips the tooltip to the left near the right chart boundary", () => {
    render(
      <LightweightSvgChart
        data={data}
        height={180}
        series={[{ color: "#22d3ee", dataKey: "value", name: "Value", type: "line" }]}
        xKey="date"
        yDomain={[0, 1]}
      />
    );

    const surface = screen.getByTestId("lightweight-chart-surface");
    const svg = surface.querySelector("svg");
    if (!svg) {
      throw new Error("Expected lightweight chart svg to render");
    }

    fireEvent.pointerMove(svg, { clientX: 748, clientY: 90 });

    const overlay = screen.getByRole("tooltip").parentElement;

    expect(overlay).toHaveAttribute("data-tooltip-side", "left");
    expect(overlay).toHaveStyle({ transform: "translate(calc(-100% - 12px), -50%)" });
  });
});
