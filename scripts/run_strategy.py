from __future__ import annotations

import argparse
from pathlib import Path

from quantfish.backtest import run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report
from quantfish.platform_config import ConfigRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one QuantFish strategy.")
    parser.add_argument(
        "strategy",
        nargs="?",
        default="examples/first-day/factor_0_vwap_close.py",
        help="Path to a strategy .py file. Defaults to factor_0_vwap_close.py.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output folder. Defaults to runs/manual_backtests/<strategy-name>.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    strategy_path = Path(args.strategy)
    if not strategy_path.is_absolute():
        strategy_path = project_root / strategy_path

    config = ConfigRepository(project_root / "config" / "platform.yaml").load()
    data_root = project_root / config.data_releases.hidden_output_root
    output_dir = (
        Path(args.output)
        if args.output is not None
        else project_root / "runs" / "manual_backtests" / strategy_path.stem
    )

    result = run_student_backtest(strategy_path, data_root, config)
    write_backtest_report(result, output_dir)

    print(result.summary.to_string(index=False))
    print()
    print("Strategy:", strategy_path)
    print("Data:", data_root)
    print("Scoring:", config.backtest.scoring_start, "to", config.backtest.scoring_end)
    print("Saved to:", output_dir)


if __name__ == "__main__":
    main()
