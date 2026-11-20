from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd

from quantfish.data.catalog import DataCatalog, DatasetSpec

LOADABLE_SUFFIXES = {".csv": "csv", ".parquet": "parquet"}
DOC_SUFFIXES = {".pdf", ".txt", ".xlsx"}

DATE_PRIORITY = [
    "publidate",
    "pub_date",
    "anondt",
    "annodt",
    "anndt",
    "trddt",
    "tradingdate",
    "tradingmonth",
    "date",
    "idxtrd01",
    "enddate",
    "accper",
    "rptdt",
    "reportdate",
    "report_date",
    "statdt",
    "implementdate",
    "listdt",
    "valid_date",
]
DATE_NAMES = set(DATE_PRIORITY)
SYMBOL_PRIORITY = ["stkcd", "stock_id", "stockid", "symbol", "indexcd", "stockcode"]
CSMAR_TABLE_RE = re.compile(r"^[A-Z]{2,5}[0-9]?_[A-Za-z0-9_]+$")
DES_LINE_RE = re.compile(r"^\ufeff?\s*([A-Za-z][A-Za-z0-9_]*)\s+\[([^\]]+)\]\s*-\s*(.*)$")
SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def scan_catalog(root: Path | str) -> DataCatalog:
    root_path = Path(root)
    datasets: list[DatasetSpec] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or _is_hidden(path.relative_to(root_path)):
            continue
        file_format = LOADABLE_SUFFIXES.get(path.suffix.lower())
        if not file_format:
            continue
        columns = _read_columns(path, file_format)
        date_columns = _infer_date_columns(columns)
        primary_asof_column = _choose_primary_asof_column(date_columns)
        symbol_column = _infer_symbol_column(columns)
        table_code = _detect_csmar_table_code(path)
        aliases = _build_aliases(path, table_code)
        doc_paths = _nearby_doc_paths(path)
        column_descriptions = _parse_descriptions(path, columns)
        dataset_id = _dataset_id(path.relative_to(root_path))
        datasets.append(
            DatasetSpec(
                dataset_id=dataset_id,
                aliases=aliases,
                csmar_table_code=table_code,
                relative_path=path.relative_to(root_path).as_posix(),
                format=file_format,
                is_static=primary_asof_column is None,
                date_columns=date_columns,
                primary_asof_column=primary_asof_column,
                symbol_column=symbol_column,
                column_descriptions=column_descriptions,
                doc_paths=doc_paths,
            )
        )
    return DataCatalog(root=root_path.as_posix(), datasets=datasets)


def _is_hidden(relative_path: Path) -> bool:
    return any(part.startswith(".") for part in relative_path.parts)


def _read_columns(path: Path, file_format: str) -> list[str]:
    if file_format == "csv":
        return list(pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns)
    if file_format == "parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("pyarrow is required to scan parquet datasets") from exc
        return list(pq.read_schema(path).names)
    raise ValueError(f"unsupported dataset format: {file_format}")


