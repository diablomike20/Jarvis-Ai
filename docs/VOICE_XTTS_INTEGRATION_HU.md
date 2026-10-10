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


## 2026-10-10 — Windows célszámítógépes indítás előkészítése

**Ne a CI-ban, hanem a saját Windows-gépen, a JARVIS-hoz tartozó
Python-környezetben** futtasd az alábbi lépéseket. Az ellenőrzőprogram
nem olvassa ki a referencia hangját, nem indít AI-modellt, és nem tölti fel
a fájlt sehova. A kimenetből a személyes hangútvonalakat kihagyja.

A projekt gyökérkönyvtárából:

~~~powershell
python scripts/voice_doctor.py --json
python scripts/voice_doctor.py --probe-runtime
~~~

A második parancs a **telepített PyTorch és Coqui TTS Python importját**
is megpróbálja, GPU-t jelez, de nem tölti be a modellt és nem generál
hangot. Az FFmpeg ellenőrzése csak azt jelzi, hogy elérhető-e a PATH-on.
Ha hiányzik a Torch, Torchaudio vagy Coqui, a hivatalos telepítési
útmutató alapján, **ugyanabba a Python-környezetbe** telepítsd. Nem
telepítünk automatikusan semmit:

https://coqui-tts.readthedocs.io/en/latest/installation.html

Amennyiben a modell nincs helyben gyorsítótárazva, az XTTS-v2 első
GUI-hangpróbája letöltési/licenckérdéssel akadhat el a háttérben.
Ezért célszerűbb az **egyértelműen kezdeményezett, interaktív** betöltés
a terminálban, saját elfogadásoddal:

~~~powershell
python scripts/prepare_xtts_model.py --download
~~~

