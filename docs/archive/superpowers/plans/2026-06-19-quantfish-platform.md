# QuantFish Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working LAN-accessible QuantFish classroom quant backtesting website on top of the existing QuantFish backend.

**Architecture:** Add backend support first using feature-owned FastAPI modules that wrap the existing data, strategy execution, backtest, report, and config engines. Then add a Vite React frontend whose feature folders consume the backend JSON contracts and render the requested finance cockpit screens.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, JSON file repositories, existing QuantFish/pandas/pyarrow backtest engine, Vite, React, TypeScript, Recharts, Lucide icons, Vitest, Testing Library.

---

## File Structure

Backend files:

- Create `src/quantfish/web_app/settings.py`: runtime directories, upload limits, engine version, static frontend path.
- Create `src/quantfish/web_app/app.py`: FastAPI app factory, CORS, router registration, health route, static frontend mount.
- Create `src/quantfish/web_app/schemas.py`: shared Pydantic response/status schemas.
- Create `src/quantfish/submissions/models.py`: Team, Submission, SubmissionStatus, fingerprints, report summary dataclasses.
- Create `src/quantfish/submissions/repository.py`: atomic JSON repositories for teams and submissions.
- Create `src/quantfish/submissions/storage.py`: strategy upload storage, report directory ownership, template/download helpers.
- Create `src/quantfish/submissions/staleness.py`: pure fingerprint and stale-result rules.
- Create `src/quantfish/submissions/report_artifacts.py`: read existing report artifacts into frontend-safe JSON payloads.
- Create `src/quantfish/submissions/service.py`: upload/authenticate/score/rerun/export workflow.
- Create `src/quantfish/submissions/routes.py`: submission upload/detail/download route contracts.
- Create `src/quantfish/leaderboard/ranking.py`: pure ranking and scoring weights.
- Create `src/quantfish/leaderboard/routes.py`: leaderboard and dashboard API routes.
- Create `src/quantfish/result_comparison/service.py`: align and summarize multiple submissions.
- Create `src/quantfish/result_comparison/routes.py`: comparison route.
- Create `src/quantfish/admin_console/service.py`: config/team/submission/admin toolbox workflow wrapper.
- Create `src/quantfish/admin_console/routes.py`: admin routes.
- Create `src/quantfish/mini_games/models.py`: classroom market dataclasses.
- Create `src/quantfish/mini_games/service.py`: pure market setup/trade/settlement/ranking logic plus JSON repository.
- Create `src/quantfish/mini_games/routes.py`: public/teacher mini-game routes.
- Modify `pyproject.toml`: add FastAPI dependencies and `quantfish-web` console script.
- Modify `README.md`: document LAN run commands.

Backend tests:

- Create `tests/test_web_staleness.py`.
- Create `tests/test_leaderboard_ranking.py`.
- Create `tests/test_submission_service.py`.
- Create `tests/test_web_api.py`.
- Create `tests/test_mini_games.py`.

Frontend files:

- Create `frontend/package.json`, `frontend/index.html`, `frontend/tsconfig*.json`, `frontend/vite.config.ts`.
- Create `frontend/src/main.tsx`, `frontend/src/app/App.tsx`, `frontend/src/app/shell/*`.
- Create `frontend/src/shared/api/client.ts`, `frontend/src/shared/ui/*`, `frontend/src/shared/charts/*`, `frontend/src/shared/formatting/*`.
- Create feature folders under `frontend/src/features/{dashboard,submissions,leaderboard,submission-detail,compare,admin,mini-games}`.
- Create `frontend/src/styles.css`.
- Create frontend tests under `frontend/src/**/*.test.tsx`.

## Task 1: Backend Web Runtime

**Files:**
- Create: `src/quantfish/web_app/settings.py`
- Create: `src/quantfish/web_app/app.py`
- Create: `src/quantfish/web_app/schemas.py`
- Create: `src/quantfish/web_app/__init__.py`
- Modify: `pyproject.toml`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write failing API smoke tests**

Add tests proving `create_app()` returns health/config status and that app state has a runtime service container:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from quantfish.web_app.app import create_app
from quantfish.web_app.settings import WebSettings


