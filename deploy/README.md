# Docker demo

One command, real engine, no market data required:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Then open <http://localhost:8010>.

## What happens on first boot

| Step | Where | What |
| --- | --- | --- |
| 1 | image build | `scripts/gen_sample_dataset.py` writes a synthetic CSMAR-style dataset and builds `learning`, `learning_1..3` and `hidden_test` releases |
| 2 | container start | `entrypoint.sh` generates admin/session secrets, prints the admin password, and verifies the releases exist |
| 3 | container start | `seed_demo.py` creates the `Alpha Desk` and `Beta Desk` teams and queues one submission each |
| 4 | server start | the FastAPI lifespan starts the scoring dispatcher, which scores both submissions with the real engine |
| 5 | afterwards | results, artifacts and the PDF report are served from the `quantfish-runtime` volume |

The PDF report needs `weasyprint` + Pango, which the image installs together with
Noto CJK fonts (`pip install './backend[pdf]'`).

## Useful commands

```bash
docker compose -f deploy/docker-compose.yml logs -f          # follow server logs
docker compose -f deploy/docker-compose.yml exec quantfish \
  python -c "import quantfish; print(quantfish.__version__)"  # sanity check
docker compose -f deploy/docker-compose.yml down -v          # reset everything
```

## Health

`docker compose … ps` reports `healthy` once `/api/ready` answers `200`; the
image's `HEALTHCHECK` and the compose override both run
[`deploy/healthcheck.py`](healthcheck.py), which exits `1` on a `503`, a refused
connection or a slow answer and prints the readiness payload so the reason shows
up in `docker inspect`:

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml exec quantfish python deploy/healthcheck.py
docker inspect --format '{{json .State.Health}}' \
  "$(docker compose -f deploy/docker-compose.yml ps -q quantfish)" | python -m json.tool
```

## Ports and state

- `8010` is the only exposed port; the API and the built frontend share it.
- `runs/` lives in the named volume `quantfish-runtime`, so submissions survive
  restarts. Delete the volume to get a clean demo.

## Without Docker

`scripts/gen_sample_dataset.py` + `scripts/start-quantfish.sh --mode prod
--config config/platform.demo.yaml` gives you the same experience locally.

## GitHub Pages demo (one-time setup)

`.github/workflows/pages.yml` publishes the static mock-api build to
`https://<owner>.github.io/<repo>/` on every push to `main`. GitHub does not let
the workflow create the site itself, so a repository admin enables it once:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**
2. Re-run the `Demo (GitHub Pages)` workflow (or push to `main`)

The base path comes from `github.event.repository.name`, so the site keeps
working if the repository is renamed. To publish the same build anywhere else:

```bash
VITE_DEMO_MODE=true VITE_BASE_PATH=/quantfish/ npm --prefix frontend run build
# frontend/dist/ is a fully static bundle, no backend needed
```

