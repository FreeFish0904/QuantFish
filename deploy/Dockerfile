# syntax=docker/dockerfile:1

# --- Frontend build -------------------------------------------------------
FROM node:20-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Runtime --------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QUANTFISH_HOST=0.0.0.0 \
    QUANTFISH_PORT=8010 \
    QUANTFISH_CONFIG=config/platform.demo.yaml \
    QUANTFISH_RUNTIME_ROOT=runs/web_platform

WORKDIR /app

# Pango/HarfBuzz power the optional PDF report renderer (weasyprint);
# Noto CJK keeps Chinese labels readable inside generated PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ ./backend/
RUN pip install './backend[pdf]'

# Take the bundle from the build stage above; the host copy is git-ignored and
# would not exist on a fresh clone.
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY config/ ./config/
COPY docs/ ./docs/
COPY examples/ ./examples/
COPY scripts/ ./scripts/
COPY deploy/entrypoint.sh deploy/seed_demo.py ./deploy/
RUN chmod +x ./deploy/entrypoint.sh

# Build the synthetic dataset into the image so the container starts fast.
RUN python scripts/gen_sample_dataset.py --config config/platform.demo.yaml

EXPOSE 8010

HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=12 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/api/health').status==200 else 1)"

ENTRYPOINT ["./deploy/entrypoint.sh"]