def test_health_route_reports_runtime_status(tmp_path: Path) -> None:
    app = create_app(WebSettings(runtime_root=tmp_path / "runtime"))
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app"] == "QuantFish"
```

- [ ] **Step 2: Verify red**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_web_api.py::test_health_route_reports_runtime_status -v
```

Expected: fail because `quantfish.web_app` does not exist.

- [ ] **Step 3: Implement minimal runtime**

Implement settings, app factory, `/api/health`, CORS for LAN dev, and console script entrypoint. Keep routes thin and service initialization out of handlers.

- [ ] **Step 4: Verify green and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_web_api.py -v
```

Commit:

```bash
git add pyproject.toml src/quantfish/web_app tests/test_web_api.py
git commit -m "feat: add QuantFish web runtime"
```

## Task 2: Submission Domain And Scoring Service

**Files:**
- Create: `src/quantfish/submissions/models.py`
- Create: `src/quantfish/submissions/repository.py`
- Create: `src/quantfish/submissions/storage.py`
- Create: `src/quantfish/submissions/staleness.py`
- Create: `src/quantfish/submissions/report_artifacts.py`
- Create: `src/quantfish/submissions/service.py`
- Create: `src/quantfish/submissions/__init__.py`
- Test: `tests/test_web_staleness.py`
- Test: `tests/test_submission_service.py`

- [ ] **Step 1: Write failing pure/domain tests**

Cover strategy SHA fingerprints, config/release fingerprints, stale detection, team authentication, upload extension validation, and report artifact reading with temp directories.

- [ ] **Step 2: Verify red**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_web_staleness.py tests/test_submission_service.py -v
```

Expected: fail because submission modules do not exist.

- [ ] **Step 3: Implement domain/service**

Use JSON repositories under `runtime_root`. Keep the runner dependency injectable so tests can use a fake runner. The real runner adapter calls `run_student_backtest()` and `write_backtest_report()` with the configured hidden release root.

- [ ] **Step 4: Verify green and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_web_staleness.py tests/test_submission_service.py -v
```

Commit:

```bash
git add src/quantfish/submissions tests/test_web_staleness.py tests/test_submission_service.py
git commit -m "feat: add submission scoring service"
```

## Task 3: Leaderboard, Comparison, Admin, And Mini-Game Backend

**Files:**
- Create: `src/quantfish/leaderboard/ranking.py`
- Create: `src/quantfish/leaderboard/routes.py`
- Create: `src/quantfish/leaderboard/__init__.py`
- Create: `src/quantfish/result_comparison/service.py`
- Create: `src/quantfish/result_comparison/routes.py`
- Create: `src/quantfish/result_comparison/__init__.py`
- Create: `src/quantfish/admin_console/service.py`
- Create: `src/quantfish/admin_console/routes.py`
- Create: `src/quantfish/admin_console/__init__.py`
- Create: `src/quantfish/mini_games/models.py`
- Create: `src/quantfish/mini_games/service.py`
- Create: `src/quantfish/mini_games/routes.py`
- Create: `src/quantfish/mini_games/__init__.py`
- Modify: `src/quantfish/web_app/app.py`
- Test: `tests/test_leaderboard_ranking.py`
- Test: `tests/test_mini_games.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write failing backend feature tests**

Test leaderboard ordering, stale badges, detail route shape, comparison alignment, admin settings payload, mini-game settlement, and mini-game route contracts.

- [ ] **Step 2: Verify red**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_leaderboard_ranking.py tests/test_mini_games.py tests/test_web_api.py -v
```

Expected: fail for missing route/features.

- [ ] **Step 3: Implement feature services and routes**

Register routes under `/api/dashboard`, `/api/submissions`, `/api/leaderboard`, `/api/compare`, `/api/admin`, and `/api/mini-games/market`. Routes translate HTTP and call feature services.

- [ ] **Step 4: Verify green and commit**

Run:

```bash
conda run -n QuantFish python -m pytest tests/test_leaderboard_ranking.py tests/test_mini_games.py tests/test_web_api.py -v
```

Commit:

```bash
git add src/quantfish/leaderboard src/quantfish/result_comparison src/quantfish/admin_console src/quantfish/mini_games src/quantfish/web_app tests/test_leaderboard_ranking.py tests/test_mini_games.py tests/test_web_api.py
git commit -m "feat: add classroom platform APIs"
```

## Task 4: Frontend Scaffold And Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/shell/*`
- Create: `frontend/src/shared/api/client.ts`
- Create: `frontend/src/shared/ui/*`
- Create: `frontend/src/shared/formatting/*`
- Test: `frontend/src/app/App.test.tsx`

