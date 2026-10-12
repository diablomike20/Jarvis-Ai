# Prepare the exact reconstructed Claude Code branch for Brahma Windows packaging.
# Requires Git, Node.js >=20, Bun >=1.1 and npm on the BUILD machine only.
# The installed JARVIS does not need Git, npm, Bun, or network installation.
param(
    [string]$ClaudeRepo = 'https://github.com/diablomike20/claude-code-source-build.git',
    [string]$ClaudeBranch = 'feature/jarvis-nextgen-working-runtime-20261011',
    [string]$ClaudeCommit = '1860c0eda0415d7a34aafcbeb48aac8995bbdc61',
    [string]$DonorRepo = 'https://github.com/diablomike20/claude-code.git',
    [string]$DonorCommit = '6ee4529f1f62631c70c948b6e654ba95668d0c6e'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root '.build-cache\claude-code-source-build'
$donor = Join-Path $root '.build-cache\claude-code-donor'
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

# Pin the exact tested commit from the isolated master-derived integration branch.
& git -C $source checkout --detach $ClaudeCommit
if ($LASTEXITCODE -ne 0) { throw "Cannot checkout expected Claude commit $ClaudeCommit" }
$actualCommit = (& git -C $source rev-parse HEAD).Trim()
if ($actualCommit -ne $ClaudeCommit) { throw "Wrong source commit: $actualCommit" }

# The user's claude-code repository is an original source donor.
# Check out its immutable SHA; never replace actual source with guessed stubs.
if (Test-Path (Join-Path $donor '.git')) {
    $donorDirty = & git -C $donor status --porcelain
    if ($donorDirty) { throw "Original Claude donor contains local changes: $donor" }
    & git -C $donor fetch origin main
    if ($LASTEXITCODE -ne 0) { throw "Original source donor fetch failed" }
} else {
    & git clone --single-branch --branch main $DonorRepo $donor
    if ($LASTEXITCODE -ne 0) { throw "Original source donor clone failed" }
}
& git -C $donor checkout --detach $DonorCommit
if ($LASTEXITCODE -ne 0) { throw "Cannot checkout original source commit $DonorCommit" }
$actualDonorCommit = (& git -C $donor rev-parse HEAD).Trim()
if ($actualDonorCommit -ne $DonorCommit) { throw "Original source donor commit mismatch" }
$originalDonorSrcEnv = $env:JARVIS_CLAUDE_DONOR_SRC
$env:JARVIS_CLAUDE_DONOR_SRC = Join-Path $donor 'src'

Push-Location $source
try {
    & node --check scripts/build-cli.mjs
    if ($LASTEXITCODE -ne 0) { throw "Claude builder syntax invalid" }
    & node --test scripts/tests/build-safety.test.mjs scripts/tests/donor-source.test.mjs scripts/tests/proactive-runtime.test.mjs scripts/tests/skill-discovery.test.mjs
    if ($LASTEXITCODE -ne 0) { throw "Claude source recovery and security tests failed" }
    & node scripts/build-cli.mjs --list-features
    if ($LASTEXITCODE -ne 0) { throw "Claude compile-time feature discovery failed" }
    # CI-only diagnostics; normal installer packaging remains minified.
    if ($env:JARVIS_CLAUDE_UNMINIFIED -eq '1') {
        & node scripts/build-cli.mjs --max-features --no-minify
    } else {
        & node scripts/build-cli.mjs --max-features
    }
    if ($LASTEXITCODE -ne 0) { throw "Maximum Claude Code build failed" }
    $manifest = Get-Content (Join-Path $source 'dist\claude-feature-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.buildStatus -ne 'built-not-runtime-tested') {
        throw "Unexpected Claude feature manifest state"
    }
    if ($manifest.originalSourceRecovery.status -ne 'pinned-donor-applied' -or
        $manifest.originalSourceRecovery.commit -ne $actualDonorCommit) {
        throw "Source donor verification failed: original Claude files were not reviewed"
    }
    $donorImported = @($manifest.originalSourceRecovery.imported).Count
    $donorPreserved = @($manifest.originalSourceRecovery.preserved).Count
    $donorReviewed = @($manifest.originalSourceRecovery.reviewedAllowlist).Count
    if ($donorImported + $donorPreserved -ne $donorReviewed -or $donorReviewed -ne 10) {
        throw "Original donor source review incomplete: imported $donorImported, preserved $donorPreserved, expected 10"
    }
    Write-Host "Original donor source audit: imported=$donorImported, preserved=$donorPreserved, reviewed=$donorReviewed"
    $partialFeatures = @($manifest.optionalModuleAudit.PSObject.Properties |
        Where-Object { $_.Value.status -ne 'source-present-runtime-not-proven' } |
        ForEach-Object { $_.Name })
    if ($partialFeatures.Count -gt 0) {
        Write-Warning ("CLAUDE PARTIAL FEATURES (not fully implemented): " + ($partialFeatures -join ', '))
    }
} finally {
    Pop-Location
    if ([string]::IsNullOrEmpty($originalDonorSrcEnv)) {
        Remove-Item Env:JARVIS_CLAUDE_DONOR_SRC -ErrorAction SilentlyContinue
    } else {
        $env:JARVIS_CLAUDE_DONOR_SRC = $originalDonorSrcEnv
    }
}

if (-not (Test-Path (Join-Path $source 'dist\cli.js'))) { throw "CLI output missing" }
if (-not (Test-Path (Join-Path $source 'dist\cli.bundle'))) { throw "CLI bundle directory missing" }

New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Copy-Item -Recurse -Force (Join-Path $source 'dist') $dest

New-Item -ItemType Directory -Path (Split-Path $nodeDest -Parent) -Force | Out-Null
$nodeSource = (Get-Command node.exe -ErrorAction Stop).Source
Copy-Item -Force $nodeSource $nodeDest

@{
    sourceRepository = $ClaudeRepo
    sourceBranch = $ClaudeBranch
    sourceCommit = $actualCommit
    originalSourceRepository = $DonorRepo
    originalSourceCommit = $actualDonorCommit
    nodeVersion = ((& node --version).Trim())
    featureManifest = 'claude-feature-manifest.json'
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $dest 'brahma-source-provenance.json')

Write-Host "Reconstructed Claude Code bundled at: $dest"
Write-Host "Node bundled at: $nodeDest"
Write-Host "Compile feature manifest: $(Join-Path $dest 'claude-feature-manifest.json')"
Write-Host "Original Claude donor SHA verified: $actualDonorCommit"
Write-Host "NEXT: Set BRAHMA_REQUIRE_CLAUDE_BUNDLE=1 then run pyinstaller installer/BrahmaEvo.spec"
