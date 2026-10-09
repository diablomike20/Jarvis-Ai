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


## JARVIS AI grafikus beállítások (aktív alkalmazáskód)

A magyar hang immár a valódi asztali JARVIS AI-ban kapcsolható:

1. Nyisd meg a **Settings → System & Connectivity → Audio Routing & Hardware Controls** részt.
2. Keresd meg: **JARVIS magyar hang (helyi XTTS-v2)**.
3. A **Magyar XTTS hang engedélyezése** kapcsoló ellenőrzi
   a WAV-referenciát, a `coqui-tts` és `torch` helyi függőségeket,
   és külön rákérdez a hangfelhasználási jogosultságra.
4. Az engedélyezés csak jóváhagyás után menti
   `jarvis_voice_enabled=true` értéket a felhasználói beállításba.
5. A **Magyar hang kipróbálása** gomb egy rövid magyar mondatot generál,
   külön szálon; így az asztali felület használható marad.
   Ez a teszt indíthatja az XTTS modell első letöltését, és a modell
   licencfeltételeinek elfogadása is szükséges lehet.
6. A kapcsoló kikapcsolásakor az XTTS leáll, az Edge/SAPI tartalék
   beszédútvonal továbbra is használható.

A képernyő **nem jeleníti meg és nem naplózza** a privát
referencia-WAV elérési útvonalát. Nem tölti fel a WAV-ot GitHubra,
és nem használja CI-ban. A `voice_readiness()` könnyű ellenőrzés
nem tölti be és nem tölti le a hangmodellt.

**Nem igazolt még**: Windows célgépes tényleges GUI-interakció,
valós XTTS hangkimenet és az első modellletöltés. Ezt a tesztet
csak a saját Windows-rendszereden lehet lezárni.


## Helyi MP3/WAV importálás a JARVIS felületéből

A hangreferenciát **nem kell többé kézzel FFmpeg-paranccsal konvertálni**.
A valódi JARVIS Beállítások → System & Connectivity →
Audio Routing & Hardware Controls részen:

1. Kattints a **Helyi MP3/WAV hangminta kiválasztása** gombra.
2. Válaszd ki a saját számítógépen lévő, megfelelően engedélyezett MP3/WAV fájlt.
3. Add meg, hányadik másodperctől kérsz egy **25 másodperces** részletet.
   Érdemes beszédet és nem háttérzenét tartalmazó szakaszt választani.
4. A külön megerősítés után a JARVIS a gépre **már telepített FFmpeg**
   program segítségével helyben előállítja a **24 kHz / mono / 16-bit PCM WAV**
   fájlt; felülírja a korábbi helyi referenciát, de nem módosítja az
   eredeti MP3/WAV forrásfájlt.
5. Siker esetén a mentés helye változatlanul
   `%LOCALAPPDATA%\BrahmaAI\voices\jarvis_hu_authorized.wav`.
   A hangmintát a GUI nem tölti fel és nem helyezi GitHubra.
6. Ezután a magyar XTTS a **Magyar XTTS hang engedélyezése** kapcsolóval,
   a licenc-/jogosultság-jóváhagyás után kapcsolható be, és a
   **Magyar hang kipróbálása** gombbal szólaltatható meg.

Az FFmpeg-nek a Windows `PATH` környezeti változóban kell elérhetőnek lennie
(`ffmpeg -version`). A funkció sem FFmpeg-et, sem XTTS-t nem telepít
váratlanul. A konverzió külön Qt-szálon fut, és a kimeneti fájlt
csak sikeres formátumellenőrzés után cseréli le.

Ha a `JARVIS_VOICE_REFERENCE` környezeti változó korábban külön helyi
útvonalra lett állítva, továbbra is az élvez elsőbbséget; ilyenkor
a felület figyelmeztet az eltérésre. A privát hangfájl teljes útvonala
nem kerül a GUI státuszszövegébe, sem a CI-naplóba.

## Windows környezet előkészítése

Az aktuális Coqui telepítési útmutató szerint a `coqui-tts` 0.27.4-től
külön kell telepíteni a PyTorch-ot. A PyTorch-verzió (és esetleges
`torchcodec`), valamint a CPU/CUDA build kiválasztása a célgéptől függ.
Hivatalos útmutató:
https://coqui-tts.readthedocs.io/en/latest/installation.html

**Lényeges**: a telepítésnek abban a Python-környezetben kell megtörténnie,
amelyből a JARVIS AI-t indítod. Másik venv-be telepített XTTS-t
az alkalmazás nem fogja magától megtalálni.

A privát MP3-ból készített WAV **nem garancia** a hangminőségre:
a Windows helyi próbán ellenőrizd a magyar kiejtést, a hanghasonlóságot,
a megszakítást és a régi Edge/SAPI tartalék működését.

## CI és bizonyíték

A hangintegráció új tesztjei csak mesterséges WAV-ot és mock FFmpeg-et
használnak. Windows alatt is ellenőrzik a kód és az útvonalak
kompatibilitását, de **nem végeznek valódi XTTS modellfuttatást**.
A forrásban a hangminta, a személyes adatok és a modellfájlok továbbra
sem szerepelnek.
