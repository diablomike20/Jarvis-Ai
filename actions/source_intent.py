"""Natural Hungarian routing to *installed* source-repository plugins."""
from __future__ import annotations

import json
import re

from actions.source_plugins import installed, source_plugins

_LIST = ("funkció", "milyen eszköz", "parancs", "mit tud", "képesség", "művelet")
_STATUS = ("állapot", "státusz", "telepítve", "elérhető", "fut-e", "működik")


def match_source_plugin(text: str) -> str | None:
    """Conservatively match explicit source plugin names, not arbitrary prose."""
    lower = (text or "").casefold()
    if any(phrase in lower for phrase in (
        "source pluginok", "source pluginek", "source-pluginok",
        "forráspluginok", "forrás pluginek", "source integrációk",
    )):
        return "all"
    names = []
    for plugin_id, plugin in installed().items():
        if not plugin["enabled"]:
            continue
        aliases = [plugin_id.replace("-", " "), plugin["name"].casefold()]
        # Avoid single short generic words triggering accidental commands.
        if any(len(alias) >= 5 and alias in lower for alias in aliases):
            names.append(plugin_id)
    return names[0] if len(names) == 1 else None


def execute_source_text(text: str) -> str:
    """Plan source operations exclusively from advertised tool names."""
    plugin_id = match_source_plugin(text)
    if plugin_id is None:
        return "Nem találtam egyértelműen megnevezett source plugint."
    if plugin_id == "all":
        return source_plugins({"action": "list"})

    lower = text.casefold()
    if any(term in lower for term in _STATUS):
        return source_plugins({"action": "status", "plugin": plugin_id})
    if any(term in lower for term in _LIST):
        return source_plugins({"action": "discover", "plugin": plugin_id})

    from actions.source_plugins import _session, installed
    manifest = installed()[plugin_id]
    if manifest["adapter"] == "creative_studio":
        from actions.creative_intent import handle_creative_text
        return handle_creative_text(text)

    session = _session(manifest)
    tools = session.list_tools()
    if not tools:
        return "A modul nem hirdetett MCP-eszközöket."
    # Prefer concise names and bounded descriptions, never feed huge schemas
    # or binary tool responses into the LLM.
    choices = [
        {"name": k, "description": str(v.get("description", ""))[:250],
         "schema": v.get("inputSchema", {})}
        for k, v in list(tools.items())[:80]
    ]
    from llm_client import client as llm
    proposal = llm.chat_json(
        json.dumps({"user_request": text, "supported_tools": choices},
                   ensure_ascii=False, default=str)[:28000],
        system=(
            "Plan a call to an installed local MCP plugin. Return only JSON. "
            "If a path/id/selection is missing, return {\"question\":\"...\"}. "
            "If ready, return {\"tool\":\"exact tool name\",\"arguments\":{...}} "
            "or {\"steps\":[{\"tool\":\"exact name\",\"arguments\":{...}},...]}. "
            "Use only advertised names and declared schemas. Never fabricate "
            "files, ids or paths. Do not execute unrequested operations. "
            "Clarifying questions must be in Hungarian."
        ),
    )
    if not isinstance(proposal, dict):
        return "A source-pluginhez nem sikerült érvényes tervet készíteni."
    if proposal.get("question"):
        return str(proposal["question"])[:450]
    steps = proposal.get("steps")
    if isinstance(steps, list):
        if not 1 <= len(steps) <= 8:
            return "Egyszerre 1-8 művelet tervezhető."
        if any(not isinstance(step, dict) or
               step.get("tool") not in tools for step in steps):
            return "Az AI olyan MCP-műveletet választott, amelyet a plugin nem támogat."
        return source_plugins({
            "action": "batch", "plugin": plugin_id, "steps": steps,
        })
    tool = proposal.get("tool")
    if not isinstance(tool, str) or tool not in tools:
        return "A kiválasztott MCP-parancs nem szerepel a modul eszközlistájában."
    return source_plugins({
        "action": "execute", "plugin": plugin_id,
        "tool": tool, "arguments": proposal.get("arguments", {}),
    })
