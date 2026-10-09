"""Natural-language bridge from Hungarian JARVIS instructions to editor MCP tools.

The AI only *plans* an MCP call. The Creative Studio adapter enforces the
actual registered tools and the trusted on-screen confirmation for edits.
"""
from __future__ import annotations

import json
import re

from actions.creative_studio import (
    CAPABILITY_CATALOGUE, READ_ONLY_TOOLS, _session, creative_studio,
)

_EXPLICIT = {
    "photocraft": ("photocraft", "photo craft"),
    "lightcraft": ("lightcraft", "light craft"),
    "filmcraft": ("filmcraft", "film craft"),
}
_HINTS = {
    "photocraft": ("psd", "réteg", "layers", "maszk", "rajz", "képszerkeszt", "képet"),
    "lightcraft": ("raw", "fotó", "fénykép", "expozíció", "színhőmér", "lightroom", "preset"),
    "filmcraft": ("videó", "video", "klip", "idővonal", "filmvág", "felirat", "timeline"),
}
_INTENT = (
    "javíts", "szerkes", "vág", "alakíts", "állíts", "export", "import", "dolgozz",
    "készíts", "módos", "rend", "helyez", "nyisd", "ments", "adj hozzá",
    "mutasd", "tedd", "korrig", "kever", "színezz", "világos", "sötét",
)
_LIST = ("parancs", "funkció", "képesség", "mit tud", "művelet", "segítség")
_STATUS = ("állapot", "státusz", "telepít", "elérhető", "működik", "status")


def recognize_creative_intent(text: str) -> str | None:
    """Infer editor only for strong context, keeping normal assistant chat intact."""
    lower = (text or "").casefold()
    if "creative studio" in lower or "kreatív stúdió" in lower:
        return "all"
    for name, aliases in _EXPLICIT.items():
        if any(alias in lower for alias in aliases):
            return name
    if not any(word in lower for word in _INTENT):
        return None
    matched = [name for name, hints in _HINTS.items()
               if any(hint in lower for hint in hints)]
    return matched[0] if len(matched) == 1 else None


def _rank_tools(app: str, text: str, discovered: dict[str, dict]) -> list[dict]:
    """Offer the model supported tools rather than hallucinated CLI methods."""
    user_words = {
        x for x in re.findall(r"[a-zA-Záéíóöőúüű]{3,}", text.casefold())
    }
    app_defaults = {
        "photocraft": ("list_commands", "doc_inspect", "session_inspect"),
        "lightcraft": (
            "query_photos", "list_controls", "get_develop", "set_develop",
            "apply_preset", "crop", "import", "render_photo", "export", "run_command",
        ),
        "filmcraft": (
            "command_list", "project_inspect", "sequence_inspect", "media_import",
            "command_run", "command_batch", "render_frame", "render_preview",
        ),
    }
    scores = []
    for name, metadata in discovered.items():
        description = str(metadata.get("description", ""))
        searchable = (name + " " + description).casefold()
        hits = sum(1 for word in user_words if word in searchable)
        score = hits * 5 + (12 if name in app_defaults[app] else 0)
        scores.append((score, name, description[:260]))
    scores.sort(key=lambda row: (-row[0], row[1]))
    return [
        {"name": name, "description": description}
        for _, name, description in scores[:55]
    ]


def handle_creative_text(text: str) -> str:
    """Resolve a Hungarian instruction to 0–8 editor actions."""
    app = recognize_creative_intent(text)
    if not app:
        return "Ez nem Creative Studio parancs."
    if app == "all":
        return creative_studio({"operation": "catalogue", "app": "all"})
    lower = text.casefold()
    if any(fragment in lower for fragment in _STATUS):
        return creative_studio({"operation": "status", "app": app})
    if any(fragment in lower for fragment in _LIST):
        return creative_studio({"operation": "discover", "app": app, "limit": 35})

    try:
        server = _session(app)
        known = server.list_tools()
        if not known:
            return f"A(z) {app} MCP szerver nem hirdetett eszközöket."
        tool_catalogue = _rank_tools(app, text, known)
        from llm_client import client as ai
        prompt = json.dumps({
            "request": text,
            "app": app,
            "supported_tools": tool_catalogue,
            "functionality": CAPABILITY_CATALOGUE[app],
        }, ensure_ascii=False)
        plan = ai.chat_json(
            prompt,
            system=(
                "You are a careful tool planner for an existing editor MCP server. "
                "Reply ONLY as JSON with either {\"question\":\"...\"} if a filename, "
                "selection, id or other crucial detail is missing, "
                "{\"tool\":\"exact_tool_name\",\"arguments\":{...}} for ONE action, "
                "or {\"steps\":[{\"tool\":\"exact_tool_name\",\"arguments\":{...}},...]} "
                "for 2-8 sequential actions. Use ONLY exact names from supported_tools. "
                "Do not invent file paths, photo ids, clip ids or other identifiers. "
                "Do not execute unrequested actions. Use a read-only inspect command "
                "first if document state is unknown. No shell commands. "
                "Answer clarification questions in Hungarian."
            ),
            max_tokens=1300,
        )
        if not isinstance(plan, dict):
            raise ValueError("Az AI nem adott értelmezhető művelettervet.")
        if plan.get("question"):
            return str(plan["question"])[:500]
        if isinstance(plan.get("steps"), list):
            steps = plan["steps"]
            if not 1 <= len(steps) <= 8:
                return "Legfeljebb nyolc lépéses terv hajtható végre."
            for step in steps:
                if not isinstance(step, dict) or step.get("tool") not in known:
                    return "Az AI nem létező MCP-parancsot választott."
            return creative_studio({
                "app": app, "operation": "batch", "steps": steps,
            })
        tool = plan.get("tool")
        if not isinstance(tool, str) or tool not in known:
            return "Nem sikerült létező szerkesztőparancsot kiválasztani."
        return creative_studio({
            "app": app,
            "operation": ("inspect" if tool in READ_ONLY_TOOLS[app] else "execute"),
            "tool": tool, "arguments": plan.get("arguments", {}),
        })
    except Exception as exc:
        return (
            f"A(z) {app} szerkesztési terv nem készült el: {exc}. "
            "A telepített parancsokat a szerkesztő neve és a 'funkciók' "
            "utasítással kérheted le."
        )
