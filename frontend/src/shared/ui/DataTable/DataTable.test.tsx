import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { I18nProvider } from "../../i18n";
import { DataTable } from "./DataTable";

type Row = {
  id: string;
  team: string;
  score: number;
};

function Wrapper({ children }: { children: React.ReactNode }) {
  return <I18nProvider defaultLanguage="en">{children}</I18nProvider>;
}

describe("DataTable", () => {
  it("supports sortable selectable tables", async () => {
    const onSort = vi.fn();
    const onSelect = vi.fn();
    const rows: Row[] = [
      { id: "a", team: "Alpha", score: 90 },
      { id: "b", team: "Beta", score: 84 }
    ];

    render(
      <DataTable
        caption="Leaderboard rows"
        columns={[
          { key: "team", header: "Team", render: (row) => row.team },
          { key: "score", header: "Score", render: (row) => row.score.toFixed(1), sortKey: "score", align: "right" }
        ]}
        getRowId={(row) => row.id}
        onSelectRow={onSelect}
        onSort={onSort}
        rows={rows}
        selectedRowIds={new Set(["b"])}
        sort={{ key: "score", direction: "desc" }}
      />,
      { wrapper: Wrapper }
    );

    await userEvent.click(screen.getByRole("button", { name: /sort by score/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /select alpha/i }));

    expect(onSort).toHaveBeenCalledWith("score");
    expect(onSelect).toHaveBeenCalledWith("a");
    expect(screen.getByRole("checkbox", { name: /select beta/i })).toBeChecked();
  });

  it("renders empty state when rows are empty", () => {
    render(
      <DataTable
        caption="Empty"
        columns={[{ key: "team", header: "Team", render: (row: Row) => row.team }]}
        getRowId={(row) => row.id}
        rows={[]}
      />,
      { wrapper: Wrapper }
    );

    expect(screen.getByText(/no rows/i)).toBeInTheDocument();
  });

  it("explains how to reach columns when the table overflows", async () => {
    const originalScrollWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollWidth");
    const originalClientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", { configurable: true, get: () => 640 });
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => 320 });

    try {
      render(
        <DataTable
          caption="Wide history"
          columns={[{ key: "team", header: "Team", render: (row: Row) => row.team }]}
          getRowId={(row) => row.id}
          rows={[{ id: "a", team: "Alpha", score: 90 }]}
        />,
        { wrapper: Wrapper }
      );

      expect(await screen.findByText(/scroll horizontally to see more columns/i)).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Wide history" })).toHaveAttribute("tabindex", "0");
    } finally {
      if (originalScrollWidth) {
        Object.defineProperty(HTMLElement.prototype, "scrollWidth", originalScrollWidth);
      } else {
        delete (HTMLElement.prototype as unknown as { scrollWidth?: number }).scrollWidth;
      }
      if (originalClientWidth) {
        Object.defineProperty(HTMLElement.prototype, "clientWidth", originalClientWidth);
      } else {
        delete (HTMLElement.prototype as unknown as { clientWidth?: number }).clientWidth;
      }
    }
  });
});
