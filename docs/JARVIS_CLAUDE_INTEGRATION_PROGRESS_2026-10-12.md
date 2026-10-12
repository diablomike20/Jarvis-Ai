# JARVIS AI — Claude Code integration: engineering handoff (2026-10-12)

This document is the current code-and-test handoff for the **development branch** `feature/jarvis-nextgen-working-runtime-20261011`. Do not mistake CI fixture success for full production feature parity.

## Source of truth

- JARVIS runtime packaging: `installer/prepare_claude_runtime.ps1`
- Reconstructed Claude runtime: `diablomike20/claude-code-source-build` pinned source commit `664c70527367df1ad1e168196e432a070f11fe4d`
- Donor original source: `diablomike20/claude-code` pinned `main` SHA `6ee4529f1f62631c70c948b6e654ba95668d0c6e`
- Ten explicit donor files are either imported or preserved in the assembled source workspace; checked via donor SHA and build manifest.
- Original JARVIS 2D Orb HUD/voice GUI is **not modified** by this source-restoration effort.
- Stable JARVIS `main` and reconstructed Claude `master` remain untouched.

## Actual new functional reconstructions

1. **Skill Discovery Prefetch** — `scripts/runtime/skillDiscoveryCore.mjs` and `scripts/runtime/skillPrefetch.mjs` in the reconstructed Claude repo. Finds/ranks already installed command/skill metadata without paid AI, executes no skill during discovery, adds real skill-discovery attachments to user input and to async post-write iterations, deduplicates. **NOT original proprietary AKI retrieval**. Test scripts cover ranking + actual prefetch call implementation.
2. **Reactive Compact (prompt overflow)** — `scripts/runtime/reactiveCompact.mjs`. On actual model prompt-too-long error, calls the existing Claude `compactConversation`, respects user auto-compact preference, abortion and one-attempt retry safety. Does **not** implement media-specific recovery or original private collapse system.
3. **Optional KAIROS transcript call guard** — the private post-compact transcript writer is missing in both inspected original-source trees; generated workspace `compact.ts` uses an optional method call so its absence does not undo an otherwise successful original compaction. **This is not transcript reconstruction**.

## Most recent proven CI

- [Windows actual reconstructed CLI SSE #38198605574](https://github.com/diablomike20/Jarvis-Ai/actions/runs/38198605574): **success**; **28 tests pass, 0 failures**; normal live local SSE PASS; forced prompt-overflow → real original Claude summary → successful retry **PASS** across exactly **3** fixture requests. The fixture returns synthetic model text.
- [JARVIS runtime smoke tests #38198605585](https://github.com/diablomike20/Jarvis-Ai/actions/runs/38198605585): **success**.
- [Voice integration regression #38198605573](https://github.com/diablomike20/Jarvis-Ai/actions/runs/38198605573): **success**, synthetic contracts only.
- [Windows installer preview #38196256080](https://github.com/diablomike20/Jarvis-Ai/actions/runs/38196256080): prior commit compiled Windows preview and setup artifacts. Does **not** include the latest two reconstructed functions.
- [Current latest-code Windows EXE preview #38198605582](https://github.com/diablomike20/Jarvis-Ai/actions/runs/38198605582): packaging underway at last check; do not mark complete until it succeeds and artifacts are inspected.

## Incomplete Claude private feature groups

| Group | Present behavior | Missing requirement |
|---|---|---|
| PROACTIVE/KAIROS | Basic local state functions + guarded absent transcript writer | Autonomous proactive agent runtime, real transcript segments |
| HISTORY_SNIP | Lossless compatibility pass-through | Verified semantic history snip/projection |
| CONTEXT_COLLAPSE | Lossless compatibility pass-through | Original collapse log/project/drain/recovery |
| CACHED_MICROCOMPACT | Disabled safe fallback | Verified server cache edit operations |

The above gaps are explicit in `dist/claude-feature-manifest.json` and CI warnings. Compile-time gates alone do not prove runtime capabilities.

## Next verification gates

- Verify latest-code Windows EXE/Setup artifact and installed executable startup. Packaging ≠ tested full installer UX.
- Exercise Skill Discovery on an actual loaded filesystem skill and inspect visible `skill_discovery` attachments; presently adapter-mocked unit tests and full CLI normal SSE are separate proofs.
- Exercise real compatible AI provider and model, multi-turn tool calls, JARVIS native MCP permission dialog and Hungarian speech pipeline.
- For each remaining four groups, locate original source first; implement/verify safe real behavior, not falsified capability.
- Do not migrate to paid Agent SDK or replace original UI without express user approval.
