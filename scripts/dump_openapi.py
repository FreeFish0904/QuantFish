#!/usr/bin/env python
"""Print the platform's OpenAPI schema as JSON, without starting a server.

The frontend types in `frontend/src/shared/api/generated/api-types.ts` are
generated from this schema, so CI re-runs this script and fails when the
committed types drift from the backend contract.

Determinism matters here: the dump uses throw-away credentials, a pinned
engine version (the real one hashes the source tree) and a temporary runtime
directory, so it never touches `runs/` or `config/` state.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepare_environment() -> None:
    os.chdir(REPO_ROOT)
    os.environ["QUANTFISH_ADMIN_PASSWORD"] = "openapi-dump"
    os.environ["QUANTFISH_ADMIN_SESSION_SECRET"] = "openapi-dump"
    os.environ["QUANTFISH_PARTICIPANT_SESSION_SECRET"] = "openapi-dump"
    # Pinned: the default engine version embeds a source hash, which would make
    # every commit look like a contract change.
    os.environ["QUANTFISH_ENGINE_VERSION"] = "quantfish-0.0.0+openapi-dump"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="quantfish-openapi-") as tmp:
        _prepare_environment()

        from quantfish.web_app.app import create_app
        from quantfish.web_app.settings import WebSettings

        settings = WebSettings(
            runtime_root=Path(tmp) / "runtime",
            frontend_dist=Path(tmp) / "missing-frontend-dist",
        )
        app = create_app(settings)
        json.dump(app.openapi(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
