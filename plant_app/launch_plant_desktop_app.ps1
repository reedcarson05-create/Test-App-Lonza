param(
  [int]$Port = 8000,
  [switch]$SkipBrowser
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$runtimeDir = Join-Path $projectRoot "runtime"
if (-not (Test-Path -LiteralPath $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

$logFile = Join-Path $runtimeDir "desktop_app.log"
$windowUrl = "http://127.0.0.1:$Port"
$healthUrl = "$windowUrl/health"

function Write-LaunchLog {
  param(
    [string]$Message
  )

  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -LiteralPath $logFile -Value "[$stamp] $Message"
}

function Test-AppServerReady {
  param(
    [string]$Url
  )

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    return ($response.StatusCode -eq 200)
  } catch {
    return $false
  }
}

function Resolve-BrowserExe {
  $browserCandidates = @(
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
  )

  foreach ($candidate in $browserCandidates) {
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }

  throw "Microsoft Edge or Google Chrome is required to open the desktop app window."
}

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
    if ((Test-Path -LiteralPath $candidate) -and (Test-PythonRuntime $candidate)) {
      return $candidate
    }
  }

  foreach ($commandName in @("py", "python")) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($command -and (Test-PythonRuntime $command.Source)) {
      return $command.Source
    }
  }

  throw "No suitable Python runtime was found. Install the Plant App dependencies first."
}

if (-not (Test-AppServerReady -Url $healthUrl)) {
  $pythonExe = Resolve-PythonExe
  $env:PLANT_APP_HOST = "0.0.0.0"
  $env:PLANT_APP_PORT = [string]$Port
  $env:PLANT_APP_SQLITE_PATH = "plant.db"

  Write-LaunchLog "Server not running on port $Port, starting background host with $pythonExe."
  Start-Process -FilePath $pythonExe -ArgumentList "app.py" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null

  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    if (Test-AppServerReady -Url $healthUrl) {
      break
    }
    Start-Sleep -Milliseconds 250
  }
}

if (-not (Test-AppServerReady -Url $healthUrl)) {
  throw "The Plant App server did not become ready on $windowUrl."
}

if (-not $SkipBrowser) {
  $browserExe = Resolve-BrowserExe
  $browserArguments = @(
    "--new-window",
    "--app=$windowUrl",
    "--disable-http-cache",
    "--window-size=1460,960"
  )

  Write-LaunchLog "Opening desktop app window in $browserExe"
  Start-Process -FilePath $browserExe -ArgumentList $browserArguments | Out-Null
}
