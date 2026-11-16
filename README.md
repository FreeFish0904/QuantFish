# QuantFish (食饭)

QuantFish is a classroom factor-research and backtesting platform. It provides a
Python data/backtest engine, a FastAPI backend, and a Vite/React web interface
for running student strategies, managing teams, publishing learning datasets,
and reviewing hidden-test results.

The repository is organized so another instructor or maintainer can clone it,
install dependencies, add their own licensed market data, and redeploy the
platform on macOS, Linux, Windows, or a server.

## Features

- Date-aware data bundles for leak-safe student research.
- Configurable learning and hidden-test data windows.
- Student strategy runner for `generate_signals(data, date)` Python files.
- Backtest reports with summary metrics, graph data, diagnostics, and yearly
  performance tables.
- FastAPI web backend with team, submission, leaderboard, admin, and download
  APIs.
- React frontend for students and instructors.
- Student download bundles and optional packed offline runtimes.
- GitHub Actions workflow for building platform-specific offline runtimes.

## Repository Layout

```text
config/                         Platform and course settings
docs/                           Project, design, and student documentation
docs/student/                   Student-facing guide and assets
examples/strategies/            Upload-ready example strategies
First Day Sample Strategies/    Beginner classroom sample strategies
frontend/                       Vite/React web frontend
scripts/                        Setup, run, runtime-build, and verification helpers
src/quantfish/                    Python package source
tests/                          Backend/domain/API tests
```

Local datasets, generated reports, runtime stores, build artifacts, caches, and
packed environments are intentionally not committed. See `.gitignore` for the
current generated paths.

## Prerequisites

- Git
- Conda or Miniconda
- Python 3.12
- Node.js and npm
- A licensed source dataset matching the configured CSMAR-style inputs
- Optional: GitHub CLI and GitHub Actions access for publishing offline runtimes

The default Conda environment name used by project scripts is `QuantFish`.

## Clone And Install

```bash
git clone <repo-url> quantfish
cd quantfish

conda env create -f environment.yml
conda activate QuantFish

python -m pip install -e '.[dev]'
npm --prefix frontend install --legacy-peer-deps
```

For China-based deployments, the project scripts and prior setup notes use the
Tsinghua PyPI mirror:

```bash
python -m pip install -e '.[dev]' -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## Configuration

The main runtime configuration lives in `config/platform.yaml`.

Use it to control:

- raw data location
- learning and hidden-test release output paths
- learning and hidden-test date ranges
- official scoring window
- capital, price policy, group count, and long-only/long-short mode
- execution settings such as costs, leverage, market scope, timeouts, and queue
  concurrency

Every web-app startup, including ASGI factory or embedded `create_app()` usage,
requires these three explicit credentials:

```bash
export QUANTFISH_ADMIN_PASSWORD='<strong-admin-password>'
export QUANTFISH_ADMIN_SESSION_SECRET='<random-session-secret>'
export QUANTFISH_PARTICIPANT_SESSION_SECRET='<different-random-session-secret>'
```

There are no built-in web credential fallbacks. The startup scripts bind to
`127.0.0.1` by default and generate a one-time
random admin password plus separate session secrets when they are not already
set. Binding to a LAN address requires all three environment variables above.

## Data Setup

QuantFish does not include commercial market data. Put your licensed raw data in
the path configured by `config/platform.yaml` (`new_data/` by default), then
build the configured learning, historical-window, and hidden-test releases:

```bash
conda activate QuantFish
python -m quantfish.data.releases build-from-config --config config/platform.yaml
```

Generated releases are written under `data_releases/` by default and remain
untracked. The practice tracks are `learning` (the complete configured learning
range), `learning_1` (2010–2015), `learning_2` (2015–2020), and `learning_3`
(2020–2022). The two boundary years intentionally appear in adjacent windows.
The hidden-test release is for official scoring and should not be distributed
to students.

To add only the historical windows without rebuilding existing releases, select
them explicitly:

```bash
python -m quantfish.data.releases build-from-config --config config/platform.yaml \
  --release learning_1 --release learning_2 --release learning_3
```

## Run The Web Platform

The easiest local or classroom startup path is:

```bash
scripts/start-quantfish.sh
```

Useful modes:

```bash
scripts/start-quantfish.sh --mode setup
scripts/start-quantfish.sh --mode dev
scripts/start-quantfish.sh --mode prod
scripts/start-quantfish.sh --mode verify
```

Development mode starts:

- backend: `http://localhost:8000`
- frontend: `http://localhost:5173`

Production mode builds the frontend and serves the full app from FastAPI:

