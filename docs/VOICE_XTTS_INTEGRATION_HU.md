# JARVIS AI – engedélyezett magyar XTTS-v2 (külön integrációs ág)

Ez a funkció **opcionális, alapértelmezetten kikapcsolt** beszédszintézis.
Az offline magyar mikrofonos felismerés (faster-whisper) és a jelenlegi
OpenRouter/Ollama beszélgetés változatlan marad. **Nem kell beolvasztani**
a korábbi hang PR #2 vagy PR #3 teljes ágát.

## Magánadat és jogosultság

- Csak olyan referenciát használj, amelynek beszédszintézisre történő
  felhasználására valóban rendelkezel megfelelő engedéllyel.
- Hangmintát, generált WAV-ot, személyes adatot és modellt **ne commitolj**
  a GitHub-repóba, PR-be vagy CI artifactba.
- A hangreferencia kizárólag a saját gépeden kerül felhasználásra;
  a kód nem küldi el a referenciát felhőalapú TTS-szolgáltatásnak.
- Az **Edge TTS tartalék üzemmód** online szövegtovábbítással járhat.
  A `offline_mode_enabled=true` beállítás mellett XTTS-hiba esetén
  az alkalmazás az **offline Windows SAPI** hangra vált.
- A Coqui XTTS-v2 modell licence külön vizsgálandó: a Coqui Public Model
  License csak nem kereskedelmi felhasználást enged.

## Előkészületek kizárólag a felhasználó saját Windows-gépén

1. Ellenőrizd a referenciahang jogosultságát, és válassz tiszta,
   lehetőleg 15–30 másodperces, egyetlen beszélőt tartalmazó részletet.
2. Készíts ebből *helyben* mono, 16-bites PCM WAV-fájlt. A mostani
   MP3 nem használható pusztán a kiterjesztés átnevezésével.
3. A referencia alapértelmezett privát helye:
   `%LOCALAPPDATA%\BrahmaAI\voices\jarvis_hu_authorized.wav`.
   A `BrahmaAI` belső adatútvonal szándékosan változatlan marad;
   megváltoztatása veszélyeztethetné a meglévő beállításokat.
   Alternatívaként állítsd a `JARVIS_VOICE_REFERENCE` környezeti változót
   egy **helyi, létező PCM WAV-fájlra**.
4. Egy *elkülönített, JARVIS-hoz kompatibilis Python 3.11 környezetben*
   telepítsd a szükséges csomagokat: `coqui-tts`,
   megfelelő `torch` / `torchaudio` és szükség esetén CUDA-függőségek.
   A Windows GPU/CPU változatokat ténylegesen ki kell próbálni.
   A telepítőparancsokat és verziókat nem állítjuk ellenőrzöttnek.
5. **Kizárólag tudatos felhasználói döntés után** állítsd a
   per-user `%LOCALAPPDATA%\BrahmaAI\config\app_settings.json` fájlban:
   
   ```json
   {
     "jarvis_voice_enabled": true,
     "offline_mode_enabled": true
   }
   ```

   A `jarvis_voice_enabled` kulcs hiánya vagy `false` értéke mindig
   kikapcsolva tartja az XTTS-t. Hibás beállítás vagy referencia esetén
   nem engedélyezi magát automatikusan.

**Fontos:** az XTTS modell első betöltése letöltéssel és a licenc
elfogadásával járhat. A hang bekapcsolását csak akkor végezd el, ha
ennek tudatában vagy, a modellt telepítetted, és elfogadod a feltételeit.
Az első betöltés és a beszédgenerálás nagy CPU-/GPU-terheléssel járhat.

## Integráció és korlátai

A `main.py` `speak()` továbbra is az
`actions.attention_monitor._speak_edge_native()` függvényt hívja.
A beszédválasztó először az engedélyezett XTTS-t próbálja; egyébként
az eredeti Edge/SAPI ágon működik. Az összes háttér TTS-hívást a
meglévő közös beszéd-lock sorosítja.

A `stop_native_speech()` leállítja az aszinkron XTTS hanglejátszást
és a meglévő Edge lejátszási folyamatot. **A már elindult XTTS
modell-inferencia azonban nem szakítható meg közvetlenül**: STOP után
az elkészült audio nem játszódik le.

Az XTTS WAV-kimenet lokális `BrahmaAI/voices/temp/` könyvtárba kerül,
normál lezáráskor törlődik; az egy napnál régebbi, `xtts_*.wav`
maradványokat következő XTTS-híváskor takarítja. Folyamatösszeomlás
esetén átmenetileg maradhat helyi WAV.

## Tesztelés

A `tests/test_authorized_hungarian_voice.py` kizárólag szintetikus
WAV és mock TTS/Windows playback objektumokat használ. NINCS
privát hangminta-feldolgozás, hangklónozás, modellletöltés vagy
Coqui függőség a CI-futásban.

Valós Windows teszt külön szükséges: CPU-/GPU-futtatás, magyar
kiejtés, hangminőség, leállítás, két gyors egymás utáni válasz,
mikrofon/STT regresszió, offline fallback és törölt ideiglenes WAV.

**A jelen ág önmagában nem bizonyítja a célgépes használhatóságot.**
