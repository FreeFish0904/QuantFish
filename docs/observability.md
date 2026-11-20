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

### The probe

Both container definitions run the same script, `deploy/healthcheck.py`, so the
check cannot drift between `docker build` and `docker compose up`:

```bash
python deploy/healthcheck.py                      # http://127.0.0.1:8010/api/ready
python deploy/healthcheck.py http://127.0.0.1:8011/api/ready
```

It exits `0` only for HTTP `200`; a `503`, a refused connection or a response
slower than its 3-second timeout exits `1`. The readiness body is echoed to
stderr on failure, so `docker compose logs` and
`docker inspect --format '{{json .State.Health}}'` show *which* check failed
rather than just "unhealthy". Docker's own `--timeout=5s` stays above the
script's timeout so the script wins the race and prints the reason.

| Situation | Probe output | Exit |
| --- | --- | --- |
| Ready (`status: "ok"`) | `healthy: … returned 200` | `0` |
| Degraded, only optional checks fail | `healthy: … returned 200` | `0` |
| A critical check fails | `unhealthy: … returned 503: {"status": "unavailable", …}` | `1` |
| Server stopped / wrong port | `unhealthy: … is unreachable (… Connection refused)` | `1` |

### Verifying it locally

Start the API the way the container does and probe it:

```bash
QUANTFISH_ADMIN_PASSWORD=demo-admin-pass \
QUANTFISH_ADMIN_SESSION_SECRET=hc-admin-secret \
QUANTFISH_PARTICIPANT_SESSION_SECRET=hc-participant-secret \
  ./.venv/bin/quantfish-web --host 127.0.0.1 --port 8013 \
    --config config/platform.demo.yaml --runtime-root /tmp/qf-hc-runtime &

./.venv/bin/python deploy/healthcheck.py http://127.0.0.1:8013/api/ready
# healthy: http://127.0.0.1:8013/api/ready returned 200   (exit 0)
```

Then prove the failure paths: remove the config file the instance was started
with (a critical check) and the probe turns red with the payload attached, and
stopping the process turns it red with `Connection refused`.

```bash
mv /tmp/qf-hc.yaml /tmp/qf-hc.yaml.bak
./.venv/bin/python deploy/healthcheck.py http://127.0.0.1:8014/api/ready
# unhealthy: … returned 503: {"status": "unavailable", … "platform_config" …}   (exit 1)

kill %1
./.venv/bin/python deploy/healthcheck.py http://127.0.0.1:8013/api/ready
# unhealthy: … is unreachable (<urlopen error [Errno 61] Connection refused>)   (exit 1)
```

`backend/tests/test_deploy_healthcheck.py` runs those cases against a throwaway
`http.server` instance, and `backend/tests/test_web_readiness.py` asserts that
both container definitions call the script and that it probes `/api/ready`
rather than `/api/health`.

The image itself was rebuilt and run to check the wiring end to end:

```text
docker build -f deploy/Dockerfile -t quantfish-demo:hc-check .   # ok
docker run -d --name qf-hc -p 8016:8010 quantfish-demo:hc-check
docker inspect --format '{{.State.Health.Status}}' qf-hc         # starting → healthy (10s)
docker inspect --format '{{range .State.Health.Log}}{{.ExitCode}} {{.Output}}{{end}}' qf-hc
# 0 healthy: http://127.0.0.1:8010/api/ready returned 200
docker exec qf-hc rm config/platform.demo.yaml                   # break a critical check
docker exec qf-hc python deploy/healthcheck.py                   # exit 1 + 503 payload
docker stop qf-hc && python deploy/healthcheck.py http://127.0.0.1:8016/api/ready
# exit 1: unreachable (Connection refused)
```

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

## Failure triage

`GET /api/admin/failures?days=7&limit=20` (admin session) answers the question
after a class upload: *why did these runs fail?*

- `status_counts` — how many submissions in the window are queued / running /
  completed / failed;
- `categories` — failures grouped into `timeout`, `stale_positions`,
  `invalid_signals`, `worker_crash`, `data_release` or `other`, each with a
  count and up to five submission ids;
- `recent_failures` — the newest failures with team, track, a 200-character
  error snippet, whether a raw log exists, and the `worker_failure.json` code.

Classification lives in `quantfish/submissions/failure_summary.py`: a machine
readable `worker_failure.json` code wins, otherwise the stored `error_message`
is matched against a small rule table. The admin console renders the same data
at the top of its submissions tab; clicking a row filters the table by that
submission id.

## Running things

```bash
# watch the logs of a dev server started by scripts/start-quantfish.sh
QUANTFISH_LOG_LEVEL=DEBUG scripts/start-quantfish.sh --mode dev

# probe readiness the way the container does
python deploy/healthcheck.py                       # exit 0 = serving students
curl -s http://127.0.0.1:7860/api/ready | python -m json.tool
```
