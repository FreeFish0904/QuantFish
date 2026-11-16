export function toCsv(rows: Array<Record<string, unknown>>, columns: string[]): string {
  const escape = (value: unknown): string => {
    if (value === null || value === undefined) {
      return "";
    }
    const text = String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const header = columns.map(escape).join(",");
  const body = rows.map((row) => columns.map((column) => escape(row[column])).join(","));
  return [header, ...body].join("\n") + "\n";
}

export function downloadTextFile(
  filename: string,
  text: string,
  mimeType = "text/plain;charset=utf-8"
): void {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
