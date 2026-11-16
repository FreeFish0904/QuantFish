# QuantFish Project Working Rules

This repository is expected to grow over time. Keep changes small, committed, and aligned with the design principles in `docs/design-principles.md`.

## Architecture Principles

- Design around domains and business capabilities, not broad technical buckets.
- Keep dependency direction one-way: UI -> API/client -> route -> service -> repository/adapter.
- Put workflows in application services; routes and pages should translate inputs and assemble outputs.
- Keep domain rules pure where possible, especially scoring, ranking, validation, settlement, and stale detection.
- Prefer feature-owned modules over shared utility files.
- Add boundaries only when they clarify ownership or isolate change; avoid layer theater.
- Keep contracts generated or centralized when frontend, backend, docs, and tests must agree.
- Design for deletion: a feature should be removable with limited unrelated damage.

## Coding Standards

- Name files and objects after the responsibility they own.
- Avoid large catch-all files such as `utils.py`, `api.ts`, or generic `helpers`.
- Prefer repository/adapter boundaries for storage, file systems, queues, runners, and external services.
- Keep pages and notebooks thin; extract state, workflow, and validation logic into feature-owned modules.
- Tests should cover domain rules, service workflows, API contracts, and critical user-visible behavior.

## Environment And Installs

- This project is called QuantFish.
- Preferred: a project virtualenv at `./.venv`; `scripts/start-quantfish.sh` uses it
  automatically when present.
- Fallback: the Conda environment `QuantFish` (`conda activate QuantFish`), Python 3.12.
- Both paths target Python 3.12+ (`backend/pyproject.toml` declares `>=3.12`).
- For future installs, use China-available mirrors when possible.
- Prefer Conda installs from Tsinghua mirrors:

```bash
conda install -n QuantFish --override-channels \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r \
  <package>
```

- For PyPI-only packages, prefer the Tsinghua PyPI mirror:

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>
```

## Repository Layout

- `backend/src/quantfish/` — the Python package (engine, API, queue, data releases).
- `backend/tests/` — pytest suite; run `python -m pytest backend/tests -q` from the root.
- `frontend/` — React + Vite SPA; one folder per screen under `frontend/src/features`.
- `config/` — `platform.yaml` (classroom) and `platform.demo.yaml` (synthetic demo).
- `deploy/` — Docker demo (`Dockerfile`, `docker-compose.yml`, entrypoint, seeding).
- `scripts/` — launchers, dataset generator, backups, runtime builders.
- Generated data lives in `data/` and `runs/`; both are git-ignored.

## Git Hygiene

- Keep commits focused and reviewable.
- Do not commit local datasets, generated outputs, caches, credentials, or environment folders.
- Before changing existing files, check `git status` and avoid overwriting unrelated user edits.
- When adding new modules, include the smallest useful verification path: unit tests, smoke tests, or a documented command.
