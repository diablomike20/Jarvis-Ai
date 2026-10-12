# Claude Platform documentation ↔ JARVIS source audit
Date: 2026-10-12 (Europe/Budapest)
Scope: Sources and official links relevant to JARVIS's custom reconstructed Claude Code runtime. This audit does not claim to have read every page of the larger Claude Platform documentation.

## Verified official docs
- https://platform.claude.com/docs/en/home — public landing page for the Claude API, Messages API, managed agents, SDKs, examples, and links to Claude Code; not a published Claude Code CLI source tree.
- https://platform.claude.com/docs/en/cli-sdks-libraries/overview — distinguishes API client SDKs from Claude Code/Agent SDK. API SDK clients implement HTTP calls/streaming, not the entire Claude Code engine.
- https://code.claude.com/docs/en/agent-sdk/overview — Agent SDK is a library **running the Claude Code binary**, offering permissions, tools, sessions, hooks and API access. This is not the original internal CLI source.
- https://code.claude.com/docs/en/agent-sdk/agent-loop — agent loop lifecycle documented; Python/TypeScript SDKs bundle Claude Code binary.
- https://platform.claude.com/docs/en/build-with-claude/context-editing — server-side clearing of tool and thinking blocks plus client-side compaction options.
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching — API cache control; not original internal cachedMicrocompact source code.
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool — dynamic tool discovery API; not implementation of private skillSearch/prefetch.
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context — API-level context-management approaches.

## Verified GitHub repositories (via repo trees)
- https://github.com/anthropics/claude-code — official documentation/plugins/examples/configuration, 1,599 Git blobs at inspected tree 3deb873687379f0c199a69fdaccc65f0865f7a29; does **not** contain the internal `src/query.ts` or `src/cli/print.ts` source files.
- https://github.com/anthropics/claude-agent-sdk-python — open SDK source (MIT in repo metadata) containing a CLI subprocess transport and bundled-CLI resolution: `src/claude_agent_sdk/_internal/transport/subprocess_cli.py`. Does not provide the private CLI internals.
- https://github.com/anthropics/claude-agent-sdk-typescript — SDK repository, not the missing private CLI source modules.
- https://github.com/anthropics/anthropic-sdk-typescript — open HTTP/API SDK implementation, not the Claude Code agent core.
- https://github.com/diablomike20/claude-code — user's source repo: has `src/query.ts` and `src/cli/print.ts`; audited `main` SHA 6ee4529f1f62631c70c948b6e654ba95668d0c6e.
- https://github.com/diablomike20/claude-code-source-build — user's sourcemap build repo; contains corresponding reconstructed internal sources and local build pipeline. Build branch pinned to exact commits by JARVIS packaging.

## Missing-module source conclusion (specific, not general)
At the inspected public Git trees, these implementation paths are not supplied by the official docs or official code repositories, nor by the inspected source trees of the two user repos:
1. `src/proactive/index` — PROACTIVE/KAIROS
2. `src/services/skillSearch/prefetch` — asynchronous skill prefetch
3. `src/services/compact/snipCompact` and `snipProjection` — HISTORY_SNIP
4. `src/services/contextCollapse/index`
5. `src/services/compact/reactiveCompact`
6. `src/services/compact/cachedMicrocompact`

The user repo **does** have a substantial real internal Claude Code source tree. These are specific missing module implementations, not proof of a missing overall codebase.

The official docs can help specify/test replacement behaviors in supported environments: tool discovery, permissions, model stream events, context editing, caching, compaction. They do **not** establish direct source equivalence for the six private CLI feature groups, and API-server capabilities are not identical to local module implementations.

## Integration policy
1. Continue using user's reconstructed `claude-code-source-build` as JARVIS runtime. **Do not substitute the official Agent SDK** as an engine without explicit new approval.
2. Preserve actual original code and audit it first, not arbitrary generated placeholders.
3. Classify each feature as: original implementation / verified functional reconstruction / compatibility no-op / unavailable. Never claim a no-op is fully restored.
4. Verify behavior through offline SSE, tool execution, permissions, context behavior, then Windows packaging on immutable SHAs.
5. User's protected main/master branches stay untouched; this note is on the isolated integration branch only.
