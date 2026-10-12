# JARVIS HU VOICE LAB – izolált helyi A/B hangpróba

**2026-10-12 / ELŐKÉSZÍTŐ FEJLESZTÉS.** Ez **nem** kész, meghallgatott hangmodell, nem bizonyítottan működő Windows GPU build, és még nem része a JARVIS runtime-nak. A `main` és a Claude Code stabil ág érintetlen.

## Miért külön voice lab?

- A Work-kolléga feladata: a 3 filmben JARVIS magyar jeleneteinek **valódi** ellenőrzése, hozzáférhető filmhang és pontos időbélyeg átadása.
- Ezen ág feladata: privát hangfájlok kinyerése, diagnosztika, tiszta WAV-referenciák, **helyi** F5 Hungarian / XTTS-v2 A/B generálás.
- A korábbi `feature/authorized-hungarian-jarvis-voice`, `feature/jarvis-ai-visual-rebrand` és korábbi hang-integrációs megoldások **nem** kódalapok.
- A generált `voice_private` könyvtárat tilos nyilvános GitHubra vagy képesség-telemetriába feltölteni.
- Minden bemeneti film- és szinkronhangot a felhasználó által engedélyezett körből kezeljünk.

## Előfeltételek

Windows 10/11 x64, **Python 3.11**, FFmpeg a PATH-ban, legalább 5-15 s színész szerint ellenőrzött JARVIS beszéd (WAV) és annak **pontos** magyar átirata. CUDA támogatású NVIDIA GPU ajánlott; az RTX/VRAM adatok nélkül a teljesítmény nem jósolható meg.

A hangmodellek külön licenceken érhetők el, és az ingyenes személyes használat nem azonos a szabad kereskedelmi terjeszthetőséggel. F5 Hungarian modell: CC BY-NC 4.0, XTTS-v2 modell: Coqui Public Model License. Ezeket a modelleket **nem** csomagoljuk automatikusan a publikus repositoryba.

### 1. Akusztikai elővizsgálat

Nyiss terminált a JARVIS repository gyökerében, a feltöltött MP3 Windowsra elmentett példányával:

```powershell
$lab = Join-Path $env:LOCALAPPDATA "JarvisAI\voice_private"
New-Item -ItemType Directory -Force $lab | Out-Null

python tools/voice_corpus/analyze_reference.py `
  --input "C:\Hangmintak\Karpati_Levente_MaRecord.mp3" `
  --report (Join-Path $lab "marecord_preflight.json")
```

A kimenet: MP3 formátum, hossz, codec, mért átlagos és csúcshangerő, csendnek tűnő intervallumok és SHA-256. Ez **nem** színészfelismerés vagy valódi speech VAD. A háttérzene is nem-csendként jelenik meg.

### 2. WAV referencia előkészítése

A *ténylegesen meghallgatott, JARVIS-ként megszólaló* részből készíts külön WAV-ot, lehetőleg egy teljes természetes mondat 5–15 másodpercben, utólagos mesterséges hangszínezés nélkül.

Például már ellenőrzött 5–15 s körüli helyi klip konvertálása:

```powershell
ffmpeg -hide_banner -i "C:\Hangmintak\ellenorzott_jarvis_jelenet.mp3" `
  -vn -ac 1 -ar 24000 -c:a pcm_s16le `
  "$lab\reference_01.wav"
```

A referencia pontos, teljes elhangzó szövegét UTF-8 kódolásban add meg a `$lab\reference_01.txt` fájlban. **Ne generálj hozzá kitalált átiratot.** A filmes dialógus és a MaRecord szövege ne keveredjen.

Nagyobb filmfájlból a `prepare_corpus.py` center kivonás és a `*.segments.csv` emberi ellenőrzésű vágás használható: [README_HU.md](README_HU.md).

### 3. A két hangmotor külön virtuális környezetben

Ne telepíts AI-csomagokat a JARVIS alkalmazás fő Python-környezetébe. A Windows CUDA-s PyTorch/torchaudio megfelelő verzióját az aktuális PyTorch telepítő útmutatója alapján válaszd ki: https://pytorch.org/get-started/locally/

**F5 (első modellpróba):**

