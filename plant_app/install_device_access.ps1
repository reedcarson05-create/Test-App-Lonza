param(
  [int]$Port = 8000,
  [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$startupFolder = [Environment]::GetFolderPath("Startup")
$startupLauncher = Join-Path $startupFolder "Plant App Startup.cmd"
$hiddenLauncher = Join-Path $projectRoot "start_plant_app_hidden.vbs"

if (-not (Test-Path -LiteralPath $hiddenLauncher)) {
  throw "Missing launcher file: $hiddenLauncher"
}

$startupLines = @(
  "@echo off",
  'set "PLANT_APP_HOST=0.0.0.0"',
  "set `"PLANT_APP_PORT=$Port`""
)

$startupLines += "wscript.exe `"$hiddenLauncher`""
$startupContent = $startupLines -join "`r`n"

Set-Content -LiteralPath $startupLauncher -Value $startupContent -Encoding ASCII
Write-Host "Startup launcher created: $startupLauncher"

if (-not $SkipFirewall) {
  $ruleName = "Plant App LAN Access ($Port)"
  $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

  if ($existingRule) {
    Write-Host "Firewall rule already exists: $ruleName"
  } else {
    try {
      New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Profile Private `
        -Protocol TCP `
        -LocalPort $Port `
        -ErrorAction Stop | Out-Null
      Write-Host "Firewall rule created for TCP port $Port on private networks."
    } catch {
      Write-Warning "Could not create the firewall rule automatically. Run this script from an elevated PowerShell window if LAN access is blocked."
    }
  }
}

Write-Host "Device access setup complete."
