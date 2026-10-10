#Requires -Version 5.1
<#
.SYNOPSIS
  JARVIS Hungarian XTTS setup in the EXISTING application virtual environment.
.DESCRIPTION
  No admin rights, hidden license acceptance, user voice uploads or auto-run.
  Explicit switches control package installation, model download and playback.
.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hungarian_voice.ps1
.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hungarian_voice.ps1 -Install -InstallFFmpeg -PrepareModel
.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hungarian_voice.ps1 -Speak
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$InstallFFmpeg,
    [switch]$PrepareModel,
    [switch]$Speak
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Legacy Windows PowerShell sometimes encodes child Python output as cp1252,
# which cannot represent Hungarian long vowels (e.g. ő, ű).
$env:PYTHONIOENCODING = "utf-8"
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
} catch {
    # Non-interactive hosts may not expose a console; Python override suffices.
}
$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Invoke-PythonChecked {
    param([Parameter(Mandatory=$true)][string[]]$CommandArgs)
    & $script:Python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw ("JARVIS voice step failed (exit code " + $LASTEXITCODE + ").")
    }
}

function Test-PythonModules {
    param([Parameter(Mandatory=$true)][string[]]$ModuleNames)
    $checks = @()
    foreach ($module in $ModuleNames) {
        & $script:Python -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('$module') else 1)" | Out-Null
        $checks += ($LASTEXITCODE -eq 0)
    }
    return (-not ($checks -contains $false))
}

if ($env:OS -ne "Windows_NT") {
    throw "The voice setup script supports Windows only."
}

$choices = @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path $Root "venv\Scripts\python.exe")
)
$Python = $null
foreach ($candidate in $choices) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $Python = $candidate
        break
    }
}
if (-not $Python) {
    throw "JARVIS app virtualenv not found. First set up the main app with bootstrap.ps1. No environment was silently created."
}

& $Python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 3)"
if ($LASTEXITCODE -ne 0) {
    throw "Use the JARVIS app Python 3.10 - 3.12 environment, ideally Python 3.11."
}

Write-Host "JARVIS AI | Magyar XTTS - Windows setup" -ForegroundColor Cyan
Write-Host "Existing JARVIS Python virtual environment will be used. No reference audio upload."
Write-Host "CPU PyTorch is the safe default; an existing GPU build will be preserved."
Push-Location $Root
try {
    if ($InstallFFmpeg) {
        if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
                throw "FFmpeg missing and winget unavailable. Install FFmpeg from https://www.gyan.dev/ffmpeg/builds/."
            }
            Write-Host "Installing FFmpeg via the Windows Package Manager..." -ForegroundColor Yellow
            & winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -ne 0) {
                throw "FFmpeg winget install failed."
            }
            Write-Host "If FFmpeg isn't on PATH now, reopen PowerShell before importing MP3."
        } else {
            Write-Host "FFmpeg is already available." -ForegroundColor Green
        }
    }

    if ($Install) {
        Write-Host "Installing optional public Python packages into JARVIS virtualenv..." -ForegroundColor Yellow
        Invoke-PythonChecked -CommandArgs @("-m", "pip", "install", "--upgrade", "pip")
        if (-not (Test-PythonModules -ModuleNames @("torch", "torchaudio"))) {
            Write-Host "Installing official CPU PyTorch, TorchAudio and TorchCodec..." -ForegroundColor Yellow
            Invoke-PythonChecked -CommandArgs @(
                "-m", "pip", "install", "--index-url", "https://download.pytorch.org/whl/cpu",
                "torch", "torchaudio", "torchcodec"
            )
        } else {
            Write-Host "Existing PyTorch/TorchAudio preserved, possibly with CUDA." -ForegroundColor Green
        }
        if (-not (Test-PythonModules -ModuleNames @("TTS"))) {
            Write-Host "Installing Coqui TTS from PyPI..." -ForegroundColor Yellow
            Invoke-PythonChecked -CommandArgs @("-m", "pip", "install", "coqui-tts")
        } else {
            Write-Host "Existing Coqui TTS installation preserved." -ForegroundColor Green
        }
    }

    Write-Host "Checking local runtime imports and private reference header..." -ForegroundColor Cyan
    Invoke-PythonChecked -CommandArgs @("scripts/voice_doctor.py", "--probe-runtime")

    if ($PrepareModel) {
        Write-Host "The public model may download and require INTERACTIVE license acceptance." -ForegroundColor Yellow
        Write-Host "No private voice reference is read at this stage."
        Invoke-PythonChecked -CommandArgs @("scripts/prepare_xtts_model.py", "--download")
    }
    if ($Speak) {
        Write-Host "Starting the explicitly requested private, local voice test..." -ForegroundColor Cyan
        Invoke-PythonChecked -CommandArgs @("scripts/voice_test_local.py", "--speak")
    }
    Write-Host "Open JARVIS Settings > Audio to import/approve your licensed WAV and enable XTTS." -ForegroundColor Green
}
finally {
    Pop-Location
}
