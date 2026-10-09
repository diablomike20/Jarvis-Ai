# Magyar JARVIS-hang – engedélyezett helyi hangminta

Ebben az ágban a JARVIS válaszait az opcionális **XTTS-v2** modell mondhatja
ki magyarul. A modell támogatja a magyar (`hu`) nyelvet és a megadott
referenciahang alapján történő hangszintézist. A GitHub-tároló **nem
tartalmaz színészfelvételt és hangklónt**.

## 1. Engedélyezett hangminta

Készíts egy tiszta (zene és háttérzaj nélküli), lehetőleg 15–30 másodperces
WAV-fájlt, amelynek AI-hangszintézisre történő használatára engedélyed van.
A felvétel és a színészi hang másolásának joga két különböző kérdés lehet:
filmből kivágott hang használatához további jogosulti engedély is szükséges
lehet.

Tedd ide (Windows):

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\BrahmaAI\voices"
Copy-Item "C:\hangmintak\engedelyezett.wav" "$env:LOCALAPPDATA\BrahmaAI\voices\jarvis_hu_authorized.wav"
```

A forrásútvonalat a valódi fájlod helyére kell cserélni. Alternatívaként
beállítható a `JARVIS_VOICE_REFERENCE` környezeti változó egy abszolút
WAV-útvonalra. **A hangfájlt ne töltsd fel a nyilvános GitHub-repóba.**

## 2. XTTS telepítés

A JARVIS indításához használt **ugyanabba a Python-környezetbe** telepítsd
az XTTS futtatókörnyezetet (célszerű Python 3.11):

```powershell
python -m pip install --upgrade pip
python -m pip install coqui-tts
```

A PyTorch telepítési módja a videokártyától/CUDA-verziótól függhet. Ha
a telepítés hiányzó `torch`/`torchaudio` miatt sikertelen, a PyTorch
hivatalos telepítési útmutatójának megfelelő parancsot használd.
A modell első betöltése letöltést és a modelllicenc elfogadását igényelheti;
a későbbi beszédgenerálás helyben történik.

**Fontos**: az XTTS modellt a Coqui Public Model License védi, ezért a
modellt és a hangot csak az engedélyekkel összeegyeztethető célra használd.

## 3. Működés

- A JARVIS minden beszédkérésnél előbb ellenőrzi, létezik-e a fenti WAV.
- Ha igen és a modell telepítve van, magyar beszédet generál (`language="hu"`).
- A referenciahang és az újonnan generált WAV helyben marad; az ideiglenes
  kimeneti WAV lejátszás után törlődik.
- Ha nincs minta, a modell hiányzik vagy a generálás hibázik, az Edge/SAPI
  beszédszintézis veszi át a feladatot.
- A hangklónozás kikapcsolható a felhasználói `app_settings.json` fájlban:
  `"jarvis_voice_enabled": false`.
- A `force_edge=True` hívások továbbra is az eredeti TTS-útvonalon mennek.

A hangklónozás nem javítja a mikrofonos beszédfelismerést. A Gemini Live
kivezetése után a folyamatos, kétirányú beszélgetéshez külön STT- és
mikrofonfolyamat szükséges. CPU-n az XTTS jóval lassabb lehet, mint GPU-val.
