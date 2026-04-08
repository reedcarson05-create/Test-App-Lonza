param(
  [switch]$SetStartup = $true,
  [switch]$TryPinTaskbar = $true
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherVbs = Join-Path $projectRoot "launch_plant_desktop_app.vbs"
$logoPng = Join-Path $projectRoot "static\logo.png"
$appIcon = Join-Path $projectRoot "static\logo.ico"

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

function New-AppIconFromLogo {
  param(
    [string]$SourcePng,
    [string]$IconPath
  )

  if (-not (Test-Path -LiteralPath $SourcePng)) {
    return $null
  }

  Add-Type -AssemblyName System.Drawing

  $source = [System.Drawing.Image]::FromFile($SourcePng)
  try {
    $iconSize = 256
    $canvas = New-Object System.Drawing.Bitmap $iconSize, $iconSize
    try {
      $graphics = [System.Drawing.Graphics]::FromImage($canvas)
      try {
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality

        $scale = [Math]::Min($iconSize / $source.Width, $iconSize / $source.Height)
        $drawWidth = [int][Math]::Round($source.Width * $scale)
        $drawHeight = [int][Math]::Round($source.Height * $scale)
        $offsetX = [int][Math]::Floor(($iconSize - $drawWidth) / 2)
        $offsetY = [int][Math]::Floor(($iconSize - $drawHeight) / 2)

        $graphics.DrawImage($source, $offsetX, $offsetY, $drawWidth, $drawHeight)
      } finally {
        $graphics.Dispose()
      }

      $pngStream = New-Object System.IO.MemoryStream
      try {
        $canvas.Save($pngStream, [System.Drawing.Imaging.ImageFormat]::Png)
        $pngBytes = $pngStream.ToArray()
      } finally {
        $pngStream.Dispose()
      }
    } finally {
      $canvas.Dispose()
    }

    $fileStream = [System.IO.File]::Open($IconPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    try {
      $writer = New-Object System.IO.BinaryWriter($fileStream)
      try {
        # ICO header + one PNG-backed 256x256 image entry.
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]1)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]32)
        $writer.Write([UInt32]$pngBytes.Length)
        $writer.Write([UInt32]22)
        $writer.Write($pngBytes)
      } finally {
        $writer.Dispose()
      }
    } finally {
      $fileStream.Dispose()
    }
  } finally {
    $source.Dispose()
  }

  return $IconPath
}

$shortcutIconLocation = "$env:SystemRoot\System32\SHELL32.dll,220"
try {
  $generatedIcon = New-AppIconFromLogo -SourcePng $logoPng -IconPath $appIcon
  if ($generatedIcon -and (Test-Path -LiteralPath $generatedIcon)) {
    $shortcutIconLocation = "$generatedIcon,0"
  }
} catch {
  Write-Warning "Could not build the app icon from $logoPng. Using the default Windows icon instead. $($_.Exception.Message)"
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
  $shortcut.IconLocation = $shortcutIconLocation
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
