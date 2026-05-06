param(
  [string]$InstallPath = (Join-Path $env:LOCALAPPDATA "LAG Plant App"),
  [int]$Port = 8000,
  [switch]$NoStartupShortcut,
  [switch]$NoTaskbarPin,
  [switch]$EnableLanAccess,
  [switch]$SkipDependencyInstall,
  [switch]$OverwriteDatabase
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installRoot = [System.IO.Path]::GetFullPath($InstallPath)
$venvPath = Join-Path $installRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$requirementsPath = Join-Path $installRoot "requirements.txt"
$wheelhousePath = Join-Path $sourceRoot "wheelhouse"

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "== $Message =="
}

function Test-SamePath {
  param(
    [string]$Left,
    [string]$Right
  )

  $leftFull = [System.IO.Path]::GetFullPath($Left).TrimEnd([char[]]@("\", "/"))
  $rightFull = [System.IO.Path]::GetFullPath($Right).TrimEnd([char[]]@("\", "/"))
  return $leftFull.Equals($rightFull, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-PythonCommand {
  param(
    [string]$FilePath,
    [string[]]$Arguments = @()
  )

  try {
    $testArgs = @($Arguments) + @(
      "-c",
      "import sys, venv; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    )
    & $FilePath @testArgs *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Get-PythonDescription {
  param(
    [string]$FilePath,
    [string[]]$Arguments = @()
  )

  try {
    $versionArgs = @($Arguments) + @(
      "-c",
      "import sys; print(sys.executable + ' ' + sys.version.split()[0])"
    )
    return ((& $FilePath @versionArgs) -join " ").Trim()
  } catch {
    return $FilePath
  }
}

function Resolve-PythonCommand {
  $commands = @()

  $pyCommand = Get-Command "py" -ErrorAction SilentlyContinue
  if ($pyCommand) {
    foreach ($pyVersion in @("-3.12", "-3.11", "-3.10", "-3")) {
      $commands += [PSCustomObject]@{
        FilePath = $pyCommand.Source
        Arguments = [string[]]@($pyVersion)
      }
    }
  }

  $pythonCommand = Get-Command "python" -ErrorAction SilentlyContinue
  if ($pythonCommand) {
    $commands += [PSCustomObject]@{
      FilePath = $pythonCommand.Source
      Arguments = [string[]]@()
    }
  }

  $pythonRoots = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python"),
    (Join-Path $env:ProgramFiles "Python*")
  )

  foreach ($pythonRoot in $pythonRoots) {
    if (-not (Test-Path -Path $pythonRoot)) {
      continue
    }

    $commands += Get-ChildItem -Path $pythonRoot -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty FullName |
      ForEach-Object {
        [PSCustomObject]@{
          FilePath = $_
          Arguments = [string[]]@()
        }
      }
  }

  foreach ($candidate in $commands) {
    if ((Test-Path -LiteralPath $candidate.FilePath) -and (Test-PythonCommand -FilePath $candidate.FilePath -Arguments @($candidate.Arguments))) {
      return $candidate
    }
  }

  return $null
}

function Install-PythonWithWinget {
  $winget = Get-Command "winget" -ErrorAction SilentlyContinue
  if (-not $winget) {
    Write-Warning "Python 3 was not found and winget is not available to install it automatically."
    return $false
  }

  Write-Host "Python 3 was not found. Trying to install Python with winget..."
  & $winget.Source install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    return $false
  }

  return $true
}

function Copy-AppFiles {
  param(
    [string]$From,
    [string]$To
  )

  $skipDirectories = @(".git", ".venv", "venv", "__pycache__", "runtime", "dist", "wheelhouse")
  $skipExtensions = @(".pyc")

  if (-not (Test-Path -LiteralPath $To)) {
    New-Item -ItemType Directory -Path $To | Out-Null
  }

  $sourcePrefix = [System.IO.Path]::GetFullPath($From).TrimEnd([char[]]@("\", "/"))
  $files = Get-ChildItem -LiteralPath $From -Recurse -File -Force

  foreach ($file in $files) {
    $relativePath = $file.FullName.Substring($sourcePrefix.Length).TrimStart([char[]]@("\", "/"))
    $segments = $relativePath -split "[\\/]+"
    $blockedSegment = $segments | Where-Object { $skipDirectories -contains $_ } | Select-Object -First 1

    if ($blockedSegment) {
      continue
    }

    if ($skipExtensions -contains $file.Extension.ToLowerInvariant()) {
      continue
    }

    if ((-not $OverwriteDatabase) -and $relativePath.Equals("plant.db", [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath (Join-Path $To $relativePath))) {
      Write-Host "Keeping existing database: $(Join-Path $To $relativePath)"
      continue
    }

    $destination = Join-Path $To $relativePath
    $destinationDirectory = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationDirectory)) {
      New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
    }

    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
  }
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$FailureMessage
  )

  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw $FailureMessage
  }
}

if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot "app.py"))) {
  throw "This installer must be run from the Plant App installer folder, next to app.py."
}

Write-Step "Installing app files"
if (Test-SamePath -Left $sourceRoot -Right $installRoot) {
  Write-Host "Source and install folder are the same: $installRoot"
} else {
  Copy-AppFiles -From $sourceRoot -To $installRoot
  Write-Host "Installed files to: $installRoot"
}

if (-not (Test-Path -LiteralPath $requirementsPath)) {
  throw "Missing requirements file after copy: $requirementsPath"
}

Write-Step "Preparing Python environment"
if (-not (Test-Path -LiteralPath $venvPython)) {
  $python = Resolve-PythonCommand
  if (-not $python) {
    if (Install-PythonWithWinget) {
      $python = Resolve-PythonCommand
    }
  }

  if (-not $python) {
    throw "Python 3.10 or newer is required. Install Python from https://www.python.org/downloads/windows/ and run this installer again."
  }

  $venvArgs = @($python.Arguments) + @("-m", "venv", $venvPath)
  Write-Host "Using Python: $(Get-PythonDescription -FilePath $python.FilePath -Arguments @($python.Arguments))"
  Invoke-Checked -FilePath $python.FilePath -Arguments $venvArgs -FailureMessage "Could not create the local Python environment."
  Write-Host "Created local Python environment: $venvPath"
} else {
  Write-Host "Using existing Python environment: $venvPath"
}

if (-not $SkipDependencyInstall) {
  Write-Step "Installing Python packages"
  Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -FailureMessage "Could not update pip."

  if (Test-Path -LiteralPath $wheelhousePath) {
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--no-index", "--find-links", $wheelhousePath, "-r", $requirementsPath) -FailureMessage "Could not install packages from the bundled wheelhouse."
  } else {
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", $requirementsPath) -FailureMessage "Could not install packages from requirements.txt."
  }
} else {
  Write-Host "Skipped dependency installation."
}

Write-Step "Checking app imports"
Invoke-Checked -FilePath $venvPython -Arguments @("-c", "import fastapi, uvicorn, jinja2, multipart, itsdangerous, pyodbc; print('Import check OK')") -FailureMessage "The app dependencies are not ready."

Write-Step "Creating Windows shortcuts"
$shortcutInstaller = Join-Path $installRoot "install_windows_app.ps1"
$setStartup = -not $NoStartupShortcut
$tryPinTaskbar = -not $NoTaskbarPin
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $shortcutInstaller -SetStartup:$setStartup -TryPinTaskbar:$tryPinTaskbar
if ($LASTEXITCODE -ne 0) {
  throw "Shortcut installation failed."
}

if ($EnableLanAccess) {
  Write-Step "Enabling LAN startup access"
  $deviceAccessInstaller = Join-Path $installRoot "install_device_access.ps1"
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deviceAccessInstaller -Port $Port
  if ($LASTEXITCODE -ne 0) {
    throw "LAN access setup failed."
  }
}

Write-Step "Done"
Write-Host "Installed to: $installRoot"
Write-Host "Open it from the Desktop or Start Menu shortcut named LAG Plant App."
Write-Host "To launch directly: $installRoot\launch_plant_desktop_app.vbs"
