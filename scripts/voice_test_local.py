"""One-shot private Hungarian JARVIS voice test on the user's own Windows PC.

Never transmits private audio. Requires enabled XTTS and valid local reference.
Run explicitly: python scripts/voice_test_local.py --speak
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions import jarvis_voice

TEST_SENTENCE = "Üdvözöllek! Itt JARVIS. A magyar hangrendszer készen áll."


def test_local_voice(*, allow_speech: bool) -> bool:
    if not allow_speech:
        return False
    state = jarvis_voice.voice_readiness()
    if not (state["enabled"] and state["can_enable"] and jarvis_voice._is_windows()):
        print("A helyi magyar hang még nincs készen: " + str(state["reason"]))
        return False
    print("Helyi magyar hangpróba: szintézis és Windows-lejátszás indul.")
    print("Ez több CPU/GPU időt vehet igénybe. A privát hangfájl helyben marad.")
    try:
        handled = jarvis_voice.speak_authorized_hungarian(TEST_SENTENCE)
    except Exception as exc:
        print("Hangpróba-hiba: " + type(exc).__name__)
        return False
    if not handled:
        print("A helyi XTTS nem tudott hangot előállítani. A JARVIS tartalék TTS útvonala megmarad.")
        return False
    print("A lejátszási hívás lezárult. Hallható hang és minőség csak a helyszínen igazolható.")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline-only JARVIS Hungarian XTTS speech test")
    parser.add_argument("--speak", action="store_true", help="Explicitly authorize local synthesis and playback")
    args = parser.parse_args(argv)
    if not args.speak:
        parser.print_help()
        return 2
    return 0 if test_local_voice(allow_speech=args.speak) else 1


if __name__ == "__main__":
    raise SystemExit(main())
