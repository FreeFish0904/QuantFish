import { ArrowDown, ArrowUp, MoveHorizontal } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { useI18n } from "../../i18n";
import { EmptyState } from "../EmptyState/EmptyState";
import styles from "./DataTable.module.css";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortKey?: string;
  align?: "left" | "right";
};

export type DataTableProps<T> = {
  caption: string;
  columns: DataTableColumn<T>[];
  empty?: ReactNode;
  getRowId: (row: T) => string;
  getRowLabel?: (row: T) => string;
  isRowSelectable?: (row: T) => boolean;
  onSelectRow?: (rowId: string) => void;
  onSort?: (sortKey: string) => void;
  rows: T[];
  selectedRowIds?: Set<string>;
  sort?: { key: string; direction: "asc" | "desc" };
};

function inferRowLabel<T>(row: T, fallback: string): string {
  const maybeNamed = row as { team?: unknown; teamName?: unknown; label?: unknown; name?: unknown };
  const value = maybeNamed.team ?? maybeNamed.teamName ?? maybeNamed.label ?? maybeNamed.name;
  return typeof value === "string" ? value : fallback;
}

export function DataTable<T>({
  caption,
  columns,
  empty,
  getRowId,
  getRowLabel,
  isRowSelectable,
  onSelectRow,
  onSort,
  rows,
  selectedRowIds,
  sort
}: DataTableProps<T>) {
  const { t } = useI18n();
  const scrollHintId = useId();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [hasHorizontalOverflow, setHasHorizontalOverflow] = useState(false);

  useEffect(() => {
    const container = wrapRef.current;
    if (!container) {
      return;
    }

    const updateOverflow = () => {
      setHasHorizontalOverflow(container.scrollWidth - container.clientWidth > 1);
    };
    updateOverflow();

    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(updateOverflow);
    observer?.observe(container);
    const table = container.querySelector("table");
    if (table) {
      observer?.observe(table);
    }
    window.addEventListener("resize", updateOverflow);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateOverflow);
    };
  }, [columns.length, rows.length]);

  if (rows.length === 0) {
    return (
      <>
        {empty ?? (
          <EmptyState title={t("common.noRows")} description={t("common.noRowsDescription")} />
        )}
      </>
    );
  }

  const selectable = Boolean(onSelectRow);

  return (
    <div className={styles.tableRegion}>
      {hasHorizontalOverflow ? (
        <p className={styles.scrollHint} id={scrollHintId}>
          <MoveHorizontal aria-hidden="true" size={15} />
          {t("common.tableScrollHint")}
        </p>
      ) : null}
      <div
        aria-describedby={hasHorizontalOverflow ? scrollHintId : undefined}
        aria-label={hasHorizontalOverflow ? caption : undefined}
        className={styles.wrap}
        ref={wrapRef}
        role={hasHorizontalOverflow ? "region" : undefined}
        tabIndex={hasHorizontalOverflow ? 0 : undefined}
      >
        <table aria-label={caption} className={styles.table}>
          <caption>{caption}</caption>
          <thead>
            <tr>
              {selectable ? <th scope="col">{t("common.select")}</th> : null}
              {columns.map((column) => (
                <th
                  aria-sort={
                    column.sortKey && onSort
                      ? sort?.key === column.sortKey
                        ? sort.direction === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                      : undefined
                  }
                  className={column.align === "right" ? styles.alignRight : undefined}
                  key={column.key}
                  scope="col"
                >
                  {column.sortKey && onSort ? (
                    <button
                      aria-label={t("common.sortBy", { header: column.header })}
                      className={styles.sort}
                      type="button"
                      onClick={() => onSort(column.sortKey ?? column.key)}
                    >
                      {column.header}
                      {sort?.key === column.sortKey ? (
                        sort.direction === "asc" ? (
                          <ArrowUp aria-hidden="true" size={13} />
                        ) : (
                          <ArrowDown aria-hidden="true" size={13} />
                        )
                      ) : null}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rowId = getRowId(row);
              const rowLabel = getRowLabel ? getRowLabel(row) : inferRowLabel(row, rowId);
              const rowSelectable = selectable && (isRowSelectable?.(row) ?? true);
              const selected = selectedRowIds?.has(rowId) ?? false;

              return (
                <tr
                  aria-selected={selectable ? selected : undefined}
                  className={selected && rowSelectable ? styles.selectedRow : undefined}
                  key={rowId}
                >
                  {selectable ? (
                    <td>
                      <input
                        aria-label={t("common.selectRow", { rowLabel })}
                        checked={rowSelectable && selected}
                        disabled={!rowSelectable}
                        onChange={() => {
                          if (rowSelectable) {
                            onSelectRow?.(rowId);
                          }
                        }}
                        type="checkbox"
                      />
                    </td>
                  ) : null}
                  {columns.map((column) => (
                    <td className={column.align === "right" ? styles.alignRight : undefined} key={column.key}>
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
