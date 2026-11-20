"""Container health probe for the demo image.

Both `deploy/Dockerfile` (`HEALTHCHECK`) and `deploy/docker-compose.yml` call
this script instead of carrying their own `python -c` one-liner, so the two
cannot drift and the same check can be run by hand:

    python deploy/healthcheck.py
    python deploy/healthcheck.py http://127.0.0.1:8011/api/ready

Exit status is `0` only for `HTTP 200`. Anything else -- a `503` with the
readiness payload, a refused connection, a timeout -- exits `1`, because that is
what Docker treats as unhealthy. The readiness body is echoed to stderr on
failure so `docker inspect --format '{{json .State.Health}}'` and
`docker compose logs` show *why* the instance is not serving.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8010/api/ready"
DEFAULT_TIMEOUT_SECONDS = 3.0


def _describe_body(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", "replace").strip()
    except OSError:  # pragma: no cover - defensive
        return ""
    return body[:400]


def main(
    argv: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> int:
    url = argv[1] if len(argv) > 1 else DEFAULT_URL
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        detail = _describe_body(error)
        message = f"unhealthy: {url} returned {error.code}"
        if detail:
            message = f"{message}: {detail}"
        print(message, file=sys.stderr)
        return 1
    except OSError as error:  # connection refused, DNS failure, timeout
        print(f"unhealthy: {url} is unreachable ({error})", file=sys.stderr)
        return 1
    if status != 200:
        print(f"unhealthy: {url} returned {status}", file=sys.stderr)
        return 1
    print(f"healthy: {url} returned 200")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
