param(
  [string]$OutputRoot = (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "dist"),
  [string]$PackageName = "LAG-Plant-App-Installer",
  [switch]$Zip,
  [switch]$DownloadWheels
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Join-Path $OutputRoot $PackageName
$zipPath = Join-Path $OutputRoot "$PackageName.zip"

function Copy-PackageFiles {
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

    $destination = Join-Path $To $relativePath
    $destinationDirectory = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationDirectory)) {
      New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
    }

    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
  }
}

function Resolve-PythonExe {
  $commands = @("py", "python")
  foreach ($commandName in $commands) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if (-not $command) {
      continue
    }

    if ($commandName -eq "py") {
      & $command.Source -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
    } else {
      & $command.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
    }

    if ($LASTEXITCODE -eq 0) {
      if ($commandName -eq "py") {
        $commandArguments = [string[]]@("-3")
      } else {
        $commandArguments = [string[]]@()
      }

      return [PSCustomObject]@{
        FilePath = $command.Source
        Arguments = $commandArguments
      }
    }
  }

  return $null
}

if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot "app.py"))) {
  throw "Run this script from the Plant App source folder."
}

if (-not (Test-Path -LiteralPath $OutputRoot)) {
  New-Item -ItemType Directory -Path $OutputRoot | Out-Null
}

Copy-PackageFiles -From $sourceRoot -To $packageRoot

if ($DownloadWheels) {
  $python = Resolve-PythonExe
  if (-not $python) {
    throw "Python 3.10 or newer is required to download offline wheels."
  }

  $wheelhouse = Join-Path $packageRoot "wheelhouse"
  if (-not (Test-Path -LiteralPath $wheelhouse)) {
    New-Item -ItemType Directory -Path $wheelhouse | Out-Null
  }

  $pipArgs = @($python.Arguments) + @("-m", "pip", "download", "-r", (Join-Path $sourceRoot "requirements.txt"), "-d", $wheelhouse)
  & $python.FilePath @pipArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Could not download offline dependency wheels."
  }
}

if ($Zip) {
  Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force
}

Write-Host "Install package folder: $packageRoot"
if ($Zip) {
  Write-Host "Install package zip: $zipPath"
}
Write-Host "On the other Windows device, run Install-LAGPlantApp.ps1 from the copied package folder."
