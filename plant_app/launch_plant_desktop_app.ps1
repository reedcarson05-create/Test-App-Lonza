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
$launchStamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$baseUrl = ""
$windowUrl = ""
$healthUrl = ""
$bootUrl = ""
$appStatusUrl = ""

function Set-LaunchUrls {
  param(
    [int]$ActivePort
  )

  $script:Port = $ActivePort
  $script:baseUrl = "http://127.0.0.1:$ActivePort"
  $script:windowUrl = "$script:baseUrl/boot?launch=$launchStamp"
  $script:healthUrl = "$script:baseUrl/health"
  $script:bootUrl = "$script:baseUrl/boot"
  $script:appStatusUrl = "$script:baseUrl/app-status"
}

Set-LaunchUrls -ActivePort $Port

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

function Get-PortOwnerProcess {
  param(
    [int]$LocalPort
  )

  try {
    $connection = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop |
      Select-Object -First 1
  } catch {
    return $null
  }

  if (-not $connection) {
    return $null
  }

  try {
    return Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction Stop
  } catch {
    return $null
  }
}

function Stop-StaleProjectServer {
  param(
    [int]$LocalPort,
    [string]$ExpectedRoot,
    [string]$Reason = "required routes were unavailable"
  )

  $owner = Get-PortOwnerProcess -LocalPort $LocalPort
  if (-not $owner) {
    return $false
  }

  $commandLine = [string]$owner.CommandLine
  $normalizedRoot = $ExpectedRoot.ToLowerInvariant()
  $looksLikeProjectServer = (
    $commandLine.ToLowerInvariant().Contains($normalizedRoot) -and
    $commandLine.ToLowerInvariant().Contains("app.py")
  )

  if (-not $looksLikeProjectServer) {
    throw "Port $LocalPort is already in use by another process and the launcher will not stop it automatically."
  }

  Write-LaunchLog "Stopping stale Plant App server process $($owner.ProcessId) because $Reason."
  Stop-Process -Id $owner.ProcessId -Force
  Start-Sleep -Milliseconds 700
  return $true
}

function Resolve-DesktopPort {
  param(
    [int]$PreferredPort
  )

  $candidates = @($PreferredPort, 8011, 8012, 8013, 8020) | Select-Object -Unique
  foreach ($candidate in $candidates) {
    $candidateHealth = "http://127.0.0.1:$candidate/health"
    $candidateBoot = "http://127.0.0.1:$candidate/boot"
    $candidateAppStatus = "http://127.0.0.1:$candidate/app-status"

    if (-not (Test-AppServerReady -Url $candidateHealth)) {
      return $candidate
    }

    if ((Test-AppServerReady -Url $candidateBoot) -and (Test-AppServerReady -Url $candidateAppStatus)) {
      return $candidate
    }
  }

  throw "No available desktop launch port was found. Close any old Plant App windows and try again."
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

if ((Test-AppServerReady -Url $healthUrl) -and ((-not (Test-AppServerReady -Url $bootUrl)) -or (-not (Test-AppServerReady -Url $appStatusUrl)))) {
  $staleReasons = @()
  if (-not (Test-AppServerReady -Url $bootUrl)) {
    $staleReasons += "/boot was unavailable"
  }
  if (-not (Test-AppServerReady -Url $appStatusUrl)) {
    $staleReasons += "/app-status was unavailable"
  }
  $staleReason = if ($staleReasons.Count) { $staleReasons -join " and " } else { "required routes were unavailable" }
  $stoppedStale = $false
  try {
    $stoppedStale = Stop-StaleProjectServer -LocalPort $Port -ExpectedRoot $projectRoot -Reason $staleReason
  } catch {
    Write-LaunchLog ("Could not stop the stale server on port {0}: {1}" -f $Port, $_.Exception.Message)
  }

  if (-not $stoppedStale) {
    $fallbackPort = Resolve-DesktopPort -PreferredPort $Port
    if ($fallbackPort -ne $Port) {
      Write-LaunchLog "Port $Port is serving an older app host ($staleReason). Switching desktop launch to port $fallbackPort."
      Set-LaunchUrls -ActivePort $fallbackPort
    }
  }
}

if (-not (Test-AppServerReady -Url $healthUrl)) {
  $pythonExe = Resolve-PythonExe
  $env:PLANT_APP_HOST = "0.0.0.0"
  $env:PLANT_APP_PORT = [string]$Port

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

if (-not (Test-AppServerReady -Url $bootUrl)) {
  throw "The Plant App server started, but the /boot route is unavailable. Restart the launcher after confirming the background host updated."
}

if (-not (Test-AppServerReady -Url $appStatusUrl)) {
  throw "The Plant App server started, but the /app-status route is unavailable. Restart the launcher after confirming the background host updated."
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
