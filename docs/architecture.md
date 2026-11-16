# Architecture

QuantFish is a single repository with two deployable halves:

```text
frontend (React 19 + Vite)  ──HTTP──▶  backend (FastAPI)
                                          │
                                          ├─ engine: panel → simulator → metrics
                                          ├─ scoring: queue → worker process → report
                                          ├─ data: raw CSVs → release folders (parquet)
                                          └─ storage: SQLite + JSON + run artifacts
```

Everything is shipped from one process in production: FastAPI serves the API
and the compiled frontend from `frontend/dist`.

## Backend package (`backend/src/quantfish`)

| Module | Responsibility |
| --- | --- |
| `web_app` | App factory, settings (env-driven), auth for admin and participant sessions, response models. |
| `platform_config` | `PlatformConfig` dataclass tree parsed from `config/platform.yaml` with validation and round-tripping. |
| `data` | Raw CSV scanning (`scanner`), release materialisation (`releases`), catalog, release jobs and file locking, scoring dataset resolution. |
| `backtest` | The engine: panel building, price adjustment, industry neutralisation, simulator, equity/metrics, graph data, PDF report. |
| `factor_execution` | Sandboxed execution of a submitted `generate_signals.py` to produce scores. |
| `submissions` | Submission lifecycle: storage, repositories, dispatcher/queue, score worker, track config, staleness, participant sessions, REST routes. |
| `leaderboard` | Ranking, score weighting and the summary endpoints consumed by the dashboard. |
| `result_comparison` | Multi-run comparison endpoints. |
| `admin_console` | Admin settings, team management, data-release jobs, settings history. |
| `team_cohorts` | Cohort grouping of teams. |
| `student_exports` | Student data zips, offline runtime packages, export manifests. |

### Request → score flow

1. `POST /api/submissions` validates the uploaded script and stores it under
   `runs/web_platform/submissions/<id>/`.
2. The dispatcher enqueues a job; a background thread spawns
   `score_worker` in a separate process with the configured timeout.
3. The worker executes the strategy through `factor_execution`, builds the
   panel (`backtest/panel.py`, cached in `backtest/panel_cache.py`), runs the
   simulator and writes artifacts into `runs/web_platform/reports/<id>/`
   (`summary.csv`, `graph_data.json`, `report.pdf`).
4. Progress is exposed through the submission status endpoints; the frontend
   polls until the status becomes `completed`, then renders metrics, charts and
   download links.

### Data contract

`scan_catalog` auto-detects the layout of a data release, so both the bundled
synthetic demo and the real market release work:

| Table | Columns used by the engine |
| --- | --- |
| `stock.daily_returns` | `stkcd`, `trddt`, `dretwd`, `clsprc`, `dnshrtrd`, `dnvaltrd`, `markettype` |
| `factor_benchmark.adj_factor` | `tradingdate`, `cumulatefwardfactor` |
| `market.index_daily` | `indexcd`, `idxtrd01`, `idxtrd05`, `idxtrd08`, `idxtrd09` |
| `basic.STK_INDUSTRYCLASS` | `ImplementDate`, `Symbol`, `IndustryName` |
| `basic.company_info` | `stkcd`, `listdt`, `statdt` |

`quantfish.data.releases build-from-config` turns raw CSVs into a release
folder with `data_catalog.json`, `distribute/` copies and parquet mirrors.

### Settings and timeouts

`config/platform.yaml` is the single source of truth. The scoring timeout lives
in `execution.submission_timeout_enabled` / `execution.submission_timeout_seconds`
and is surfaced to the UI through the leaderboard summary (`runner_status`).
Runtime paths, secrets and CORS origins come from environment variables
(`QUANTFISH_*`), documented in `.env.example`.

## Frontend (`frontend/src`)

```text
app/            Shell composition (routing outlet)
features/       One folder per screen: api.ts (typed client), model.ts (React Query
                hooks + view model), view.tsx (presentation), view.module.css, tests
shared/         api client + generated OpenAPI types, i18n, layout, charts, UI kit,
                preferences (localStorage), downloads helper
theme/          Design tokens (--qf-*) and global styles
test/           MSW server + render helpers used by the vitest suite
```

Conventions:

- **Feature folders are self-contained.** Data access lives in `api.ts`, all
  transformation in `model.ts`, rendering in `view.tsx`. Tests cover the model
  (pure functions) and the view (Testing Library + MSW).
- **No chart library.** `shared/charts` renders hand-written SVG so the bundle
  stays small and tooltips/axes behave consistently across light and dark.
- **Two languages, one dictionary.** `shared/i18n/translations.ts` holds `en`
  and `zh` trees; components only call `t("namespace.key")`.
- **Demo mode.** `VITE_DEMO_MODE=true` boots a service-worker mock backend
  (`src/mocks` + `src/demo`) so the UI can be hosted on GitHub Pages without a
  server.

## Deployment shapes

| Shape | Entry point | Notes |
| --- | --- | --- |
| Single-process demo | `scripts/start-quantfish.sh --mode prod` | FastAPI + prebuilt frontend on one port. |
| Docker demo | `deploy/docker-compose.yml` | Generates synthetic data, builds releases, runs a real backtest. |
| Static portfolio demo | `.github/workflows/pages.yml` | `VITE_DEMO_MODE=true` build, mock API in the browser. |
| Classroom server | `scripts/start-quantfish-server.sh` | venv-based, host/port and runtime root configurable. |
