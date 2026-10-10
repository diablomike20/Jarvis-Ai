"""No private voice data, torch, download or playback in CI."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("voice_test_local", ROOT/"scripts"/"voice_test_local.py")
voice_cli = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(voice_cli)


def _ready(enabled, can_enable):
    return {"enabled":enabled, "can_enable":can_enable, "reason":"Synthetic status"}


def test_no_explicit_speak_does_not_invoke_model(monkeypatch):
    monkeypatch.setattr(voice_cli.jarvis_voice, "speak_authorized_hungarian",
                        lambda _: (_ for _ in ()).throw(AssertionError("must not synthesize")))
    assert voice_cli.main([]) == 2
    assert voice_cli.test_local_voice(allow_speech=False) is False


def test_unready_local_voice_stops_before_synthesis(monkeypatch, capsys):
    monkeypatch.setattr(voice_cli.jarvis_voice, "voice_readiness", lambda:_ready(False, False))
    monkeypatch.setattr(voice_cli.jarvis_voice, "_is_windows", lambda:True)
    monkeypatch.setattr(voice_cli.jarvis_voice, "speak_authorized_hungarian",
                        lambda _: (_ for _ in ()).throw(AssertionError("must not synthesize")))
    assert voice_cli.main(["--speak"]) == 1
    assert "nincs készen" in capsys.readouterr().out


def test_success_only_after_opt_in(monkeypatch, capsys):
    synth = []
    monkeypatch.setattr(voice_cli.jarvis_voice, "voice_readiness", lambda:_ready(True, True))
    monkeypatch.setattr(voice_cli.jarvis_voice, "_is_windows", lambda:True)
    monkeypatch.setattr(voice_cli.jarvis_voice, "speak_authorized_hungarian",
                        lambda words: synth.append(words) or True)
    assert voice_cli.main(["--speak"]) == 0
    assert synth == [voice_cli.TEST_SENTENCE]
    assert "Hallható hang" in capsys.readouterr().out


def test_no_sample_path_leaked_if_model_fails(monkeypatch, capsys):
    monkeypatch.setattr(voice_cli.jarvis_voice, "voice_readiness", lambda:_ready(True, True))
    monkeypatch.setattr(voice_cli.jarvis_voice, "_is_windows", lambda:True)

    def synthetic_failure(words):
        raise RuntimeError("C:\\Private\\audio\\voice.wav")
    monkeypatch.setattr(voice_cli.jarvis_voice, "speak_authorized_hungarian", synthetic_failure)
    assert voice_cli.main(["--speak"]) == 1
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "Private" not in output
