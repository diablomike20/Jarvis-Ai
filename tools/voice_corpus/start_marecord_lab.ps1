#Requires -Version 5.1
<#
.SYNOPSIS
  One-command LOCAL preparation of already-provided MaRecord reference.
.DESCRIPTION
  Leaves all audio in a private Windows folder. Does not modify Jarvis-AI main,
  the Claude runtime, or upload any recordings. Requires FFmpeg and Python 3.11.
  Optionally produces UNVERIFIED draft Hungarian transcription.
.EXAMPLE
  .\start_marecord_lab.ps1 -MaRecordMp3 "$env:USERPROFILE\Downloads\marecord_produkcios_hangstudio-www_marecord_hu_-_karpati_levente_hangminta.mp3" -AutoTranscript
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MaRecordMp3,

    [string]$PrivateDir = (Join-Path $env:LOCALAPPDATA 'JarvisAI\voice_private'),

    [ValidateRange(0, 24)]
    [int]$MaxClips = 8,

    [string]$PythonExe = '',

    [switch]$AutoTranscript,

    [ValidateSet('tiny', 'base', 'small', 'medium', 'large-v3-turbo')]
    [string]$WhisperModel = 'small',

    [ValidateSet('cpu', 'cuda')]
    [string]$WhisperDevice = 'cpu'
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Bootstrap = Join-Path $PSScriptRoot 'bootstrap_marecord.py'
$Transcriber = Join-Path $PSScriptRoot 'local_transcribe_hu.py'

if (-not (Test-Path -LiteralPath $MaRecordMp3 -PathType Leaf)) {
    throw "Cannot find the provided MaRecord MP3: $MaRecordMp3"
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg not on PATH. Install FFmpeg and reopen PowerShell.'
}
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw 'FFprobe not on PATH.'
}

$Source = (Resolve-Path -LiteralPath $MaRecordMp3).Path
$LabPath = [System.IO.Path]::GetFullPath($PrivateDir)
if ($LabPath.TrimEnd('\') -eq $Repo.TrimEnd('\') -or
    $LabPath.StartsWith($Repo.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Private audio output must be OUTSIDE the Git repository.'
}

if ($PythonExe) {
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw "Python interpreter not found: $PythonExe"
    }
    $Python = (Resolve-Path -LiteralPath $PythonExe).Path
    $PyPrefix = @()
} else {
$pyCmd = Get-Command py -ErrorAction SilentlyContinue
if ($pyCmd) {
    $Python = $pyCmd.Source
    $PyPrefix = @('-3.11')
} else {
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pyCmd) {
        throw 'Python 3.11 is missing. Install Python 3.11 and add it to PATH.'
    }
    $Python = $pyCmd.Source
    $PyPrefix = @()
}
}

& $Python @PyPrefix --version
if ($LASTEXITCODE -ne 0) { throw 'Python runtime is not working.' }
New-Item -ItemType Directory -Force -Path $LabPath | Out-Null

Write-Host 'Preparing MaRecord references locally...' -ForegroundColor Cyan
& $Python @PyPrefix $Bootstrap --input $Source --output-dir $LabPath --max-clips $MaxClips
if ($LASTEXITCODE -ne 0) { throw 'MaRecord audio preparation failed.' }

$hash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLower()
$session = Join-Path $LabPath ('marecord_' + $hash.Substring(0,12))
$masterWav = Join-Path $session 'full_reference_24k_mono.wav'
$review = Join-Path $session 'review_candidates.csv'

if (-not (Test-Path -LiteralPath $masterWav -PathType Leaf)) {
    throw "No reference WAV created: $masterWav"
}

if ($AutoTranscript) {
    $draft = Join-Path $LabPath ('marecord_whisper_draft_' + $hash.Substring(0,12))
    Write-Host 'Running local Whisper draft transcription...' -ForegroundColor Cyan
    & $Python @PyPrefix $Transcriber --input $masterWav --output-dir $draft --model $WhisperModel --device $WhisperDevice
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Draft transcription did not complete. Verify faster-whisper installation; original WAV clips remain saved.'
    }
}

Write-Host ''
Write-Host 'LOCAL AUDIO OUTPUT CREATED' -ForegroundColor Green
Write-Host "  Unprocessed copy: $masterWav"
Write-Host "  Candidate review: $review"
Write-Host "  Private folder: $session"
Write-Host '  Important: candidates are NOT yet actor-verified, transcribed, or TTS-ready.'
