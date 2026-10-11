"""
The Skill Forge: Autonomous Capability Synthesis Engine
Part of Project Ultron for Jarvis AI.

Transforms natural language goals into fully architected, tested,
and hot-pluggable Python skills for Jarvis AI.
"""

from __future__ import annotations

import hashlib
import json
import uuid
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.user_paths import get_user_data_dir
from core.skill_crucible import SkillCrucible
from core.dynamic_registry import DynamicToolRegistry

logger = logging.getLogger("SkillForge")

CONFIG_DIR = get_user_data_dir() / "config"
API_CONFIG_PATH = CONFIG_DIR / "api_keys.json"



class SkillForge:
    """Autonomous synthesizer of new Jarvis AI skills."""

    @classmethod
    def forge_skill(
        cls,
        goal: str,
        skill_name: Optional[str] = None,
        context_hints: str = "",
        max_repair_attempts: int = 2,
    ) -> Dict[str, Any]:
        """Generate a REVIEWABLE draft. No new code runs until the human approves.

        Draft code is written only to the user-specific review folder, NOT
        features/. No subprocess tests, pip commands or module imports occur
        before HUD consent. A missing HUD means the draft stays unactivated.
        """
        goal = (goal or "").strip()
        if not goal or len(goal) > 2000:
            return {"success": False, "message": "Adj meg rövid, konkrét funkcióleírást."}
        name_hint = re.sub(r"[^a-zA-Z0-9_]", "_", (skill_name or "").lower()).strip("_")
        synthesis = cls._call_llm_synthesizer(goal, name_hint, context_hints)
        if not synthesis.get("success"):
            return {"success": False,
                    "message": f"A skillgenerálás nem sikerült: {synthesis.get('error')}"}

        raw_manifest = synthesis.get("manifest")
        code = synthesis.get("code")
        cases = synthesis.get("test_cases", [{"input": {}}])
        if not isinstance(raw_manifest, dict) or not isinstance(code, str):
            return {"success": False, "message": "Érvénytelen generált skillcsomag."}
        manifest = dict(raw_manifest)
        name = manifest.get("name") or name_hint
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name):
            return {"success": False, "message": "Érvénytelen vagy nem biztonságos skillnév."}
        if len(code.encode("utf-8")) > 100_000:
            return {"success": False, "message": "A generált kód túl nagy."}
        if (not isinstance(cases, list) or not 1 <= len(cases) <= 20 or
                not all(isinstance(t, dict) and isinstance(t.get("input", {}), dict)
                        for t in cases)):
            return {"success": False, "message": "Érvénytelen generált tesztesetek."}
        try:
            if len(json.dumps(cases, ensure_ascii=False)) > 20000:
                raise ValueError("Túl nagy tesztadatok.")
        except (TypeError, ValueError) as exc:
            return {"success": False, "message": f"Érvénytelen tesztadatok: {exc}"}

        # Repair malformed source *without running it*. The exact final
        # reviewed source is hashed and cannot be replaced after approval.
        for attempt in range(max(0, min(max_repair_attempts, 2)) + 1):
            valid, reason = SkillCrucible.validate_ast(code)
            if valid:
                break
            if attempt >= max(0, min(max_repair_attempts, 2)):
                return {"success": False, "message": f"Szintaktikailag hibás skill: {reason}"}
            repair = cls._repair_code(code, reason, goal)
            if not repair.get("success") or not isinstance(repair.get("code"), str):
                return {"success": False, "message": f"Javítás nem sikerült: {reason}"}
            code = repair["code"]

        manifest["name"] = name
        manifest["active"] = True
        manifest["version"] = "1.0.0"
        manifest["created_at"] = time.time()
        manifest["author"] = "JARVIS AI Skill Forge (reviewed)"
        manifest["description"] = str(manifest.get("description") or goal)[:500]
        aliases = manifest.get("aliases", [])
        triggers = manifest.get("triggers", [])
        if (not isinstance(aliases, list) or not isinstance(triggers, list) or
                any(not isinstance(x, str) for x in aliases + triggers)):
            return {"success": False, "message": "Érvénytelen trigger/alias metaadat."}
        manifest["aliases"] = list(dict.fromkeys(aliases[:16] + [name.replace("_", "")]))
        manifest["triggers"] = list(dict.fromkeys(triggers[:16] + [goal, name.replace("_", " ")]))
        manifest["parameters"] = manifest.get("parameters") or {"type": "OBJECT", "properties": {}}
        # Do not modify features/__init__.py or overwrite an existing skill.
        dest = DynamicToolRegistry.get_skills_directory() / f"{name}.py"
        if dest.exists() or (dest.parent / name).exists():
            return {"success": False, "message": f"A(z) {name} skill már létezik. Nem írom felül."}

        full_code = "FEATURE_METADATA = " + repr(manifest) + "\n\n" + code
        valid, reason = SkillCrucible.validate_ast(full_code)
        if not valid:
            return {"success": False, "message": f"Hibás generált metaadat/kód: {reason}"}
        digest = hashlib.sha256(full_code.encode("utf-8")).hexdigest()
        review_id = uuid.uuid4().hex
        review_dir = get_user_data_dir() / "skill_reviews" / review_id
        review_dir.mkdir(parents=True, exist_ok=False)
        review_path = review_dir / "candidate.py"
        review_path.write_text(full_code, encoding="utf-8")
        proposal_text = json.dumps(
            {"name": name, "manifest": manifest, "test_cases": cases,
             "digest": digest, "goal": goal}, ensure_ascii=False, indent=2,
        )
        (review_dir / "proposal.json").write_text(proposal_text, encoding="utf-8")
        proposal_digest = hashlib.sha256(proposal_text.encode("utf-8")).hexdigest()

        from core.confirm import request
        detail = (
            f"Új AI-generált Python-kód, amely a saját felhasználói jogoddal "
            f"futhat. Modul: {name}. Kód: {review_path}. "
            f"SHA256: {digest[:16]}. Előbb ellenőrizd a teljes fájlt! "
            "Jóváhagyáskor függőségellenőrzés és tesztfuttatás következik; "
            "ez NEM teljes operációs rendszeres sandbox. "
            "Csak sikeres tesztek után aktiválódik. Elutasításkor nincs futtatás."
        )
        approval = request(
            "forge-" + review_id, "JARVIS új skill jóváhagyása",
            detail, lambda: cls.approve_draft(review_dir, digest, proposal_digest),
        )
        return {
            "success": True, "pending": True, "name": name,
            "description": manifest["description"],
            "review_path": str(review_path), "digest": digest,
            "message": approval,
        }

    @classmethod
    def approve_draft(
        cls, review_dir: Path, expected_digest: str, expected_proposal_digest: str,
    ) -> str:
        """Run ONLY the exact HUD-approved code and metadata (not editable hashes)."""
        try:
            path = Path(review_dir)
            proposal_bytes = (path / "proposal.json").read_bytes()
            if hashlib.sha256(proposal_bytes).hexdigest() != expected_proposal_digest:
                return "Elutasítva: a jóváhagyás óta megváltozott a skill leírása."
            proposal = json.loads(proposal_bytes.decode("utf-8"))
            code = (path / "candidate.py").read_text(encoding="utf-8")
            if (hashlib.sha256(code.encode("utf-8")).hexdigest() != expected_digest or
                    proposal["digest"] != expected_digest):
                return "Elutasítva: a jóváhagyás óta megváltozott a skillkód."
            name = proposal["name"]
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name):
                return "Elutasítva: érvénytelen skillnév."
            target_dir = DynamicToolRegistry.get_skills_directory()
            target = target_dir / (name + ".py")
            package = target_dir / name
            if target.exists() or package.exists():
                return "Elutasítva: a skillnév már használatban van."
            valid, err = SkillCrucible.validate_ast(code)
            if not valid:
                return f"Elutasítva: {err}"
            dependencies = SkillCrucible.extract_dependencies(code)
            good, msg = SkillCrucible.resolve_dependencies(dependencies)
            if not good:
                return f"A szükséges függőségek hiányoznak. Nem telepítettem őket: {msg}"
            good, msg, _telemetry = SkillCrucible.run_sandbox_test(
                code, proposal["test_cases"],
            )
            if not good:
                return f"A tesztek nem sikerültek, a funkció inaktív maradt: {msg}"
            # Ensure the inspected bits did not change during the review/test.
            if (hashlib.sha256((path / "candidate.py").read_bytes()).hexdigest() != expected_digest or
                    hashlib.sha256((path / "proposal.json").read_bytes()).hexdigest() != expected_proposal_digest):
                return "Elutasítva: a skill tervezete a teszt közben megváltozott."
            # Only now does it become part of the runnable registry.
            package.mkdir(parents=True, exist_ok=False)
            try:
                (package / "manifest.json").write_text(
                    json.dumps(proposal["manifest"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (package / "skill.py").write_text(code, encoding="utf-8")
                (package / "test_cases.json").write_text(
                    json.dumps(proposal["test_cases"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                # Avoid duplicate .py and package entries in the registry.
                DynamicToolRegistry.initialize()
                if not DynamicToolRegistry.has_tool(name):
                    raise RuntimeError("Az új skill regisztrációja nem sikerült.")
            except Exception:
                import shutil
                shutil.rmtree(package, ignore_errors=True)
                DynamicToolRegistry.initialize()
                raise
            return f"A(z) {name} skill tesztelve és aktiválva. A kód külön új parancsként használható."
        except Exception as exc:
            logger.exception("Approved skill activation failed")
            return f"Skill aktiválási hiba: {exc}"

    @classmethod
    def _parse_json_response(cls, text: str) -> Dict[str, Any]:
        """Robustly extracts and parses a JSON object from model output, ignoring any extra trailing text."""
        clean = (text or "").strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*\n?", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\n?```\s*$", "", clean).strip()

        # 1. Try direct json.loads
        try:
            data = json.loads(clean)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # 2. Use JSONDecoder.raw_decode starting from first '{' (skips trailing notes/extra data)
        start_idx = clean.find("{")
        if start_idx != -1:
            try:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(clean[start_idx:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass

        # 3. Match outermost balanced { and }
        if start_idx != -1:
            for end_idx in range(len(clean) - 1, start_idx, -1):
                if clean[end_idx] == "}":
                    candidate = clean[start_idx:end_idx + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict):
                            return data
                    except Exception:
                        continue

        raise ValueError("Could not extract a valid JSON object from LLM output.")

    @classmethod
    def _call_llm_synthesizer(cls, goal: str, name_hint: str, context_hints: str) -> Dict[str, Any]:
        """Prompts the configured LLM to generate the complete skill package JSON."""
        system_instructions = """You are the Jarvis AI Autonomous Skill Architect ("Project Ultron").
Your mission is to invent, architect, and write a complete, standalone, production-ready Python skill plugin.

Skill Architecture Guidelines:
1. Entry point MUST be `def execute(**kwargs)` or `async def execute(**kwargs)`.
2. Must be clean, robust Python with error handling (try/except) and type annotations.
3. Default Parameter Handling:
   - In `execute(**kwargs)`, ALWAYS assign safe fallback defaults to all expected parameters (e.g. `query = kwargs.get('query') or kwargs.get('search') or 'headphones'`).
   - If called with empty kwargs `{}` (such as during sandbox verification), the skill MUST execute cleanly without throwing KeyError or TypeError.
4. Resilient Network & Safe SSL Handling:
   - When external live data or web downloads are needed, use HTTPS with certificate verification enabled and a short timeout. Never disable SSL certificate verification.
   - NEVER require or assume environment API keys (e.g. `GIPHY_API_KEY`, `OPENAI_API_KEY`). Skills must be 100% self-contained and run out of the box using public open APIs (such as Tenor public key `LIVDSRZULELA` or open REST) or local Python logic.
   - If any network call fails or times out, ALWAYS catch generic `Exception` and supply a working fallback so `execute()` NEVER returns an `{'error': ...}` dictionary.
   - Do NOT use heavy scrapers (avoid selenium/playwright).
5. Visual Deliverables, Images, GIFs, & UI Cards:
   - If the user asks for images, drawings, graphics, headphones, cars, animals, cartoons, plots, scorecards, charts, or GIFs:
     a) ALWAYS produce an actual deliverable image file (.png or .gif) saved to:
        `output_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'BrahmaAI', 'deliverables')`
        `os.makedirs(output_dir, exist_ok=True)`
        `image_path = os.path.join(output_dir, f'{actual_name}_output.png')`
     b) For diagrams, illustrations, charts, or tech visuals: Generate the visual NATIVELY using `PIL` (`from PIL import Image, ImageDraw, ImageFont`) or `matplotlib` (`import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt`).
        Style it with a sleek cyberpunk dark theme: dark slate background `#0B0F19` or `#030712`, glowing cyan `#00F0FF`, ice cyan `#38BDF8`, emerald `#10B981`, and white `#FFFFFF`.
     c) For web images/GIFs: Attempt downloading using safe SSL context or requests, but if download fails or if network is unavailable, IMMEDIATELY fall back to drawing a crisp high-tech visual deliverable using PIL/matplotlib so execution always succeeds and displays on screen.
     d) Return format for visuals:
        `return {'image_path': image_path, 'title': '...', 'summary': '...'}`
        This triggers Jarvis AI's HUD Result Wing to immediately display the card!
6. Output Format:
   Output MUST be clean JSON with exact structure:
{
    "manifest": {
        "name": "snake_case_feature_name",
        "aliases": ["alias_1", "alias_2"],
        "description": "Concise, actionable description of when and how the configured LLM should call this feature",
        "triggers": [
            "direct trigger phrase 1",
            "natural variation 2",
            "query command 3"
        ],
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "param_name": {
                    "type": "STRING|INTEGER|NUMBER|BOOLEAN",
                    "description": "What this parameter is"
                }
            },
            "required": []
        }
    },
    "code": "Full python source code including imports and def execute(**kwargs)",
    "test_cases": [
        {
            "input": {}
        }
    ]
}
Return ONLY this JSON object with no markdown fences around it.
"""

        prompt = f"""Synthesize a new skill for the following user request:
Goal: {goal}
Preferred Name: {name_hint or 'auto_generate'}
Additional Context: {context_hints}
"""

        # Fallback to Unified llm_client if available
        try:
            from llm_client import client as unified_client
            resp = unified_client.chat(
                prompt=prompt,
                system=system_instructions,
                max_tokens=8192,
                temperature=0.2,
            )
            data = cls._parse_json_response(resp)
            if not isinstance(data.get("manifest"), dict) or not isinstance(data.get("code"), str):
                raise ValueError("Unified LLM response must contain a manifest object and code string.")
            data["success"] = True
            return data
        except Exception as fallback_exc:
            return {"success": False, "error": f"LLM synthesis failed: {fallback_exc}"}

    @classmethod
    def _repair_code(cls, broken_code: str, error_msg: str, goal: str) -> Dict[str, Any]:
        """Asks LLM to fix syntax or sandbox runtime errors."""
        prompt = f"""You are repairing a Python skill generated for Jarvis AI ("Project Ultron").
The skill failed verification in the Crucible sandbox.
User Goal: {goal}
Verification Error: {error_msg}

Broken Code:
```python
{broken_code}
```

Critical Repair Instructions:
1. Ensure `def execute(**kwargs)` handles empty or missing kwargs with safe defaults.
2. If using `matplotlib`, ensure `import matplotlib; matplotlib.use('Agg')` is placed before `pyplot`.
3. If making HTTP requests, use HTTPS with certificate verification enabled and short timeouts. NEVER assume custom library exceptions or unset API keys (like GIPHY_API_KEY).
4. If downloading an image or media fails or has SSL errors, NEVER just return an error dictionary. Generate the image natively using PIL (Pillow) or matplotlib and save to `BrahmaAI/deliverables/<name>.png`.
5. Return a clean deliverable dictionary with `'image_path'`, `'title'`, `'summary'` if visual, or clean structured output.
6. The test runner checks that the returned value does NOT contain an `'error'` key. Do not return `{{'error': '...'}}`. If an error occurs, provide a graceful fallback result.
7. Return ONLY a JSON object:
{{
    "code": "Fully corrected, runnable Python code"
}}
"""
        try:
            from llm_client import client as unified_client
            raw = unified_client.chat(prompt=prompt, temperature=0.1)
            data = cls._parse_json_response(raw)
            if isinstance(data.get("code"), str):
                data["success"] = True
                return data
        except Exception as exc:
            logger.warning(f"[Forge] OpenRouter repair failed: {exc}")

        return {"success": False, "error": "Repair attempt failed."}