def _dataset_id(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    if parts and parts[0] in {"distribute", "teacher"}:
        parts = parts[1:]
    return ".".join(parts)


def _detect_csmar_table_code(path: Path) -> str | None:
    stem = path.stem
    if CSMAR_TABLE_RE.match(stem):
        return stem
    return None


def _build_aliases(path: Path, table_code: str | None) -> list[str]:
    aliases: list[str] = []
    if table_code:
        aliases.append(table_code)
    if _is_datago_path(path):
        aliases.append(path.stem)
    return aliases


def _infer_date_columns(columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column.lower() in DATE_NAMES]


def _choose_primary_asof_column(date_columns: Iterable[str]) -> str | None:
    columns_by_lower = {column.lower(): column for column in date_columns}
    for name in DATE_PRIORITY:
        if name in columns_by_lower:
            return columns_by_lower[name]
    return None


def _infer_symbol_column(columns: Iterable[str]) -> str | None:
    columns_by_lower = {column.lower(): column for column in columns}
    for name in SYMBOL_PRIORITY:
        if name in columns_by_lower:
            return columns_by_lower[name]
    return None


def _nearby_doc_paths(path: Path) -> list[str]:
    docs = []
    for candidate in sorted(path.parent.iterdir()):
        if not candidate.is_file() or candidate == path or candidate.name.startswith("."):
            continue
        if candidate.suffix.lower() in DOC_SUFFIXES:
            docs.append(candidate.name)
    return docs


def _parse_descriptions(path: Path, columns: Iterable[str]) -> dict[str, dict[str, str]]:
    descriptions: dict[str, dict[str, str]] = {}
    for candidate in _description_files_for(path):
        text = candidate.read_text(encoding="utf-8-sig", errors="replace")
        for line in text.splitlines():
            match = DES_LINE_RE.match(line)
            if not match:
                continue
            field_name, label_zh, description = match.groups()
            descriptions[field_name] = {
                "label_zh": label_zh.strip(),
                "description": description.strip(),
            }
    for candidate in _xlsx_description_files_for(path):
        descriptions.update(_parse_xlsx_descriptions(candidate, path.stem, columns))
    return descriptions


def _description_files_for(path: Path) -> list[Path]:
    stem = path.stem
    candidates = []
    for candidate in path.parent.glob("*.txt"):
        name = candidate.name
        if stem in name and "[DES][csv]" in name:
            candidates.append(candidate)
    return sorted(candidates)


def _xlsx_description_files_for(path: Path) -> list[Path]:
    return sorted(
        candidate
        for candidate in path.parent.glob("*.xlsx")
        if candidate.is_file() and not candidate.name.startswith(".")
    )


def _is_datago_path(path: Path) -> bool:
    return "datago" in path.parts


def _parse_xlsx_descriptions(
    path: Path, table_stem: str, columns: Iterable[str]
) -> dict[str, dict[str, str]]:
    try:
        with ZipFile(path) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            sheet_targets = _xlsx_sheet_targets(archive)
            target = _choose_xlsx_sheet_target(sheet_targets, table_stem)
            rows = _xlsx_rows(archive, target, shared_strings)
    except (BadZipFile, ET.ParseError, KeyError, OSError, ValueError):
        return {}

    column_names = set(columns)
    for index, row in enumerate(rows):
        header = {str(value).strip(): position for position, value in enumerate(row) if value}
        field_index = header.get("字段")
        description_index = header.get("字段说明")
        data_type_index = header.get("数据类型")
        if field_index is None or description_index is None:
            continue
        descriptions: dict[str, dict[str, str]] = {}
        for value_row in rows[index + 1 :]:
            field_name = _row_value(value_row, field_index)
            if not field_name or field_name not in column_names:
                continue
            entry: dict[str, str] = {}
            data_type = (
                _row_value(value_row, data_type_index) if data_type_index is not None else ""
            )
            description = _row_value(value_row, description_index)
            if data_type:
                entry["data_type"] = data_type
            if description:
                entry["description"] = description
            if entry:
                descriptions[field_name] = entry
        return descriptions
    return {}


def _row_value(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index]).strip()


def _xlsx_shared_strings(archive: ZipFile) -> list[str]:
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    strings = []
    for item in root.findall(f".//{{{SPREADSHEET_NS}}}si"):
        strings.append(
            "".join(text.text or "" for text in item.findall(f".//{{{SPREADSHEET_NS}}}t"))
        )
    return strings


def _xlsx_sheet_targets(archive: ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        relation.attrib["Id"]: relation.attrib["Target"]
        for relation in rels.findall(f".//{{{PKG_REL_NS}}}Relationship")
    }
    sheets: dict[str, str] = {}
    for sheet in workbook.findall(f".//{{{SPREADSHEET_NS}}}sheet"):
        name = sheet.attrib.get("name")
        relation_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if not name or not relation_id or relation_id not in rel_targets:
            continue
        target = rel_targets[relation_id]
        if target.startswith("/"):
            normalized = target.lstrip("/")
        else:
            normalized = posixpath.normpath(posixpath.join("xl", target))
        sheets[name] = normalized
    if not sheets:
        raise ValueError("xlsx workbook has no sheets")
    return sheets


def _choose_xlsx_sheet_target(sheet_targets: dict[str, str], table_stem: str) -> str:
    if table_stem in sheet_targets:
        return sheet_targets[table_stem]
    normalized_table_stem = _normalize_sheet_name(table_stem)
    for sheet_name, target in sheet_targets.items():
        if _normalize_sheet_name(sheet_name) == normalized_table_stem:
            return target
    return next(iter(sheet_targets.values()))


def _normalize_sheet_name(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _xlsx_rows(
    archive: ZipFile,
    target: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ET.fromstring(archive.read(target))
    rows = []
    for row in root.findall(f".//{{{SPREADSHEET_NS}}}row"):
        values: list[str] = []
        for cell in row.findall(f"{{{SPREADSHEET_NS}}}c"):
            column_index = _xlsx_column_index(cell.attrib.get("r", ""))
            while len(values) <= column_index:
                values.append("")
            values[column_index] = _xlsx_cell_value(cell, shared_strings)
        rows.append(values)
    return rows


def _xlsx_column_index(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha())
    if not letters:
        return 0
    index = 0
    for char in letters.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(f".//{{{SPREADSHEET_NS}}}t"))
    value = cell.find(f"{{{SPREADSHEET_NS}}}v")
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (ValueError, IndexError):
            return ""
    return value.text
