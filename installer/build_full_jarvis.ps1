<#
Build a PRIVATE, all-in-one Windows JARVIS installer.

This performs Rust/Python builds on the maintainer's machine. The resulting
BrahmaEvo_Setup.exe already contains the PhotoCraft, LightCraft and FilmCraft
headless engines: no Git, Rust or Python is required on the target PC.

IMPORTANT: The upstream Brahma AI Evo license prohibits redistribution.
Do not publish the generated EXE to GitHub Releases or share it with others.
#>
[CmdletBinding()]
param(
    [string]$SourcesRoot = "",
    [string]$Python = "python",
    [switch]$SkipPythonDependencies,
    [switch]$SkipRustBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $SourcesRoot) {
    $SourcesRoot = Join-Path $RepoRoot ".source-build"
}
$SourcesRoot = [IO.Path]::GetFullPath($SourcesRoot)
$StageRoot = Join-Path $RepoRoot ".bundle-stage"
$EngineStage = Join-Path $StageRoot "editor_engines"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $RepoRoot ".venv\Scripts\pyinstaller.exe"

$Projects = @(
    @{ Id = "photocraft"; Sha = "b71991e15a3fc01d3c5848464c14c19b6dc8f2b5"; Package = "photocraft-cli" },
    @{ Id = "lightcraft"; Sha = "7b47ba7894a2563be32ab75176866b6d743df7a4"; Package = "lightcraft-cli" },
    @{ Id = "filmcraft"; Sha = "5231852443363f001c3f6b396dd9b1e6461ae2be"; Package = "filmcraft-cli" }
)

function Run-Checked {
    param([string]$Program, [string[]]$Arguments)
    Write-Host ("> " + $Program + " " + ($Arguments -join " ")) -ForegroundColor DarkCyan
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command exited with $LASTEXITCODE : $Program"
    }
}

if (-not $IsWindows -and -not ($env:OS -eq "Windows_NT")) {
    throw "This installer can only be built on Windows x64."
}

Set-Location $RepoRoot
Write-Host "Building private full JARVIS installer (PhotoCraft + LightCraft + FilmCraft)" -ForegroundColor Cyan
Write-Host "No public release artifacts will be published." -ForegroundColor Yellow

foreach ($required in @("git", "cargo", $Python)) {
    if (-not (Get-Command $required -ErrorAction SilentlyContinue)) {
        throw "Missing build prerequisite: $required. Install it on the BUILD computer only."
    }
}

New-Item -ItemType Directory -Path $SourcesRoot -Force | Out-Null
New-Item -ItemType Directory -Path $EngineStage -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $EngineStage "licenses") -Force | Out-Null

foreach ($project in $Projects) {
    $id = $project.Id
    $projectDir = Join-Path $SourcesRoot $id
    $gitDir = Join-Path $projectDir ".git"
    if (-not (Test-Path -LiteralPath $gitDir)) {
        if (Test-Path -LiteralPath $projectDir) {
            throw "Source folder already exists, but is not a Git clone: $projectDir"
        }
        Run-Checked "git" @("clone", "--no-checkout", "https://github.com/diablomike20/$id.git", $projectDir)
        Run-Checked "git" @("-C", $projectDir, "checkout", "--detach", $project.Sha)
    }

    $commit = (& git -C $projectDir rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $commit -ne $project.Sha) {
        throw "Unexpected $id source revision. Expected $($project.Sha), got $commit. Use a clean $SourcesRoot."
    }

    $exe = Join-Path $projectDir ("target\release\" + $project.Package + ".exe")
    if (-not $SkipRustBuild) {
        Write-Host "Building $id at verified commit $commit" -ForegroundColor Cyan
        Push-Location $projectDir
        try {
            Run-Checked "cargo" @("build", "--release", "--locked", "-p", $project.Package)
        }
        finally { Pop-Location }
    }
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "$id native editor engine did not build: $exe"
    }

    $targetDir = Join-Path $EngineStage $id
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Copy-Item -LiteralPath $exe -Destination (Join-Path $targetDir ($project.Package + ".exe")) -Force

    # Include adjacent native runtime dependencies when present. Validate the
    # actual application on Windows before depending on platform-specific libs.
    Get-ChildItem -LiteralPath (Split-Path -Parent $exe) -Filter "*.dll" -File |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $targetDir -Force }

    $licenseFolder = Join-Path (Join-Path $EngineStage "licenses") $id
    New-Item -ItemType Directory -Path $licenseFolder -Force | Out-Null
    foreach ($licenseFile in @("LICENSE-MIT", "LICENSE-APACHE", "NOTICE")) {
        $source = Join-Path $projectDir $licenseFile
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination $licenseFolder -Force
        }
    }
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Run-Checked $Python @("-m", "venv", (Join-Path $RepoRoot ".venv"))
}
if (-not $SkipPythonDependencies) {
    Run-Checked $PythonExe @("-m", "pip", "install", "--upgrade", "pip", "wheel")
    Run-Checked $PythonExe @("-m", "pip", "install", "-r", "requirements.txt", "-r", "requirements-voice.txt", "pyinstaller", "pywin32")
}
if (-not (Test-Path -LiteralPath $PyInstaller)) {
    throw "PyInstaller not found in JARVIS .venv. Install the Python build requirements."
}

$env:JARVIS_BUNDLED_ENGINE_DIR = $EngineStage
try {
    Run-Checked $PyInstaller @("installer\BrahmaEvo.spec", "--noconfirm", "--clean")
    $DistInternal = Join-Path $RepoRoot "dist\BrahmaEvo\_internal"
    foreach ($project in $Projects) {
        $expected = Join-Path $DistInternal ("editor_engines\" + $project.Id + "\" + $project.Package + ".exe")
        if (-not (Test-Path -LiteralPath $expected -PathType Leaf)) {
            throw "PyInstaller payload validation failed: missing $expected"
        }
    }
    # The existing self-contained setup wizard wraps the complete onedir app
    # into a SINGLE EXE for installation.
    Run-Checked $PyInstaller @("installer\BrahmaEvo_Setup.spec", "--noconfirm", "--clean")
}
finally {
    Remove-Item Env:\JARVIS_BUNDLED_ENGINE_DIR -ErrorAction SilentlyContinue
}

$setupExe = Join-Path $RepoRoot "dist\BrahmaEvo_Setup.exe"
if (-not (Test-Path -LiteralPath $setupExe -PathType Leaf)) {
    throw "Setup executable missing after successful build: $setupExe"
}
Write-Host ""
Write-Host "Private, all-in-one installer created: $setupExe" -ForegroundColor Green
Write-Host "All three Craft engines are included; do not distribute this build." -ForegroundColor Yellow
