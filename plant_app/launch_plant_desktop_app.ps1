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
$startupStdOutLog = ""
$startupStdErrLog = ""

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
  $script:startupStdOutLog = Join-Path $runtimeDir "startup-$ActivePort.out.log"
  $script:startupStdErrLog = Join-Path $runtimeDir "startup-$ActivePort.err.log"
}

Set-LaunchUrls -ActivePort $Port

function Write-LaunchLog {
  param(
    [string]$Message
  )

  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -LiteralPath $logFile -Value "[$stamp] $Message"
}

function Reset-StartupLogs {
  foreach ($startupLog in @($startupStdOutLog, $startupStdErrLog)) {
    Set-Content -LiteralPath $startupLog -Value ""
  }
}

function Get-StartupLogTail {
  param(
    [string]$Path,
    [int]$LineCount = 12
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    return ""
  }

  try {
    $lines = Get-Content -LiteralPath $Path -Tail $LineCount -ErrorAction Stop |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_ }
    return ($lines -join " | ")
  } catch {
    return ""
  }
}

function Write-StartupFailureDetails {
  if (-not $startupStdOutLog -or -not $startupStdErrLog) {
    return
  }

  Write-LaunchLog "Startup logs for port ${Port}: stdout=$startupStdOutLog stderr=$startupStdErrLog"

  $stderrTail = Get-StartupLogTail -Path $startupStdErrLog
  if ($stderrTail) {
    Write-LaunchLog "Startup stderr tail: $stderrTail"
  }

  $stdoutTail = Get-StartupLogTail -Path $startupStdOutLog
  if ($stdoutTail) {
    Write-LaunchLog "Startup stdout tail: $stdoutTail"
  }
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

function Get-AppServerStatus {
  param(
    [string]$Url
  )

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    if ($response.StatusCode -ne 200) {
      return $null
    }

    if (-not $response.Content) {
      return $null
    }

    return ($response.Content | ConvertFrom-Json)
  } catch {
    return $null
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

function Get-ListeningPortSet {
  $ports = New-Object 'System.Collections.Generic.HashSet[int]'

  try {
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    foreach ($listener in $listeners) {
      [void]$ports.Add([int]$listener.Port)
    }
  } catch {
  }

  return $ports
}

function Get-DesktopPortCandidates {
  param(
    [int]$PreferredPort
  )

  $legacyFallbackPorts = @(8011, 8012, 8013, 8020)
  $overflowFallbackPorts = 8021..8099
  return @($PreferredPort) + $legacyFallbackPorts + $overflowFallbackPorts | Select-Object -Unique
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

  $candidates = Get-DesktopPortCandidates -PreferredPort $PreferredPort
  $listeningPorts = Get-ListeningPortSet
  $firstAvailablePort = $null
  foreach ($candidate in $candidates) {
    if (-not $listeningPorts.Contains($candidate)) {
      if ($null -eq $firstAvailablePort) {
        $firstAvailablePort = $candidate
      }
      continue
    }

    $candidateHealth = "http://127.0.0.1:$candidate/health"
    $candidateBoot = "http://127.0.0.1:$candidate/boot"
    $candidateAppStatus = "http://127.0.0.1:$candidate/app-status"

    if (-not (Test-AppServerReady -Url $candidateHealth)) {
      continue
    }

    if ((Test-AppServerReady -Url $candidateBoot) -and (Test-AppServerReady -Url $candidateAppStatus)) {
      $status = Get-AppServerStatus -Url $candidateAppStatus
      if ($status -and (-not $status.restart_required)) {
        return $candidate
      }
    }
  }

  if ($null -ne $firstAvailablePort) {
    return $firstAvailablePort
  }

  throw "No available desktop launch port was found in the Plant App desktop range. Close any old Plant App windows and try again."
}

function Resolve-ReusableDesktopPort {
  param(
    [int]$PreferredPort
  )

  $candidates = Get-DesktopPortCandidates -PreferredPort $PreferredPort
  $listeningPorts = Get-ListeningPortSet
  foreach ($candidate in $candidates) {
    if (-not $listeningPorts.Contains($candidate)) {
      continue
    }

    $candidateHealth = "http://127.0.0.1:$candidate/health"
    $candidateBoot = "http://127.0.0.1:$candidate/boot"
    $candidateAppStatus = "http://127.0.0.1:$candidate/app-status"

    if ((Test-AppServerReady -Url $candidateHealth) -and (Test-AppServerReady -Url $candidateBoot) -and (Test-AppServerReady -Url $candidateAppStatus)) {
      $status = Get-AppServerStatus -Url $candidateAppStatus
      if ($status -and (-not $status.restart_required)) {
        return $candidate
      }
    }
  }

  return $null
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
    if (-not $candidate) {
      continue
    }

    $candidateExists = $false
    try {
      $candidateExists = Test-Path -LiteralPath $candidate -PathType Leaf -ErrorAction Stop
    } catch {
      continue
    }

    if ($candidateExists -and (Test-PythonRuntime $candidate)) {
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

if (Test-AppServerReady -Url $healthUrl) {
  $staleReasons = @()
  if (-not (Test-AppServerReady -Url $bootUrl)) {
    $staleReasons += "/boot was unavailable"
  }
  if (-not (Test-AppServerReady -Url $appStatusUrl)) {
    $staleReasons += "/app-status was unavailable"
  } else {
    $currentStatus = Get-AppServerStatus -Url $appStatusUrl
    if ($currentStatus -and $currentStatus.restart_required) {
      $loadedBuild = [string]$currentStatus.loaded_build_label
      $diskBuild = [string]$currentStatus.disk_build_label
      if ($loadedBuild -and $diskBuild) {
        $staleReasons += "the running app build ($loadedBuild) was older than disk ($diskBuild)"
      } else {
        $staleReasons += "the running app build was older than disk"
      }
    }
  }

  if ($staleReasons.Count) {
    $staleReason = $staleReasons -join " and "
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
}

if (-not (Test-AppServerReady -Url $healthUrl)) {
  $pythonExe = Resolve-PythonExe
  $env:PLANT_APP_HOST = "0.0.0.0"
  $env:PLANT_APP_PORT = [string]$Port

  Reset-StartupLogs
  Write-LaunchLog "Server not running on port $Port, starting background host with $pythonExe. Logs: stdout=$startupStdOutLog stderr=$startupStdErrLog"
  $serverProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList "app.py" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $startupStdOutLog `
    -RedirectStandardError $startupStdErrLog `
    -PassThru
  Write-LaunchLog "Background host started with PID $($serverProcess.Id)."

  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    if (Test-AppServerReady -Url $healthUrl) {
      break
    }
    Start-Sleep -Milliseconds 250
  }
}

if (-not (Test-AppServerReady -Url $healthUrl)) {
  Write-StartupFailureDetails
  $reusablePort = Resolve-ReusableDesktopPort -PreferredPort $Port
  if ($reusablePort -and ($reusablePort -ne $Port)) {
    Write-LaunchLog "Fresh restart on port $Port failed. Reusing active Plant App server on port $reusablePort."
    Set-LaunchUrls -ActivePort $reusablePort
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
