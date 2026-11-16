$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$Platform,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeZip,

    [string]$Manifest = ""
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeRoot = if ($env:QUANTFISH_RUNTIME_ROOT) { $env:QUANTFISH_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runs/web_platform" }
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

$ImportArgs = @(
    "--platform", $Platform,
    "--zip", $RuntimeZip,
    "--runtime-root", $RuntimeRoot,
    "--project-root", $ProjectRoot
)
if ($Manifest) {
    $ImportArgs += @("--manifest", $Manifest)
}

& $PythonExecutable @PythonArguments -m quantfish.student_exports.runtime_packages import @ImportArgs
& $PythonExecutable @PythonArguments -m quantfish.student_exports.monitor refresh `
    --config (Join-Path $ProjectRoot "config/platform.yaml") `
    --runtime-root $RuntimeRoot `
    --project-root $ProjectRoot