**Ez a parancs internetet használhat a nyilvános Coqui XTTS-v2
modell letöltéséhez**, és elfogadandó licencfeltételeket mutathat.
A licencet a felhasználó kezeli, a parancs nem fogadja el helyette.
A privát referenciahangot egyáltalán nem olvassa be; kizárólag a
nyilvános modellt próbálja előkészíteni. A parancs külön
\`--download\` kapcsoló nélkül nem tölt modellt.

Utána a JARVIS grafikus felületén a Settings → System & Connectivity →
Audio Routing & Hardware Controls részben importáld a helyi
MP3/WAV-ot, kapcsold be a magyar XTTS-t, és próbáld ki a gombbal.
A modell cache-nek a JARVIS futtatását végző ugyanazon felhasználó
környezetében kell lennie.

**Visszaállás:** kapcsold ki a magyar XTTS-hangot; a régi SAPI/Edge
beszédútvonal megmarad. A STOP már a várakozó, még el nem kezdett XTTS
kéréseket is megszakítja. Az opcionális hangpróba és helyi
hangkonverzió daemon háttérszálon fut, ezért nem tartja fogva a
program bezárását, de egy már elindult FFmpeg- vagy XTTS-modellművelet
az operációs rendszeren belül még befejeződhet.

**Továbbra sincs igazolva**: valódi Win10/11 GUI + PyTorch CUDA,
XTTS-v2 modellbetöltés és kiejtés, privát referenciahang használatával
végzett sikeres beszéd, illetve teljes STT→AI→TTS E2E.


## Egyparancsos Windows-beüzemelés — 2026-10-10

A működő JARVIS \`bootstrap.ps1\` telepítője a projekt gyökerében
\`.venv\` nevű Python környezetet hoz létre. Az új beüzemelő **ezt
használja**, nem másik Pythonhoz telepíti a modellt, és nem hoz létre
új környezetet. A meglévő JARVIS-projekt gyökeréből, PowerShellben:

**Csak ellenőrzés, semmilyen telepítés vagy letöltés:**

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hungarian_voice.ps1
~~~

**Felhasználó által indított tényleges telepítés és modelltöltés:**

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hungarian_voice.ps1 -Install -InstallFFmpeg -PrepareModel
~~~

A telepítő a szükséges nyilvános Coqui/PyTorch csomagokat a
**meglévő alkalmazás-venvbe** helyezi, a Torch alapértelmezésben
a hivatalos CPU indexéről érkezik. A korábban telepített Torch/TorchAudio
csomagokat nem cseréli le, ha mindkettő jelen van; NVIDIA CUDA build
automatikus kiválasztását nem ígéri. FFmpeg csak az \`-InstallFFmpeg\`
kapcsolóval települ; a \`-PrepareModel\` explicit modellcache-letöltést
és interaktív licenckérdést is kiválthat. **Az elfogadás nem automatizált.**
Nincs adminjogkérés és nincs privát hangmintafeltöltés. A telepítés
befolyásolhatja a meglévő \`.venv\` csomagverzióit: előtte készíts
visszaállítási pontot a projektfájlokról, és szükség esetén futtasd
újra a JARVIS eredeti követelményfájl szerinti telepítést.

Ha a saját \`ffmpeg\` parancs még nem érhető el közvetlenül a winget
telepítése után, **nyiss új terminált**, és ellenőrizd:
\`ffmpeg -version\`.

Ezután a JARVIS beállításaiban, a Magyar XTTS hang szekcióban
importálhatod a saját, megfelelő engedéllyel rendelkező hangfájlt.
Az automatikus előkészítés a PCM WAV-ot per-user lokális adatkönyvtárba
helyezi. A magyar hangot csak ezután, a felületen látható
külön beleegyezés után lehet bekapcsolni.

**Első hallható teszt** a JARVIS kezelőfelületi próbagombjával,
vagy kifejezett CLI-paranccsal:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_hungarian_voice.ps1 -Speak
~~~

Ez nem feltétlenül azonnali: CPU-n a szintézis lassú lehet.
A CLI visszatérési kódja csak a lejátszási útvonal sikerét jelzi,
nem ellenőrzi akusztikai módszerrel, hogy a hangszórón tényleg
hallható volt-e a beszéd vagy megfelelő volt-e a hangminőség.
A STOP események továbbra is megszakíthatják a próbát.

**Mit tesztel a CI?** A Windows runner PowerShell 5.1 nyelvtani
ellenőrzést és a tényleges \`-Install\` nélküli diagnosztika-futtatást
végez ideiglenes JARVIS \`.venv\`-ben. A Coqui és PyTorch
telepítését, a több gigabájtos modell letöltését és a valós
beszédkimenetet **nem végzi el automatikusan**.

Referenciák:
- Coqui telepítés: https://coqui-tts.readthedocs.io/en/latest/installation.html
- Windows PyTorch: https://pytorch.org/get-started/locally/
- XTTS-v2 magyar nyelv: https://coqui-tts.readthedocs.io/en/latest/models/xtts.html


## Telepítés közvetlenül a JARVIS kezelőfelületéről

Ha a projekt saját Windows telepítése már létezik és a \`.venv\`
könyvtárban elérhető, a valódi JARVIS **Settings → System &
Connectivity → Audio Routing & Hardware Controls** képernyőjén
megjelenik a **Magyar hangmotor előkészítése (Windows)** gomb.

A gomb **kifejezett megerősítést kér**, és külön, látható
PowerShell-konzolban indítja a \`scripts/setup_hungarian_voice.ps1\`
fájlt \`-Install -InstallFFmpeg -PrepareModel\` paraméterekkel.
Itt a felhasználó láthatja a letöltéseket, a telepítési hibákat és
az XTTS modelllicenc esetleges elfogadási kérését. A JARVIS
nem fogadja el automatikusan a licencet, és nem küld hangmintát
GitHubra vagy más szolgáltatásba.

Ha az alkalmazás telepített EXE-ből fut, és nincs mellette
a projekt \`.venv\` környezete vagy a PowerShell beüzemelő,
ez a fejlesztői funkció figyelmeztetést ad. Nem próbálja
módosítani a telepített EXE környezetét.

A beüzemelés után a magyar XTTS kapcsolóját és a referencia
importálását **továbbra is külön** kell aktiválni, csak jogosult
referenciahanggal. A hangpróba csak így engedélyezhető.
