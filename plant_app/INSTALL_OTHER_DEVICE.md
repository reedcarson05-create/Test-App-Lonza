# Install On Another Windows Device

The easiest option is the one-file installer.

## Build The One-File Installer

From this `plant_app` folder, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_one_file_installer.ps1
```

That creates:

```text
dist\Install-LAG-Plant-App.cmd
```

Copy only that one file to the other Windows device, then double-click it or run it.

If the install fails, check `LAG-Plant-App-install.log` on that device's Desktop.

## Optional Folder/Zip Package

If you prefer a normal folder or zip package, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_install_package.ps1 -Zip
```

That creates:

- `dist\LAG-Plant-App-Installer`
- `dist\LAG-Plant-App-Installer.zip`

Use either the folder or the zip on the other Windows device.

## Install From The Folder Package

1. Put `LAG-Plant-App-Installer` on the other Windows device.
2. Open PowerShell in that folder.
3. Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-LAGPlantApp.ps1
```

The installer copies the app to:

```text
%LOCALAPPDATA%\LAG Plant App
```

It also creates a local Python environment, installs `requirements.txt`, checks the imports, and creates the `LAG Plant App` Desktop and Start Menu shortcuts.

## Useful Install Options

Install without opening automatically at Windows sign-in:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-LAGPlantApp.ps1 -NoStartupShortcut
```

Install and also enable LAN access on port `8000`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-LAGPlantApp.ps1 -EnableLanAccess
```

Install to a custom folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-LAGPlantApp.ps1 -InstallPath "C:\Plant App"
```

## Data Notes

The package includes `plant.db`, so a first-time install gets the current local database. If the app is already installed on a device, the installer keeps that device's existing `plant.db` unless you pass `-OverwriteDatabase`.

For multiple devices sharing the same live data, configure the SQL Server environment variables used by `db.py` instead of relying on each device's local `plant.db`.

## Offline Dependencies

The normal installer downloads Python packages from the internet. To build a one-file installer with a bundled `wheelhouse` for offline Python package installs, run this on a Windows device with internet:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_one_file_installer.ps1 -DownloadWheels
```

For the folder/zip package, use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_install_package.ps1 -Zip -DownloadWheels
```
