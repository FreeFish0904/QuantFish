# Observability

QuantFish runs as one uvicorn process plus one short-lived `score_worker`
subprocess per submission. That is small enough to stay on the standard
library's `logging`; this document describes the contract so logs and probes
stay useful as the platform grows.

## Health vs. readiness

| Endpoint | Question it answers | Behaviour |
| --- | --- | --- |
| `GET /api/health` | Is the process alive? | Always `200` with `status: "ok"`. Cheap enough for a liveness probe. |
| `GET /api/ready` | Can this instance serve students right now? | `200` when every critical check passes, `503` otherwise. |

`/api/ready` returns a per-check payload:

```json
{
  "app": "QuantFish",
  "status": "degraded",
  "engine_version": "quantfish-0.1.0+source.abcdef123456",
  "checks": [
    {"name": "runtime_root", "critical": true, "ok": true, "detail": null},
    {"name": "frontend_bundle", "critical": false, "ok": false,
     "detail": "frontend build is missing; the API is up but the UI is not served"}
  ]
}
```

`status` is `ok` (all checks pass), `degraded` (only optional checks failed) or
`unavailable` (a critical check failed, HTTP `503`).

Checks live in `backend/src/quantfish/web_app/readiness.py`:

| Check | Critical | What it proves |
| --- | --- | --- |
| `runtime_root` | yes | The runtime directory exists and accepts writes (a probe file is written and removed). |
| `submission_store` | yes | The SQLite submission store answers `SELECT 1`. |
| `platform_config` | yes | `config/platform.yaml` exists and parses into the frozen config tree. |
| `frontend_bundle` | no | `frontend/dist/index.html` is present, so the SPA is served. |
| `scoring_dispatcher` | no | The in-process queue is running; if it is not, uploads queue but never score. |

The container healthcheck (`deploy/Dockerfile`, `deploy/docker-compose.yml`)
probes `/api/ready`, so a container with a broken config reports unhealthy
instead of merely "process started".

## Log lines

`quantfish.observability.configure_logging()` installs a single stderr handler
whose format is `timestamp level logger event=<name> key=value …`. Keys are
sorted, values containing spaces are quoted, and `None` fields are dropped, so
lines stay greppable:

```text
2026-11-20T10:31:02+0800 INFO quantfish.web.request event=request duration_ms=12.4 method=POST path=/api/submissions request_id=9f2c1ad0b447 status=200
2026-11-20T10:31:19+0800 INFO quantfish.submissions.dispatcher event=score_completed data_track=hidden_test sharpe=1.42 submission_id=sub-123 team_id=team-alpha trading_days=250
```

Entry points:

- `QUANTFISH_LOG_LEVEL` (default `INFO`) raises or lowers verbosity; the value
  is read by `configure_logging()` and accepts standard level names.
- `configure_logging()` is idempotent, so `quantfish-web` and scripts can call
  it without duplicating handlers.

What is logged:

- one line per `/api/*` request (method, path, status, duration, request id),
  except `/api/health` and `/api/ready` which are quiet unless they fail;
- `score_started` / `score_completed` / `score_cancelled` / `score_failed` for
  every submission, with `submission_id`, `team_id` and `data_track`;
- `score_failed` keeps the **traceback** in the log. The database only stores
  `str(exc)` in `error_message`, which is enough for the UI but not for
  debugging;
- a failed `score_worker` subprocess logs its stderr tail (`stderr_tail=…`),
  on top of the `worker_error.log` and `worker_failure.json` written into the
  report directory.

What is never logged: request bodies, uploaded strategies, cookies,
authorization headers and session secrets.

## Correlation

Every request gets an `x-request-id` (12 hex characters, generated when the
caller does not supply one) and the same value is echoed back in the response
header. A student report ("my upload failed around 14:03") can therefore be
matched to the request line, the `score_started` line and the eventual
`score_failed` traceback.

## Running things

```bash
# watch the logs of a dev server started by scripts/start-quantfish.sh
QUANTFISH_LOG_LEVEL=DEBUG scripts/start-quantfish.sh --mode dev

# probe readiness the way the container does
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7860/api/ready
curl -s http://127.0.0.1:7860/api/ready | python -m json.tool
```
