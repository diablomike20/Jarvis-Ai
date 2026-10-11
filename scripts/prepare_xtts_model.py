"""Explicit, interactive one-time model setup on the user's OWN Windows PC.

Usage from the same Python interpreter used by JARVIS:
    python scripts/prepare_xtts_model.py --download

The program does NOT read, copy, inspect or upload any voice reference.
It may download the public Coqui XTTS-v2 model, and it preserves Coqui's
own licensing prompts. It never grants license acceptance on behalf of the
user and never silently installs dependencies.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def prepare_model(*, approved: bool) -> bool:
    """Load/cache the public XTTS model only after an explicit CLI request."""
    if not approved:
        return False
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from actions.jarvis_voice import _is_windows, _load_model
    if not _is_windows():
        print("A JARVIS magyar hangja jelenleg csak Windows alatt támogatott.")
        return False
    print("A nyilvános XTTS-v2 modell helyi előkészítése indul.")
    print("Ez internet-hozzáférést és a modelllicenc feltételeinek elfogadását kérheti.")
    print("A privát hangmintát ez a parancs egyáltalán nem használja.")
    try:
        model = _load_model()
    except Exception as exc:
        # Do not log exception text: third-party errors may include private dirs.
        print("Modellindítási hiba:", type(exc).__name__)
        print("Futtasd előbb: python scripts/voice_doctor.py --probe-runtime")
        return False
    if model is None:
        print("Az XTTS modell nem töltődött be.")
        return False
    print("XTTS-v2 betöltve. Most már elindítható a hangpróba a JARVIS felületén.")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Interactive local XTTS-v2 model cache setup")
    parser.add_argument("--download", action="store_true", help="Allow public model download and interactive licensing prompt")
    args = parser.parse_args(argv)
    if not args.download:
        parser.print_help()
        print("Nincs modellbetöltés. Csak explicit --download kapcsolóval indul.")
        return 2
    return 0 if prepare_model(approved=args.download) else 1


if __name__ == "__main__":
    raise SystemExit(main())
