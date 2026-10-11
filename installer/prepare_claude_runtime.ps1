# Prepare the exact reconstructed Claude Code branch for Brahma Windows packaging.
# Requires Git, Node.js >=20, Bun >=1.1 and npm on the BUILD machine only.
# The installed JARVIS does not need Git, npm, Bun, or network installation.
param(
    [string]$ClaudeRepo = 'https://github.com/diablomike20/claude-code-source-build.git',
    [string]$ClaudeBranch = 'feature/jarvis-claude-full-runtime-20261011'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root '.build-cache\claude-code-source-build'
$dest = Join-Path $root 'runtime\claude-code\dist'
$nodeDest = Join-Path $root 'runtime\node\node.exe'

foreach ($cmd in @('git', 'node', 'npm', 'bun')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Required build tool not found: $cmd"
    }
}
$nodeMajor = [int]((& node --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 20) { throw "Node >= 20 required; found $nodeMajor" }
New-Item -ItemType Directory -Path (Split-Path $source -Parent) -Force | Out-Null
if (Test-Path (Join-Path $source '.git')) {
    # Never reset a developer's changed working tree.
    $dirty = & git -C $source status --porcelain
    if ($dirty) { throw "Build checkout has local changes: $source" }
    & git -C $source fetch origin $ClaudeBranch
    if ($LASTEXITCODE -ne 0) { throw "Failed to fetch Claude source branch" }
    & git -C $source checkout $ClaudeBranch
    if ($LASTEXITCODE -ne 0) { throw "Failed to select Claude source branch" }
    & git -C $source merge --ff-only "origin/$ClaudeBranch"
    if ($LASTEXITCODE -ne 0) { throw "Claude checkout was not fast-forwardable" }
} else {
    & git clone --single-branch --branch $ClaudeBranch $ClaudeRepo $source
    if ($LASTEXITCODE -ne 0) { throw "Claude source clone failed" }
}

Push-Location $source
try {
    & node scripts/build-cli.mjs --list-features
    if ($LASTEXITCODE -ne 0) { throw "Claude compile-time feature discovery failed" }
    & node scripts/build-cli.mjs --max-features
    if ($LASTEXITCODE -ne 0) { throw "Maximum Claude Code build failed" }
    $manifest = Get-Content (Join-Path $source 'dist\claude-feature-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.buildStatus -ne 'built-not-runtime-tested') {
        throw "Unexpected Claude feature manifest state"
    }
} finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $source 'dist\cli.js'))) { throw "CLI output missing" }
if (-not (Test-Path (Join-Path $source 'dist\cli.bundle'))) { throw "CLI bundle directory missing" }

New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Copy-Item -Recurse -Force (Join-Path $source 'dist') $dest

New-Item -ItemType Directory -Path (Split-Path $nodeDest -Parent) -Force | Out-Null
$nodeSource = (Get-Command node.exe -ErrorAction Stop).Source
Copy-Item -Force $nodeSource $nodeDest

Write-Host "Reconstructed Claude Code bundled at: $dest"
Write-Host "Node bundled at: $nodeDest"
Write-Host "Compile feature manifest: $(Join-Path $dest 'claude-feature-manifest.json')"
Write-Host "NEXT: Set BRAHMA_REQUIRE_CLAUDE_BUNDLE=1 then run pyinstaller installer/BrahmaEvo.spec"
