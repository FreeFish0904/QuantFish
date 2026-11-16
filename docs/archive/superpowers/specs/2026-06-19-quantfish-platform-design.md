# QuantFish Platform Design

## Scope

Build a LAN-accessible classroom quantitative strategy website for the existing
QuantFish Python package. The student-facing product name is QuantFish, while the
Python package and repository remain `quantfish`.

The first working version supports:

- Team strategy uploads with password authentication.
- Hidden-test scoring through the existing `run_student_backtest()` engine.
- A live leaderboard with stale-result detection.
- Submission detail and side-by-side comparison views.
- Downloadable learning data and starter templates.
- Instructor management for teams, scoring settings, execution limits, datasets,
  submissions, exports, and class tooling.
- A classroom market mini-game screen with public and teacher modes.

## Architecture

The backend is added before the frontend and follows the project dependency
direction:

```text
React UI -> typed API client -> FastAPI route -> feature service -> repository/adapter
```

Existing modules stay as lower-level domain engines:

- `quantfish.backtest` owns official scoring and report artifacts.
- `quantfish.factor_execution` owns student strategy loading and signal validation.
- `quantfish.data` owns release catalogs and release building.
- `quantfish.platform_config` owns validated YAML course/scoring config.

New web-facing code is feature-owned instead of grouped by technical layer:

- `quantfish/web_app`: app factory, settings, CORS/static mounting, shared schemas.
- `quantfish/submissions`: teams, uploads, result status, file storage, jobs, report
  artifact reading, scoring adapter, and stale detection.
- `quantfish/leaderboard`: ranking rules and leaderboard API.
- `quantfish/admin_console`: instructor config/team/dataset/submission/toolbox APIs.
- `quantfish/result_comparison`: multi-submission alignment and comparison payloads.
- `quantfish/mini_games`: classroom market game state, settlement, and APIs.
- `frontend`: Vite React app with feature folders matching the backend domains.

## Backend Behavior

### Persistence

Use JSON file repositories under an ignored runtime directory, default
`runs/web_platform/`. This keeps the first version easy to inspect and avoids
introducing database migrations before the classroom workflow requires them.
Repositories write atomically and expose intent-shaped methods such as
`save_submission()`, `list_submissions()`, and `find_team_by_name()`.

### Submissions

The upload workflow lives in `SubmissionService`:

1. Validate team name, password, and `.py` file extension.
2. Authenticate or create teams according to instructor settings.
3. Save the queued strategy under a submission-owned directory.
4. Create a submission record with status `queued`.
5. Run hidden-test scoring through a job adapter.
6. Persist report artifacts and mark status `completed` or `failed`.

The MVP runs scoring synchronously by default so it is deterministic in tests and
easy to run locally. The service boundary is shaped so a background queue can
replace that adapter later without changing routes or UI contracts.

### Scoring And Staleness

Each scored submission stores fingerprints for:

- Strategy file SHA-256.
- Platform config JSON SHA-256.
- Hidden release catalog SHA-256.
- Scoring engine version string.
- Report artifact manifest.

A submission is stale when any current fingerprint differs from the stored
fingerprint. Stale rows remain visible on the leaderboard with a `stale` badge so
students and instructors know a rerun is needed.

### Leaderboard

Ranking is a pure function over public submission summaries. Default sort is:

1. Non-stale completed submissions before stale/failed/running rows.
2. Higher composite score.
3. Higher Sharpe.
4. Lower max drawdown.
5. Earlier submission time.

The composite score uses existing metrics and admin weights. The first version
defaults to Sharpe, total return, and drawdown weights and exposes those weights
through the admin scoring panel.

### Admin Console

Instructor APIs expose the existing platform config safely through service
methods. The first version supports editing:

- Dataset split dates.
- Scoring start/end, capital, alpha type, group count, and metric weights.
- Execution limits such as max upload bytes and timeout seconds.
- Teams and passwords.
- Submission rerun/export/delete actions.

Hidden-test exports are server-side zip files containing report artifacts and
metadata, never raw hidden data.

### Downloads

The backend serves:

- The ignored local learning release if present.
- A generated starter `strategy.py` template.
- A README-style quickstart text file.

Missing local data returns an explicit API status and a frontend empty state.

### Mini Games

The mini-game module owns a lightweight classroom market simulation:

- Teacher mode controls setup, status, settlement, and reset.
- Public mode shows live price/trade chart, trade tape, participant ledger, and
  ranking.
- Settlement/ranking rules are pure functions with focused tests.

## Frontend Behavior

Use Vite + React + TypeScript in `frontend/`. The UI is a compact dark-mode
finance cockpit, not a marketing landing page. The first screen is the dashboard.

The shell includes:

- Collapsible desktop sidebar with Lucide icons.
- Sticky top header with QuantFish brand, live status, theme toggle, and language
  toggle.
- Mobile bottom navigation.
- Keyboard-visible focus states and semantic form/table markup.

Feature folders own page models, API calls, and components:

- `dashboard`: home KPIs, latest submissions, live system state.
- `submissions`: upload form, template/download actions, class settings panel.
- `leaderboard`: track toggle, search, sortable selectable table, compare action,
  pagination, top-rank medals, and status badges.
- `submission-detail`: equity/drawdown charts, KPI grid, score breakdown, trade
  summary tables, and error/empty states.
- `compare`: aligned equity/drawdown/KPI comparison for selected submissions.
- `admin`: segmented panels for overview, datasets, scoring, execution, teams,
  submissions, and toolbox.
- `mini-games`: public/teacher market classroom screen.

Use CSS variables for dark navy/charcoal surfaces, cyan accents, emerald success,
red drawdown/failure, amber queued/warning, and muted gray text. Numeric metrics
use tabular figures.

## Contracts

Pydantic schemas are the canonical backend contract. The frontend uses generated
or hand-typed TypeScript mirrors in a small API client until OpenAPI generation
is added. Route handlers translate HTTP and never contain workflow logic.

## Testing And Verification

Backend:

- Existing Python tests remain green.
- Add domain tests for ranking, staleness, report artifact reading, and
  mini-game settlement.
- Add service tests with temporary repositories and tiny data fixtures.
- Add FastAPI contract tests for upload, leaderboard, detail, compare, admin, and
  mini-game routes.

Frontend:

- Add Vitest and Testing Library tests for API client states, upload form
  validation, leaderboard sorting/selection, and admin panel rendering.
- Verify a production build.

Operational:

- Backend binds to `0.0.0.0` for LAN access.
- Frontend dev server binds to `0.0.0.0`.
- The backend serves the built frontend for a one-process classroom run.

## Implementation Waves

1. Backend runtime settings, schemas, repositories, and scoring service.
2. Backend routes for submissions, leaderboard, detail, comparison, admin,
   downloads, and mini-games.
3. Frontend project scaffold, shared shell, tokens, API client, and layout.
4. Student screens: dashboard, submit, leaderboard, detail, compare.
5. Instructor and mini-game screens.
6. LAN smoke verification, documentation, and final review.
