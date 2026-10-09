# Personal-use, all-in-one JARVIS installer.
# Build dependencies (Rust/Python/Git) are only needed on the machine BUILDING it.
# End users need only the resulting dist\BrahmaEvo_Setup.exe.
# The upstream license forbids redistribution; keep the setup private.
$ErrorActionPreference = "Stop"
& "$PSScriptRoot\installer\build_full_jarvis.ps1" @args
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
