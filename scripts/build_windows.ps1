#requires -Version 5.1
<#
.SYNOPSIS
  Build SpaceCodeAgent.exe on Windows.
.DESCRIPTION
  Creates/reuses .venv, installs pinned dependencies and runs PyInstaller.
  Default output: dist\SpaceCodeAgent.exe (one-file). Use -Onedir for a
  faster-startup folder build used while debugging Qt plugins.
#>
param(
    [switch]$Onedir,
    [switch]$NoInstall,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Entry = Join-Path $Root 'scripts\entry.py'
$VersionFile = Join-Path $Root 'scripts\version_info.txt'
$Icon = Join-Path $Root 'assets\spacecode.ico'
$Dist = Join-Path $Root 'dist'
$Build = Join-Path $Root 'build'

if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $Root '.venv')
}

if (-not $NoInstall) {
    Write-Host "Installing dependencies..."
    & $Python -m pip install --upgrade pip --quiet
    & $Python -m pip install -r (Join-Path $Root 'requirements.txt') --quiet
}

if ($Clean) {
    Remove-Item -Recurse -Force $Build, $Dist -ErrorAction SilentlyContinue
}

# PyInstaller refuses to overwrite an existing one-dir output; remove only our target.
$TargetDir = Join-Path $Dist 'SpaceCodeAgent'
$TargetExe = Join-Path $Dist 'SpaceCodeAgent.exe'
if ($Onedir) {
    Remove-Item -Recurse -Force $TargetDir -ErrorAction SilentlyContinue
} else {
    Remove-Item -Force $TargetExe -ErrorAction SilentlyContinue
}

$Mode = if ($Onedir) { '--onedir' } else { '--onefile' }
$Arguments = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--windowed',
    '--name', 'SpaceCodeAgent',
    '--distpath', $Dist,
    '--workpath', $Build,
    '--specpath', $Build,
    '--paths', (Join-Path $Root 'src'),
    '--add-data', "$(Join-Path $Root 'src\space_code_agent\samples');space_code_agent/samples",
    '--version-file', $VersionFile,
    '--collect-submodules', 'openai',
    '--hidden-import', 'httpx2',
    $Mode,
    $Entry
)
if (Test-Path $Icon) {
    $Arguments = @('-m', 'PyInstaller', '--icon', $Icon) + $Arguments[3..($Arguments.Count - 1)]
}

Write-Host "Building ($Mode)..."
$ErrorActionPreference = 'Continue'
& $Python @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
$ExitCode = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

if ($ExitCode -ne 0) {
    throw "PyInstaller failed with exit code $ExitCode"
}

$Exe = if ($Onedir) {
    Join-Path $Dist 'SpaceCodeAgent\SpaceCodeAgent.exe'
} else {
    Join-Path $Dist 'SpaceCodeAgent.exe'
}
if (Test-Path $Exe) {
    Write-Host "Built: $Exe ($([math]::Round((Get-Item $Exe).Length / 1MB, 1)) MB)"
} else {
    throw "Build finished but $Exe is missing"
}
