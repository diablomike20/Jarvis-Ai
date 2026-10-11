# JARVIS NextGen – saját Claude Source Build integráció

**Állapot:** aktív fejlesztői munkaváltozat, nem kész / nem teljesen működésigazolt kiadás.

## Forrás és megőrzési szabályok

- JARVIS: `feature/jarvis-nextgen-working-runtime-20261011`; merge: `2f57aa76d7f860f14d58da65cb508582e0f4a0c1` vagy későbbi.
- Alap JARVIS-ágak: korábbi Claude-integráció + `delivery/jarvis-ai-complete-2026-10-10`, két szülős merge committal.
- A teljes kiadás 327 külön delivery commitjának előzményeit megtartottuk.
- Eredeti delivery HUD Git blob: `81eca8399c0e92206ac79b88d8e62dbdad3a3a0c`; az eredeti animáció megőrzése tesztelt. Windows CRLF-konverzió miatt a byte-ellenőrzés sortörésnormalizálás után történik.
- Claude Source Build: `feature/jarvis-nextgen-working-runtime-20261011`, közvetlenül a változatlan `master`-ről elágazva.
- Windows builder ismert jó kiindulási commit: `2f00cdd98359cfd52823b7aa254523b0106cd488` (pin a `installer/prepare_claude_runtime.ps1` fájlban).
- `main`, `delivery`, eredeti Claude `master` nem lett írva.

## Elvégzett műszaki implementáció

1. Claude-CLI Node folyamat: meglévő `core/claude_runtime.py`; `stream-json`/STDIO; explicit, nem automatikus felhasználói engedély.
2. **Új Windows MCP executor-gate:** `core/claude_permission_broker.py`. Sessionenként külön loopback HTTP-broker és titok; kizárólag ténylegesen jóváhagyott `mcp__brahma_windows__desktop_*` kérésekhez, pontos argumentumokhoz kötött, lejáró, egyszer használatos engedély.
3. A `core/brahma_mcp_stdio.py` immár fail-closed módon tagadja meg a nem hitelesített `tools/call` műveleteket. Az upstream CLI permission-flow önmagában nem elegendő végrehajtói engedélynek.
4. A Claude Source Build builder megőrzi a Windows specifikus javításokat, de külön master-alapú ágban; a sourcemap-file írási útvonalakat validálja, symlinket tilt, cache-bizonyítékként tartalmi SHA-256-ot tárol.
5. A modellrendszer kötelező díjmentes OpenRouter-utat használ (`openrouter/free` vagy `:free`). Opcionálisan konfigurálható helyi Anthropic Messages-kompatibilis modell, kizárólag HTTP loopback címen: `claude_code_local_anthropic_url` és saját `claude_code_model`.
6. Közös JARVIS-delivery + Claude összefésülés: `main.py`, `ui.py`, `or_client.py`, `installer/BrahmaEvo.spec`, `requirements.txt`, `.gitignore` hárombázisú összevetéssel, a hang/UI/creative-studio modulok megőrzésével.
7. Python unit/regresszió: jóváhagyás / egyszeri felhasználás / lejárat / replay tiltás; free/local model policy; egész kiadás integritása.
8. Windows packaged smoke: valódi `node.exe cli.js --version`, MCP `initialize`, `tools/list`, **jogosulatlan `desktop_type` tiltása**; eredeti HUD és delivery-funkciók ellenőrzése.

## Jelenlegi CI és bizonyítás

Workflow-k:
- `.github/workflows/claude-runtime-tests.yml` – Linux és Windows Python unit.
- `.github/workflows/jarvis-full-windows.yml` – Windowsra fordítás, CLI és MCP smoke, telepítő és portable artifact.
- Az eddigi zöld Python tesztek és a korábban sikeres Windows-buildek **nem jelentenek valós modell-/hang-/desktop-end-to-end igazolást**.

A legújabb GitHub Actions runokat a fejlesztői ág Actions fülén kell ellenőrizni a kiadás minősítése előtt.

## Jelenleg **nem** igazolt működések – nem lehet „kész”-nek nevezni

- Ingyenes OpenRouter modell valós streaming + tool-use kompatibilitása a rekonstruált Claude Code CLI-vel.
- Helyi Anthropic-kompatibilis backend valós CLI-képességei és a modell minősége.
- Teljes Claude STDIO `control_request → user approval → MCP grant → Windows GUI operation → result` élő Windows desktop-on.
- Hang, beszédmegszakítás, eredeti HUD élő hangszinkron, Android, memória és multi-agent hosszú munkamenet együtt.
- Tiszta Windows gépes telepítés, elindítás, hang- és GUI-próbák és uninstall.

## Következő fejlesztési kör / kötelező elfogadási kapu

1. Legfrissebb egyesített commitra Windows Setup build és új, emelt szintű MCP-deny smoke PASS.
2. Windows személyes GUI-teszt: app indul, hang és jóváhagyás.
3. Felhasználó ingyenes OpenRouter API-kulcsával vagy local kompatibilis modellel élő Agent SDK/CLI turn teszt. Külső fizetős modell tiltott.
4. Valódi fájllétrehozás és tesztfuttatás jóváhagyással; tiltott művelet visszautasítása.
5. Tartós session/resume, időkorlát, a gyermekfolyamatok tiszta megszüntetése.
6. Minden meglévő delivery-funkció (hang, original HUD, kreatív eszközök, Android, memoria) regressziós validálása.

## Csomagolás és ideiglenes artifacts

A GitHub Actions / artifact-feltöltés jelenlegi működése **változatlanul marad**, a felhasználó kifejezett kérésére. Nem került sor a korábbi artefaktumok törlésére. A személyes használatra szánt végleges binárisok ideiglenes GitHub tárolását a projekt befejezéséig meghagytuk.

**Ne olvasszuk össze a stable ágakkal és ne nevezzük full-working release-nek a valós end-to-end igazolás előtt.**
