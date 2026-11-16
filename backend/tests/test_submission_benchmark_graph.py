from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.platform_config import PlatformConfig
from quantfish.submissions.benchmark_graph import complete_hs300_benchmark_artifacts
from quantfish.submissions.models import SubmissionDataTrack


def _write_release_with_trd_index(root: Path) -> None:
    index_dir = root / "teacher" / "index_metadata" / "index_info"
    index_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "Indexcd": "000300",
                "Trddt": "2010-01-04",
                "Clsindex": 3535.229,
                "Retindex": -0.011314,
            },
            {
                "Indexcd": "000300",
                "Trddt": "2022-12-30",
                "Clsindex": 3871.634,
                "Retindex": 0.003872,
            },
        ]
    ).to_csv(index_dir / "TRD_Index.csv", index=False)
    DataCatalog(
        root=root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id="index_metadata.index_info.TRD_Index",
                aliases=["TRD_Index"],
                csmar_table_code="TRD_Index",
                relative_path="teacher/index_metadata/index_info/TRD_Index.csv",
                format="csv",
                is_static=False,
                date_columns=["Trddt"],
                primary_asof_column="Trddt",
                symbol_column="Indexcd",
            )
        ],
    ).save(root / "data_catalog.json")


def test_complete_hs300_benchmark_artifacts_extends_saved_learning_graph(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "learning"
    _write_release_with_trd_index(release_root)
    config = replace(
        PlatformConfig.default(),
        data_releases=replace(
            PlatformConfig.default().data_releases,
            learning_output_root=release_root.as_posix(),
        ),
    )
    artifacts = {
        "diagnostics": {"capital": 1_000_000},
        "graph_data": {
            "equity": [
                {"date": "2010-01-04", "equity": 1.0},
                {"date": "2022-12-30", "equity": 1.2},
            ],
            "benchmark": [
                {
                    "date": "2022-12-30",
                    "benchmark_return": 0.003872,
                    "benchmark_equity": 1.003872,
                    "benchmark_cny": 1_003_872,
                }
            ],
        },
    }

    completed = complete_hs300_benchmark_artifacts(
        artifacts,
        config,
        SubmissionDataTrack.LEARNING,
    )

    assert completed["graph_data"]["benchmark"] == [
        {
            "date": "2010-01-04",
            "benchmark_return": pytest.approx(-0.011314),
            "benchmark_equity": pytest.approx(0.988686),
            "benchmark_cny": pytest.approx(988_686),
        },
        {
            "date": "2022-12-30",
            "benchmark_return": pytest.approx(0.003872),
            "benchmark_equity": pytest.approx(0.992558),
            "benchmark_cny": pytest.approx(992_558),
        },
    ]
    assert artifacts["graph_data"]["benchmark"][0]["date"] == "2022-12-30"
