$ErrorActionPreference = "Stop"

param(
    [string]$Platform = "windows-x86_64"
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputDir = if ($env:QUANTFISH_RUNTIME_OUTPUT_DIR) { $env:QUANTFISH_RUNTIME_OUTPUT_DIR } else { Join-Path $ProjectRoot "dist/offline-runtimes" }
$BuildRoot = if ($env:QUANTFISH_RUNTIME_BUILD_ROOT) { $env:QUANTFISH_RUNTIME_BUILD_ROOT } else { Join-Path $ProjectRoot ".runtime-build/offline-runtimes" }
$PipIndexUrl = if ($env:QUANTFISH_PIP_INDEX_URL) { $env:QUANTFISH_PIP_INDEX_URL } else { "https://pypi.tuna.tsinghua.edu.cn/simple" }
$CondaEnv = if ($env:QUANTFISH_CONDA_ENV) { $env:QUANTFISH_CONDA_ENV } else { "QuantFish" }

Set-Location $ProjectRoot
$env:PYTHONPATH = (Join-Path $ProjectRoot "src") + [System.IO.Path]::PathSeparator + $env:PYTHONPATH

if ($env:QUANTFISH_PYTHON) {
    $PythonCommand = @($env:QUANTFISH_PYTHON)
} elseif ($env:CONDA_DEFAULT_ENV -eq $CondaEnv) {
    $PythonCommand = @("python")
} else {
    $PythonCommand = @("conda", "run", "-n", $CondaEnv, "python")
}
$PythonExecutable = $PythonCommand[0]
$PythonArguments = if ($PythonCommand.Count -gt 1) { $PythonCommand[1..($PythonCommand.Count - 1)] } else { @() }

& $PythonExecutable @PythonArguments -m quantfish.student_exports.runtime_packages build `
    --platform $Platform `
    --project-root $ProjectRoot `
    --output-dir $OutputDir `
    --build-root $BuildRoot `
    --pip-index-url $PipIndexUrl
