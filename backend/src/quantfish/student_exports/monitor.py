from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Sequence

from quantfish.platform_config import ConfigRepository
from quantfish.student_exports.service import StudentExportService
from quantfish.web_app.settings import WebSettings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor and refresh QuantFish student exports.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "refresh", "watch"):
        command_parser = subparsers.add_parser(command)
        _add_common_args(command_parser)
    subparsers.choices["watch"].add_argument("--interval-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)

    settings = WebSettings(
        runtime_root=Path(args.runtime_root),
        config_path=Path(args.config),
    )
    repository = ConfigRepository(settings.config_path)
    service = StudentExportService(settings, repository, project_root=Path(args.project_root))

    if args.command == "status":
        _print_status(service, repository)
        return 0
    if args.command == "refresh":
        result = service.refresh(repository.load())
        payload = _status_payload(service, repository)
        payload["refreshed"] = result.refreshed
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "watch":
        return _watch(service, repository, float(args.interval_seconds))
    return 2


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config/platform.yaml")
    parser.add_argument("--runtime-root", default="runs/web_platform")
    parser.add_argument("--project-root", default=".")


def _print_status(
    service: StudentExportService,
    repository: ConfigRepository,
) -> None:
    print(
        json.dumps(
            _status_payload(service, repository),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _status_payload(
    service: StudentExportService,
    repository: ConfigRepository,
) -> dict[str, object]:
    config = repository.load()
    options = service.environment_options()
    return {
        "dependency_signature": service.dependency_signature(),
        "export_signature": service.export_signature(config),
        "learning_data_zip": service.learning_data_zip_path().as_posix(),
        "platforms": options["platforms"],
    }


def _watch(
    service: StudentExportService,
    repository: ConfigRepository,
    interval_seconds: float,
) -> int:
    previous_signature: str | None = None
    while True:
        config = repository.load()
        signature = service.export_signature(config)
        if signature != previous_signature:
            result = service.refresh(config)
            previous_signature = signature
            print(
                json.dumps(
                    {
                        "refreshed": result.refreshed,
                        "export_signature": signature,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
