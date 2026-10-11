# Brahma / JARVIS ↔ Claude Code 2.1.88: full-runtime integration

**Development branch (JARVIS):** feature/jarvis-claude-full-runtime-20261011

**Development branch (Claude build):** feature/jarvis-claude-full-runtime-20261011

The stable JARVIS main branch, stable Claude master branch and the original
Three.js HUD are not modified by this integration branch.

## Goal and scope

JARVIS uses the user's specific reconstructed Claude Code source build as a
real execution engine, not a Claude-like prompt template. The engine retains
its native CLI logic (tools, planners, agents, hooks, permissions, skills,
sessions, and MCP) while exposing JSONL events and permission replies to
JARVIS. It is not yet verified as 100% parity with Anthropic cloud features.

## Implemented integration paths

- core/claude_runtime.py — real Node.js CLI process, structured stdin/stdout,
  session resume, streaming event callbacks, permission responses, cancellation,
  timeout, process-tree termination, and explicit OpenRouter provider setup.
- actions/claude_code_bridge.py — JARVIS tool adapter, status/probe,
  callbacks shared by live UI and background agent executor.
- main.py — routes dev_agent and natural-language coding/website requests to
  the genuine runtime; a Qt signal router displays native Claude events and
  permission requests. No HUD asset is changed.
- core/brahma_mcp_stdio.py — local Windows desktop MCP server, for screenshot,
  click, move, type, hotkey and scroll, using the installed Brahma pyautogui
  dependencies. This is a Windows implementation of the *capability class*,
  not the macOS Swift binary. It exposes no tools on non-Windows hosts.
- installer/BrahmaEvo.spec — packages Node, the reconstructed compiled CLI,
  and BrahmaMcp.exe as one Windows application distribution.
- installer/prepare_claude_runtime.ps1 — build-time preparation of the exact
  Claude GitHub branch, max-feature profile and Node executable.
- tests/test_claude_runtime.py and tests/test_brahma_mcp_stdio.py — offline
  transport/permission/protocol tests on Windows and Linux CI.

## OpenRouter configuration (free cloud)

Set OPENROUTER_API_KEY in the user's Windows environment, or store the
openrouter_api_key field only in the per-user AppData/BrahmaAI/config/api_keys.json
file. **Never commit an API key into GitHub.**

The bridge sets:

    ANTHROPIC_BASE_URL=https://openrouter.ai/api
    ANTHROPIC_AUTH_TOKEN=<OpenRouter API key>
    ANTHROPIC_API_KEY=
    ANTHROPIC_MODEL=openrouter/free
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
    DISABLE_TELEMETRY=1

The model defaults to openrouter/free; configure another OpenRouter model if
tool-use compatibility tests indicate it is required. Free models have usage
limits and cannot guarantee parity with the Claude models.

Optional AppData/BrahmaAI/config/app_settings.json entries:

    "claude_code_entrypoint": "C:/.../claude-code-source-build/dist/cli.js",
    "claude_code_model": "openrouter/free",
    "claude_code_windows_mcp": true,
    "claude_code_feature_overrides": {}

For packaged builds the CLI path is detected automatically. On development
machines the exact reconstructed dist/cli.js must be configured or placed in
the runtime directory. It is never replaced with an unrelated claude command.

Use the JARVIS Claude tool with {"action":"status"} for a no-network readiness
probe. It reports the CLI, Node, API-key and Windows MCP helper readiness
without exposing the key. No model usage is charged for the probe.

## Packaging the full Windows distribution

1. On a Windows build machine install Node >=20, Git, Bun >=1.1, npm,
   Python/PyInstaller and all Brahma requirements.
2. From the JARVIS repository run
   powershell -ExecutionPolicy Bypass -File installer/prepare_claude_runtime.ps1
3. Check runtime/claude-code/dist/claude-feature-manifest.json. Pay attention
   to reconstructedNativePackages and buildStatus.
4. Build with the explicit full-runtime packaging guard:
   $env:BRAHMA_REQUIRE_CLAUDE_BUNDLE='1'
   pyinstaller installer/BrahmaEvo.spec
5. Check the BrahmaEvo output folder has BrahmaEvo.exe, BrahmaMcp.exe,
   the Node executable and runtime/claude-code/dist/cli.js + cli.bundle/.
6. Run actual Windows GUI + MCP/Claude end-to-end tests with a user-provided
   OpenRouter key. These tests have not yet been completed.

This is a single application distribution that can include helper processes;
the PyInstaller .spec builds an onedir app, **not yet an installer wizard**.

## Security and privacy

The JARVIS Qt UI asks explicit permission for CLI can_use_tool requests, with
the name and input visible. No default --dangerously-skip-permissions.
Desktop MCP preserves pyautogui FAILSAFE and a constrained hotkey list.

The reconstructed CLI's nonessential traffic and telemetry options are set
by default. Full privacy needs a runtime network trace and outbound allowlist;
an OpenRouter model must be permitted HTTPS access to openrouter.ai.
Avoid enabling arbitrary server-side security / entitlement overrides.

## Function audit: what is and is not proven

- **Real source-build process bridge:** code integrated, hermetic tests present.
- **Bidirectional permission control:** protocol implemented; live backend
  test with an actual compiled CLI is pending.
- **Hidden compile-time gates:** the source-build branch discovers literal
  feature() usages and requests compilation of all of them. It writes a
  manifest, but a gate is not a verified capability.
- **Runtime GrowthBook local overrides:** BRAHMA_CLAUDE_FEATURE_OVERRIDES
  works for known feature keys; do not treat server-exclusive features as local.
- **Windows desktop MCP:** protocol exists and has Windows implementations
  through PyAutoGUI. True desktop integration needs interactive Windows tests.
- **Native @ant/* addons:** some source-map modules are partial/stubbed;
  the feature manifest reports their state. macOS-only Swift code cannot
  simply be switched on in Windows.
- **Server-exclusive Claude.ai remote bridge and Anthropic-only services:**
  not made locally available merely by compiling their client code.
- **Free OpenRouter models:** model API compatibility, tool use, extended
  reasoning, and multi-agent reliability must be tested with the selected model.
- **Windows full packaged EXE:** packaging path added; final compiler/build,
  native runtime and installer acceptance are pending verification.

The working definition of completed is: every feature has a passing end-to-end
test or an explicit documented external dependency / platform limitation.
