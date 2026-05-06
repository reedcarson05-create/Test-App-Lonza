param(
  [string]$OutputPath = (Join-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "dist") "Install-LAG-Plant-App.cmd"),
  [switch]$DownloadWheels
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$builderScript = Join-Path $sourceRoot "build_install_package.ps1"
$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $outputFullPath
$packageWorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("LAG-Plant-App-OneFile-Build-" + [System.Guid]::NewGuid().ToString("N"))
$packageName = "payload"
$packageRoot = Join-Path $packageWorkRoot $packageName
$payloadZip = Join-Path $packageWorkRoot "payload.zip"

function Split-Base64Lines {
  param(
    [string]$Value,
    [int]$LineLength = 76
  )

  $lines = New-Object System.Collections.Generic.List[string]
  for ($index = 0; $index -lt $Value.Length; $index += $LineLength) {
    $length = [Math]::Min($LineLength, $Value.Length - $index)
    $lines.Add($Value.Substring($index, $length))
  }

  return ($lines -join "`r`n")
}

if (-not (Test-Path -LiteralPath $builderScript)) {
  throw "Missing package builder: $builderScript"
}

try {
  New-Item -ItemType Directory -Path $packageWorkRoot -Force | Out-Null
  New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

  $packageArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $builderScript,
    "-OutputRoot",
    $packageWorkRoot,
    "-PackageName",
    $packageName
  )

  if ($DownloadWheels) {
    $packageArgs += "-DownloadWheels"
  }

  & powershell.exe @packageArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Could not build the embedded install package."
  }

  if (-not (Test-Path -LiteralPath (Join-Path $packageRoot "Install-LAGPlantApp.ps1"))) {
    throw "The embedded package is missing Install-LAGPlantApp.ps1."
  }

  Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $payloadZip -Force
  $base64Payload = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($payloadZip))
  $payloadText = Split-Base64Lines -Value $base64Payload

  $installerTemplate = @'
@echo off
setlocal
set "INSTALLER_SELF_PATH=%~f0"
echo Installing LAG Plant App...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $scriptPath=$env:INSTALLER_SELF_PATH; $raw=[System.IO.File]::ReadAllText($scriptPath); $marker='### LAG_PLANT_APP_POWERSHELL_PAYLOAD ###'; $idx=$raw.LastIndexOf($marker); if ($idx -lt 0) { throw 'Installer payload marker missing.' }; $ps=$raw.Substring($idx + $marker.Length); Invoke-Expression $ps"
set "INSTALL_EXIT=%ERRORLEVEL%"
if not "%INSTALL_EXIT%"=="0" (
  echo.
  echo Install failed. Error code %INSTALL_EXIT%.
  echo Check the log on your Desktop named LAG-Plant-App-install.log.
  echo.
  pause
  exit /b %INSTALL_EXIT%
)
echo.
echo Install complete. Open LAG Plant App from the Desktop or Start Menu shortcut.
echo.
pause
exit /b 0
### LAG_PLANT_APP_POWERSHELL_PAYLOAD ###
$ErrorActionPreference = "Stop"

$desktopPath = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($desktopPath)) {
  $desktopPath = [System.IO.Path]::GetTempPath()
}

$logPath = Join-Path $desktopPath "LAG-Plant-App-install.log"
$transcriptStarted = $false
$installExitCode = 0

try {
  Start-Transcript -Path $logPath -Force | Out-Null
  $transcriptStarted = $true
} catch {
  Write-Warning "Could not start install transcript: $($_.Exception.Message)"
}

Write-Host "Install log: $logPath"

$payloadBase64 = @"
__PAYLOAD_BASE64__
"@

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("LAG-Plant-App-Install-" + [System.Guid]::NewGuid().ToString("N"))
$extractRoot = Join-Path $tempRoot "app"
$zipPath = Join-Path $tempRoot "payload.zip"

try {
  New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
  [System.IO.File]::WriteAllBytes($zipPath, [Convert]::FromBase64String(($payloadBase64 -replace "\s", "")))

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $extractRoot)

  $installer = Join-Path $extractRoot "Install-LAGPlantApp.ps1"
  if (-not (Test-Path -LiteralPath $installer)) {
    throw "The embedded installer did not unpack correctly."
  }

  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
  if ($LASTEXITCODE -ne 0) {
    throw "The embedded installer failed with exit code $LASTEXITCODE."
  }
} catch {
  $installExitCode = 1
  Write-Host ""
  Write-Host "INSTALL FAILED"
  Write-Host $_.Exception.Message
  Write-Host ""
  Write-Host "Install log: $logPath"
} finally {
  if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
  }

  if ($transcriptStarted) {
    Stop-Transcript | Out-Null
  }
}

exit $installExitCode
'@

  $installerContent = $installerTemplate.Replace("__PAYLOAD_BASE64__", $payloadText)
  Set-Content -LiteralPath $outputFullPath -Value $installerContent -Encoding ASCII
  Write-Host "One-file installer: $outputFullPath"
  Write-Host "Copy only this file to the other Windows device, then double-click it or run it."
} finally {
  if (Test-Path -LiteralPath $packageWorkRoot) {
    Remove-Item -LiteralPath $packageWorkRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