```bash
scripts/start-quantfish.sh --mode prod --host 0.0.0.0 --backend-port 8000
```

Then open:

```text
http://localhost:8000/
http://<server-lan-ip>:8000/
```

## Manual Deployment

Use this path when deploying outside the helper script.

```bash
conda activate QuantFish
python -m pip install -e '.[dev]'
npm --prefix frontend install --legacy-peer-deps
npm --prefix frontend run build

QUANTFISH_ADMIN_PASSWORD='<strong-admin-password>' \
QUANTFISH_ADMIN_SESSION_SECRET='<random-session-secret>' \
QUANTFISH_PARTICIPANT_SESSION_SECRET='<different-random-session-secret>' \
quantfish-web --host 0.0.0.0 --port 8000 --runtime-root runs/web_platform
```

For a server deployment:

- persist `runs/web_platform/` or your chosen `--runtime-root`
- keep `data_releases/hidden_test/` private
- put FastAPI behind a reverse proxy if exposing it beyond a trusted LAN
- use HTTPS and strong admin secrets for any non-local deployment
- back up `runs/web_platform/repositories/`, submissions, reports, and exports

## Frontend Development

```bash
cd frontend
npm run dev -- --host 0.0.0.0
npm test -- --run
npm run build
```

During frontend development, Vite proxies `/api/*` to the backend at
`http://127.0.0.1:8000`.

## Student Workflow

Students should start with:

```text
docs/student/README.md
```

The beginner path is:

1. Read the student guide.
2. Copy `docs/student/examples/hello_strategy.py`.
3. Change only the `score = ...` logic at first.
4. Run against the learning data locally.
5. Submit the strategy file through the web platform.

Student strategies expose a callable:

```python
def generate_signals(data, date):
    ...
```

One-argument `generate_signals(data)` also works. Returned scores may be a
`pandas.Series` indexed by stock code or a DataFrame with `code` and `score`
columns.

## Student Downloads And Offline Runtimes

The web backend can publish:

- `learning-data.zip`
- starter strategy and quickstart files
- platform-specific offline Python runtimes

Relevant scripts:

```bash
scripts/build-offline-runtime.sh macos-arm64
scripts/build-offline-runtime.sh macos-x86_64
scripts/build-offline-runtime.ps1 windows-x86_64
scripts/import-offline-runtime.sh <platform> <zip-path>
scripts/verify-student-kit.sh <kit-root>
```

The GitHub Actions workflow `.github/workflows/offline-runtimes.yml` builds
runtime artifacts for macOS ARM, macOS Intel, and Windows x86_64.

## Backtest Engine

Programmatic use:

```python
from quantfish.platform_config import ConfigRepository
from quantfish.backtest import run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report

config = ConfigRepository("config/platform.yaml").load()

result = run_student_backtest(
    "submissions/team_alpha/strategy.py",
    config.data_releases.hidden_output_root,
    config,
)

write_backtest_report(result, "outputs/team_alpha")
```

Official evaluation uses front-adjusted prices. The canonical panel joins daily
returns with adjustment factors, computes raw VWAP, and evaluates trades with
front-adjusted VWAP for execution and front-adjusted close for marking.

## Verification

Run the full project checks before publishing changes:

```bash
conda run -n QuantFish python -m pytest
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

The helper script wraps the same checks:

```bash
scripts/start-quantfish.sh --mode verify
```

## Generated Files And Data Policy

Do not commit:

- raw or licensed market data
- `data_releases/`
- `runs/`
- `output/`
- `build/`, `dist/`, `frontend/dist/`
- `.runtime-build/`
- Python, Node, pytest, and Vite caches
- credentials or local environment folders

Commit source code, tests, documentation, small examples, and small static
assets that are safe to redistribute.

## Contributing

- Keep changes focused and reviewable.
- Follow `AGENTS.md` and `docs/design-principles.md`.
- Prefer feature-owned modules over broad utility files.
- Add or update tests for domain rules, service workflows, API contracts, and
  user-visible behavior.
- Run the verification commands above before opening a pull request.

## Security Notes

- Change `QUANTFISH_ADMIN_PASSWORD` for any shared deployment.
- Set a strong `QUANTFISH_ADMIN_SESSION_SECRET`.
- Treat hidden-test data, student submissions, and reports as sensitive.
- Use a reverse proxy, firewall rules, and HTTPS for non-local deployments.

## License

No open-source license file is currently included in this repository. Before
publishing or accepting external contributions, add an explicit `LICENSE` file
and confirm that all bundled code, examples, documents, and assets can be
redistributed under that license. Third-party market data must be licensed and
distributed separately according to its provider terms.
