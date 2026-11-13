# Install Homeport on Windows (no admin rights needed):
#   irm https://raw.githubusercontent.com/ferdousmikdad/Homeport/main/install.ps1 | iex
#
# Installs the app into %LOCALAPPDATA%\Programs\Homeport with a Start menu
# shortcut, then starts it. Files fetched this way aren't marked as downloaded
# from the internet, so SmartScreen doesn't block them.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # much faster downloads

$repo = 'ferdousmikdad/Homeport'
$base = "https://github.com/$repo/releases/latest/download"
$dest = Join-Path $env:LOCALAPPDATA 'Programs\Homeport'
$tmp  = Join-Path $env:TEMP ("homeport-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null

function New-Shortcut($path, $target, $workdir) {
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut($path)
    $s.TargetPath = $target
    $s.WorkingDirectory = $workdir
    $s.Save()
}

try {
    try {
        Invoke-WebRequest "$base/Homeport-windows-x64.zip" -OutFile "$tmp\homeport.zip" -UseBasicParsing
        $native = $true
    } catch {
        $native = $false
    }

    if ($native) {
        Get-Process -Name Homeport -ErrorAction SilentlyContinue | Stop-Process -Force
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        Unblock-File "$tmp\homeport.zip"
        Expand-Archive "$tmp\homeport.zip" -DestinationPath $dest -Force
        Get-ChildItem $dest -Recurse | Unblock-File
        $exe = Join-Path $dest 'Homeport.exe'
        New-Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) 'Homeport.lnk') $exe $dest
        Write-Host "Homeport installed - find it in the Start menu. Opening it now." -ForegroundColor Green
        Start-Process $exe
    } else {
        # No app download: run from source (run.bat sets everything up by itself).
        # Use the latest release's source so it matches the apps, not unreleased
        # work on main; $env:HOMEPORT_REF picks another tag or branch.
        $ref = $env:HOMEPORT_REF
        if (-not $ref) {
            try { $ref = (Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest" -UseBasicParsing).tag_name } catch { $ref = $null }
            if (-not $ref) { $ref = 'main' }
        }
        $src = Join-Path $env:LOCALAPPDATA 'Homeport\app'
        Write-Host "Installing Homeport ($ref) from source into $src ..."
        Invoke-WebRequest "https://github.com/$repo/archive/$ref.zip" -OutFile "$tmp\src.zip" -UseBasicParsing
        $unpacked = Join-Path $tmp 'src'
        Expand-Archive "$tmp\src.zip" -DestinationPath $unpacked -Force
        if (Test-Path $src) { Remove-Item $src -Recurse -Force }
        New-Item -ItemType Directory -Path (Split-Path $src) -Force | Out-Null
        # GitHub names the folder after the version (e.g. Homeport-1.0.1), so take the only one
        Move-Item (Get-ChildItem $unpacked -Directory | Select-Object -First 1).FullName $src
        Get-ChildItem $src -Recurse | Unblock-File
        New-Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) 'Homeport.lnk') (Join-Path $src 'run.bat') $src
        Write-Host "Homeport installed - find it in the Start menu. Starting it now." -ForegroundColor Green
        Start-Process (Join-Path $src 'run.bat') -WorkingDirectory $src
    }
} finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
