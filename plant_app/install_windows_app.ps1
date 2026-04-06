param(
  [switch]$SetStartup = $true,
  [switch]$TryPinTaskbar = $true
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherVbs = Join-Path $projectRoot "launch_plant_desktop_app.vbs"

if (-not (Test-Path -LiteralPath $launcherVbs)) {
  throw "Missing launcher file: $launcherVbs"
}

$shortcutName = "Lonza Plant App.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) $shortcutName
$programsFolder = Join-Path ([Environment]::GetFolderPath("Programs")) "Lonza Plant App"
$startMenuShortcut = Join-Path $programsFolder $shortcutName
$startupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) $shortcutName
$legacyStartupLauncher = Join-Path ([Environment]::GetFolderPath("Startup")) "Plant App Startup.cmd"
$taskbarPinnedFolder = Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
$taskbarPinnedShortcut = Join-Path $taskbarPinnedFolder $shortcutName

if (-not (Test-Path -LiteralPath $programsFolder)) {
  New-Item -ItemType Directory -Path $programsFolder | Out-Null
}

function New-AppShortcut {
  param(
    [string]$ShortcutPath
  )

  $wshShell = New-Object -ComObject WScript.Shell
  $shortcut = $wshShell.CreateShortcut($ShortcutPath)
  $shortcut.TargetPath = "$env:SystemRoot\System32\wscript.exe"
  $shortcut.Arguments = "`"$launcherVbs`""
  $shortcut.WorkingDirectory = $projectRoot
  $shortcut.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,220"
  $shortcut.Description = "Open the Lonza Plant App desktop window."
  $shortcut.Save()
}

function Try-PinShortcutToTaskbar {
  param(
    [string]$ShortcutPath
  )

  try {
    $shellApp = New-Object -ComObject Shell.Application
    $folder = $shellApp.Namespace((Split-Path $ShortcutPath))
    $item = $folder.ParseName((Split-Path $ShortcutPath -Leaf))
    if (-not $item) {
      return $false
    }

    foreach ($verb in $item.Verbs()) {
      $verbName = (($verb.Name -replace "&", "") -replace "\s+", " ").Trim()
      if ($verbName -match "Pin to taskbar") {
        $verb.DoIt()
        Start-Sleep -Milliseconds 1000
        return $true
      }
    }
  } catch {
    return $false
  }

  return $false
}

New-AppShortcut -ShortcutPath $desktopShortcut
New-AppShortcut -ShortcutPath $startMenuShortcut
Write-Host "Desktop shortcut created: $desktopShortcut"
Write-Host "Start Menu shortcut created: $startMenuShortcut"

if ($SetStartup) {
  New-AppShortcut -ShortcutPath $startupShortcut
  if (Test-Path -LiteralPath $legacyStartupLauncher) {
    Remove-Item -LiteralPath $legacyStartupLauncher -Force
  }
  Write-Host "Startup shortcut created: $startupShortcut"
}

if ($TryPinTaskbar) {
  $pinned = Try-PinShortcutToTaskbar -ShortcutPath $startMenuShortcut
  if ($pinned) {
    Write-Host "Taskbar pin requested for the desktop app shortcut."
  } elseif (Test-Path -LiteralPath $taskbarPinnedFolder) {
    Copy-Item -LiteralPath $startMenuShortcut -Destination $taskbarPinnedShortcut -Force
    Write-Warning "Windows did not expose the pin verb. A taskbar shortcut file was placed in the pinned-items folder; sign out and back in if it does not appear right away."
  } else {
    Write-Warning "Windows did not expose the pin verb, so taskbar pinning could not be completed automatically."
  }
}

Write-Host "Desktop app installation complete."
