"""Seed the QuantFish demo with two teams and two submissions.

Run once before the server starts (see ``deploy/entrypoint.sh``). The
submissions are queued, not scored: once the web server boots, its dispatcher
picks them up and runs real backtests against the generated dataset, so the
demo UI shows a live leaderboard instead of an empty shell.
"""

from __future__ import annotations

import os
from pathlib import Path

from quantfish.web_app.app import create_app
from quantfish.web_app.settings import WebSettings

CONFIG_PATH = Path(os.environ.get("QUANTFISH_CONFIG", "config/platform.demo.yaml"))
RUNTIME_ROOT = Path(os.environ.get("QUANTFISH_RUNTIME_ROOT", "runs/web_platform"))

DEMO_SUBMISSIONS = (
    ("Alpha Desk", "alpha-demo", "hidden_test", "examples/first-day/factor_0_vwap_close.py"),
    ("Beta Desk", "beta-demo", "learning", "examples/first-day/factor_0_vwap_close.py"),
)


def main() -> int:
    if (RUNTIME_ROOT / "repositories").exists() and any(
        (RUNTIME_ROOT / "submissions").glob("*")
    ):
        print("[seed] runtime already contains submissions, skipping")
        return 0

    app = create_app(WebSettings(runtime_root=RUNTIME_ROOT, config_path=CONFIG_PATH))
    services = app.state.services
    for team_name, password, data_track, strategy_path in DEMO_SUBMISSIONS:
        if services.team_repository.resolve_login(team_name) is None:
            services.team_repository.create_team_with_name(
                display_name=team_name,
                password=password,
            )
        strategy = Path(strategy_path)
        submission = services.submission_service.submit_strategy(
            team_name=team_name,
            password=password,
            filename=strategy.name,
            content=strategy.read_bytes(),
            data_track=data_track,
        )
        print(f"[seed] queued {submission.submission_id} for {team_name} ({data_track})")
    print("[seed] done; the dispatcher will score these submissions on startup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
