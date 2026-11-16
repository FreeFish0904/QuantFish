# Offline Runtime Automation

QuantFish serves offline student environment packages from:

```text
runs/web_platform/exports/offline_runtimes/
```

Each platform needs a zip plus a JSON manifest:

```text
macos-arm64.zip
macos-arm64.json
macos-x86_64.zip
macos-x86_64.json
windows-x86_64.zip
windows-x86_64.json
```

The runtime zip is built with `conda-pack`, so students do not need internet access.
The generated student setup scripts run `conda-unpack` automatically when it exists.

## Build Locally

Build on the same operating system and CPU architecture as the target package.
Your Mac can build `macos-arm64` directly. Build `macos-x86_64` on an Intel Mac or
inside an x86_64 Conda/Rosetta setup. Build `windows-x86_64` on Windows.

macOS:

```bash
cd /path/to/quantfish
conda activate QuantFish
python -m pip install conda-pack

chmod +x scripts/build-offline-runtime.sh scripts/import-offline-runtime.sh
scripts/build-offline-runtime.sh macos-arm64
scripts/import-offline-runtime.sh \
  macos-arm64 \
  dist/offline-runtimes/macos-arm64.zip \
  dist/offline-runtimes/macos-arm64.json
```

Windows PowerShell:

```powershell
cd "C:\path\to\quantfish"
conda activate QuantFish
python -m pip install conda-pack

.\scripts\build-offline-runtime.ps1 -Platform windows-x86_64
.\scripts\import-offline-runtime.ps1 `
  -Platform windows-x86_64 `
  -RuntimeZip dist\offline-runtimes\windows-x86_64.zip `
  -Manifest dist\offline-runtimes\windows-x86_64.json
```

Importing a runtime also refreshes the student exports, so the submission-page
dropdown updates after the command finishes.

## Build In GitHub Actions

Run **Build Offline Runtimes** manually from the Actions tab. It is intentionally
not wired to `push`, because it spins up three full `conda-pack` builds (macOS
arm64, macOS x86_64, Windows) and takes tens of minutes:

- `macos-arm64`
- `macos-x86_64`
- `windows-x86_64`

Rebuild when `backend/pyproject.toml`, `backend/environment.yml`, the runtime
scripts or the student runner change. Download the three `offline-runtime-*`
artifacts, then import each zip and JSON manifest on the QuantFish host:

```bash
cd /path/to/quantfish
conda activate QuantFish

scripts/import-offline-runtime.sh macos-arm64 ~/Downloads/macos-arm64.zip ~/Downloads/macos-arm64.json
scripts/import-offline-runtime.sh macos-x86_64 ~/Downloads/macos-x86_64.zip ~/Downloads/macos-x86_64.json
scripts/import-offline-runtime.sh windows-x86_64 ~/Downloads/windows-x86_64.zip ~/Downloads/windows-x86_64.json
```

## Status Check

```bash
conda run -n QuantFish python -m quantfish.student_exports.monitor status \
  --config config/platform.yaml \
  --runtime-root runs/web_platform \
  --project-root .
```

If `pyproject.toml` or `environment.yml` changes, old runtime manifests become
stale. Rebuild the affected runtime artifacts and import them again.