```powershell
py -3.11 -m venv "$lab\venv_f5"
& "$lab\venv_f5\Scripts\python.exe" -m pip install -U pip

# PyTorch + torchaudio telepítését a rendszeredhez illő módon végezd el.
& "$lab\venv_f5\Scripts\python.exe" -m pip install f5-tts soundfile huggingface_hub
```

A nyilvánosan publikált F5 magyar modelljének szükséges fájljai:
- https://huggingface.co/Maxdorger29/f5-tts-hungarian
- `model_last_final.safetensors` (~640 MB)
- `vocab.txt` (magyar karakterkészlet)

A modellt **ne** az eredeti F5 v1 Base súlyokkal keverd össze. A magyar checkpointot és a hozzá tartozó vocabot töltsd le a magánkönyvtárba:

```powershell
& "$lab\venv_f5\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; import os; snapshot_download(repo_id='Maxdorger29/f5-tts-hungarian', allow_patterns=['model_last_final.safetensors','vocab.txt','config.json'], local_dir=os.path.join(os.environ['LOCALAPPDATA'],'JarvisAI','voice_private','models','f5_hungarian'))"
```

**XTTS-v2 (külön kontroll):**

```powershell
py -3.11 -m venv "$lab\venv_xtts"
& "$lab\venv_xtts\Scripts\python.exe" -m pip install -U pip

# Előbb platformkompatibilis PyTorch + torchaudio a hivatalos telepítési útmutató szerint.
& "$lab\venv_xtts\Scripts\python.exe" -m pip install coqui-tts "transformers<5"
```

A Coqui-t a jelenleg karbantartott `coqui-tts` Python-csomagból telepítsd, ne a korábbi `TTS` elnevezésű elavult kiadásból. Az XTTS súlyok első betöltése letöltést és licencelfogadást igényelhet; csak explicit `--allow-xtts-model-download` paraméterrel indul.

**A hangfelvételek nem töltődnek fel az előző parancsokkal.** A modellsúlyok letöltése természetesen hálózatot használ.

### 4. A/B generálás

**F5 Hungarian:**

```powershell
& "$lab\venv_f5\Scripts\python.exe" tools/voice_corpus/tts_compare.py `
  --workspace $lab `
  --reference "$lab\reference_01.wav" `
  --reference-transcript "$lab\reference_01.txt" `
  --engines f5 `
  --f5-checkpoint "$lab\models\f5_hungarian\model_last_final.safetensors" `
  --f5-vocab "$lab\models\f5_hungarian\vocab.txt" `
  --device auto --rounds 1
```

**XTTS-v2:**

```powershell
& "$lab\venv_xtts\Scripts\python.exe" tools/voice_corpus/tts_compare.py `
  --workspace $lab `
  --reference "$lab\reference_01.wav" `
  --reference-transcript "$lab\reference_01.txt" `
  --engines xtts `
  --device auto --allow-xtts-model-download --rounds 1
```

Az `evaluation/ab_YYYYMMDD...` könyvtárban:
- generált, még **nem értékelt** WAV fájlok;
- `benchmark.json`: motornév, mondat, referencia hash, generálási idő, RTF (generálási idő / hanghossz), mintavétel és output hash;
- hibánál naplózott státusz; **nincs kitalált hanghűségi pontszám**.

Ha az adott motorhoz a szükséges Python-csomag hiányzik, a futás hibát jelent, nem vált át másik hangra.

### 5. Szubjektív hallgatási értékelés

Minden WAV-hoz 1–5 skálán külön értékelendő: hangazonosság, magyar kiejtés, ritmus, JARVIS-beszédstílus, zaj/artefakt. Ne keverjük össze a technikai RTF-számot a beszédhang minőségével.

**A jelenlegi code status:** eszköz + offline unit teszt forrás készült; nincs valós GPU generálás, és a felhasználó MaRecord MP3 fájlját a futtatókörnyezeti hiba miatt még nem tudtuk mérni.

## Claude után következő integrációs elv

Csak a stabil Claude runtime integráció befejezése után központi `VoiceManager`, egységes TTS event API, aszinkron lejátszás, megszakítás, HUD állapotváltás, privát hangprofil, hiba esetén **text-only** (Original Voice Only). A korábbi visszautasított brancheket nem vesszük alapul, nem nyúlunk az eredeti HUD geometriájához.