- [ ] **Step 1: Create failing frontend tests**

Test that the app shell renders QuantFish, desktop navigation, mobile navigation, live status, theme toggle, and language toggle.

- [ ] **Step 2: Verify red**

Run:

```bash
cd frontend && npm test -- --run src/app/App.test.tsx
```

Expected: fail because frontend files do not exist.

- [ ] **Step 3: Implement scaffold and shell**

Build a dark-mode cockpit shell using Lucide icons, semantic landmarks, responsive desktop sidebar and mobile bottom nav, and CSS variables.

- [ ] **Step 4: Verify green and commit**

Run:

```bash
cd frontend && npm test -- --run src/app/App.test.tsx
cd frontend && npm run build
```

Commit:

```bash
git add frontend
git commit -m "feat: add QuantFish frontend shell"
```

## Task 5: Student Frontend Screens

**Files:**
- Create: `frontend/src/features/dashboard/*`
- Create: `frontend/src/features/submissions/*`
- Create: `frontend/src/features/leaderboard/*`
- Create: `frontend/src/features/submission-detail/*`
- Create: `frontend/src/features/compare/*`
- Create: `frontend/src/shared/charts/*`
- Modify: `frontend/src/app/App.tsx`
- Test: `frontend/src/features/**/*.test.tsx`

- [ ] **Step 1: Write failing student screen tests**

Test upload validation, template buttons, leaderboard sorting/selection, compare action, detail KPI/chart rendering, empty state, and error state.

- [ ] **Step 2: Verify red**

Run:

```bash
cd frontend && npm test -- --run src/features
```

Expected: fail for missing features.

- [ ] **Step 3: Implement screens**

Use the shared API client, status badges, compact tables, KPI cards, Recharts charts, search/filter controls, pagination, and accessible forms.

- [ ] **Step 4: Verify green and commit**

Run:

```bash
cd frontend && npm test -- --run src/features
cd frontend && npm run build
```

Commit:

```bash
git add frontend/src
git commit -m "feat: add student platform screens"
```

## Task 6: Admin, Mini Games, LAN Run Docs, And Final Verification

**Files:**
- Create: `frontend/src/features/admin/*`
- Create: `frontend/src/features/mini-games/*`
- Modify: `frontend/src/app/App.tsx`
- Modify: `README.md`
- Test: `frontend/src/features/admin/*.test.tsx`
- Test: `frontend/src/features/mini-games/*.test.tsx`

- [ ] **Step 1: Write failing instructor/game tests**

Test admin tabs, settings forms, team table, toolbox actions, public game mode, teacher game mode, trade tape, ledger, and settlement panels.

- [ ] **Step 2: Verify red**

Run:

```bash
cd frontend && npm test -- --run src/features/admin src/features/mini-games
```

Expected: fail for missing panels.

- [ ] **Step 3: Implement instructor and game screens**

Use segmented controls, dense panels, state badges, forms, and Recharts for live market data. Keep all in-app text bilingual-ready through local label objects.

- [ ] **Step 4: Verify all and commit**

Run:

```bash
conda run -n QuantFish python -m pytest
cd frontend && npm test -- --run
cd frontend && npm run build
```

Commit:

```bash
git add frontend README.md
git commit -m "feat: add instructor and mini-game screens"
```

- [ ] **Step 5: LAN smoke**

Run backend:

```bash
conda run -n QuantFish quantfish-web --host 0.0.0.0 --port 8000
```

Run frontend during development:

```bash
cd frontend && npm run dev -- --host 0.0.0.0
```

Check:

- `http://localhost:8000/api/health`
- `http://localhost:5173/`
- One upload flow with a tiny strategy fixture or explicit missing-data error.
