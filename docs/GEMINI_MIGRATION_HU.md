# JARVIS Gemini-mentes AI és magyar beszédfelismerés

A Gemini Live API-t az alkalmazás új futtatási ágában kiváltja:
- **Felhős szöveges AI:** OpenRouter `openrouter/free` (ingyenes modellválasztó).
- **Képernyő- és kameraképek:** ugyanaz a multimodális free router.
- **Helyi AI:** Ollama, a felhasználói beállításban megadott modellel.
- **Magyar mikrofon:** helyi faster-whisper, alapértelmezetten `base` modellel.
- **JARVIS beszédhang:** Edge TTS / Windows SAPI; a külön magyar JARVIS-hang PR
  finomhangolt `hu-HU-TamasNeural` profilt ad ehhez.

Az OpenRouter oldalán a `openrouter/free` nulla modellhasználati árú, de **az
ingyenes hozzáférés korlátos és nem garantáltan mindig elérhető**.
Az API-kulcsot a https://openrouter.ai/settings/keys oldalon lehet létrehozni.
Ne töltsd fel a kulcsot a nyilvános repóba.

## Magyar mikrofon telepítése (Windows)

Python 3.11/3.12 ajánlott. A JARVIS futtatási környezetében:

```powershell
python -m pip install -r requirements-voice.txt
```

Az első hangfelismeréskor a `faster-whisper` letöltheti a `base`
modell súlyait (egyszeri internetigény). A további beszédfelismerés helyben
működik és nem hív Google beszédfelismerési API-t.
A nagyobb `small` modell jobb pontosságú lehet, de lassabb:

```powershell
$env:JARVIS_WHISPER_MODEL = "small"
python main.py
```

A hangfelismerés a mikrofon némítása alatt nem rögzít; a bekapcsolt
Push-to-Talk a Ctrl+Space lenyomása alatt gyűjt hangot, egyébként a mikrofon
hangenergia alapján határolja a mondatokat. Hangos környezetben érdemes
Push-to-Talk módot használni. A késleltetés géptől függ.

## Képfeldolgozás, offline működés

A `screen_process` ugyanazt az egységes AI-klienst használja: OpenRouter
felhőn ingyenes multimodális modellt választ, offline módban a beállított
helyi modellt hívja. **Nem minden helyi Ollama-modell ért képeket**;
képfeldolgozáshoz multimodális modellt kell választani. A `qwen2.5:3b`
például általános szöveges modell, képelemzésre nem alkalmas.

Az offline mód az LLM-forgalmat helyben tartja, de egyes más JARVIS
bővítmények hálózatot használhatnak. A felhős Edge TTS sem offline;
offline módhoz a Windows SAPI tartalék hangja használatos.

## Fejlesztői ellenőrzés

```powershell
python -m compileall -q main.py ui.py actions core agent memory
python -m pip install pytest
pytest -q tests/test_gemini_migration.py
```

A teljes Windows UI és a valós mikrofon/ASR sebesség külön manuális
ellenőrzést igényel. Ez az ág nem helyettesíti a korábbi Gemini Live
alacsony késleltetésű, folyamatos multimodális sessionjét 1:1 arányban.
