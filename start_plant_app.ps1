param(
  [string]$HostAddress = "0.0.0.0",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$runtimeDir = Join-Path $projectRoot "runtime"
if (-not (Test-Path -LiteralPath $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

$logFile = Join-Path $runtimeDir "plant_app.log"

function Test-PythonRuntime {
  param(
    [string]$PythonExe
  )

  try {
    & $PythonExe "-c" "import fastapi, jinja2, multipart" *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Resolve-PythonExe {
  $localCandidates = @(
    (Join-Path $projectRoot ".venv\Scripts\python.exe"),
    (Join-Path $projectRoot "venv\Scripts\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe")
  )

  $installedPythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
  if (Test-Path -LiteralPath $installedPythonRoot) {
    $localCandidates += Get-ChildItem -Path $installedPythonRoot -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty FullName
  }

  foreach ($candidate in ($localCandidates | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $candidate) {
      if (Test-PythonRuntime $candidate) {
        return $candidate
      }
    }
  }

  foreach ($commandName in @("py", "python")) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($command -and (Test-PythonRuntime $command.Source)) {
      return $command.Source
    }
  }

  throw "No suitable Python runtime was found. Install the app dependencies into a local Python/virtual environment, then run this launcher again."
}

$pythonExe = Resolve-PythonExe
$env:PLANT_APP_HOST = $HostAddress
$env:PLANT_APP_PORT = [string]$Port

$startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -LiteralPath $logFile -Value "`n[$startedAt] Starting Plant App on $HostAddress`:$Port"

& $pythonExe "app.py" *>> $logFile
$exitCode = $LASTEXITCODE

$stoppedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -LiteralPath $logFile -Value "[$stoppedAt] Plant App stopped with exit code $exitCode"

exit $exitCode
