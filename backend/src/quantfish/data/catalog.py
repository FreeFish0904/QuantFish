from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    aliases: list[str]
    csmar_table_code: str | None
    relative_path: str
    format: str
    is_static: bool
    date_columns: list[str] = field(default_factory=list)
    primary_asof_column: str | None = None
    symbol_column: str | None = None
    column_descriptions: dict[str, dict[str, str]] = field(default_factory=dict)
    doc_paths: list[str] = field(default_factory=list)
    row_count: int | None = None
    source_row_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetSpec:
        return cls(
            dataset_id=data["dataset_id"],
            aliases=list(data.get("aliases", [])),
            csmar_table_code=data.get("csmar_table_code"),
            relative_path=data["relative_path"],
            format=data["format"],
            is_static=bool(data.get("is_static", False)),
            date_columns=list(data.get("date_columns", [])),
            primary_asof_column=data.get("primary_asof_column"),
            symbol_column=data.get("symbol_column"),
            column_descriptions=dict(data.get("column_descriptions", {})),
            doc_paths=list(data.get("doc_paths", [])),
            row_count=data.get("row_count"),
            source_row_count=data.get("source_row_count"),
        )


@dataclass
class DataCatalog:
    root: str | None
    datasets: list[DatasetSpec]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._index = self._build_index(self.datasets)

    @staticmethod
    def _build_index(datasets: Iterable[DatasetSpec]) -> dict[str, DatasetSpec]:
        index: dict[str, DatasetSpec] = {}
        for spec in datasets:
            keys = [spec.dataset_id, *spec.aliases]
            for key in keys:
                if key in index and index[key].dataset_id != spec.dataset_id:
                    raise ValueError(f"duplicate dataset key: {key}")
                index[key] = spec
        return index

    def list_datasets(self) -> list[str]:
        return sorted(spec.dataset_id for spec in self.datasets)

    def resolve(self, dataset_id_or_alias: str) -> DatasetSpec:
        try:
            return self._index[dataset_id_or_alias]
        except KeyError as exc:
            raise KeyError(f"unknown dataset: {dataset_id_or_alias}") from exc

    def describe(self, dataset_id_or_alias: str) -> DatasetSpec:
        return self.resolve(dataset_id_or_alias)

    def path_for(self, dataset_id_or_alias: str, root: Path | None = None) -> Path:
        spec = self.resolve(dataset_id_or_alias)
        base = root or (Path(self.root) if self.root else Path("."))
        return base / spec.relative_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "metadata": self.metadata,
            "datasets": [spec.to_dict() for spec in self.datasets],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataCatalog:
        return cls(
            root=data.get("root"),
            metadata=dict(data.get("metadata", {})),
            datasets=[DatasetSpec.from_dict(item) for item in data.get("datasets", [])],
        )

    @classmethod
    def from_json(cls, text: str) -> DataCatalog:
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: Path | str) -> DataCatalog:
        catalog_path = Path(path)
        return cls.from_json(catalog_path.read_text(encoding="utf-8"))

    def save(self, path: Path | str) -> None:
        catalog_path = Path(path)
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(self.to_json() + "\n", encoding="utf-8")
