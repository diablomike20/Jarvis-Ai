# JARVIS AI — különálló Orb + Qt WebEngine tesztlabor

**Kísérleti projekt, nem produkciós animációcsere.** A meglévő
`assets/web_background/index.html`, `ui.py`, `main.py`,
a PR #9 magyar XTTS motorja és a főág nem módosulnak.

Csomag: `jarvis-ai-web-animation@0.1.2`, React / Three.js, MIT licenc.
Forrás: https://github.com/cyber1443/jarvis-ai-orb-web-animation

## A. Önálló böngészős teszt

Node.js 22 és npm környezetben:

```sh
cd experiments/jarvis-orb-web-demo
npm install
npm test
npm run build
npm run dev
```

Nyisd meg a `http://127.0.0.1:5173/` címet. Az alkalmazás külön
állapotgombokat, hangerőszimulációt, minőségválasztót, FPS- és p95
**böngésző UI-képkocka** adatot tartalmaz.

Konzolból vagy Qt WebEngine `runJavaScript` hívással:

```js
setBrahmaState('SPEAKING')
setAudioLevel(0.75)
```

A `LISTENING` és `SPEAKING` egyedi 3D animációs állapotot használ;
a többi `IDLE`, `THINKING`, `SUCCESS`, `ERROR`, `OFFLINE`
állapot a JARVIS működési jelzéseihez igazodik.

## B. Külön Qt WebEngine-ablak Windows rendszeren

**Nem kell módosítani vagy elindítani a teljes JARVIS programot.**
A fenti `npm run build` után a saját Python 3.11 környezetedben:

```powershell
python -m pip install PyQt6 PyQt6-WebEngine
python tools/qt_orb_lab.py
```

Ez egy különálló, visszavonható tesztablak: a böngészőbundle-t
`127.0.0.1` címen, szabad porton szolgálja ki. Nincs LAN-expozíció,
publikus webszerver, felhős hangszolgáltatás vagy produkciós JARVIS-kódimport.
A Windows Qt WebEngine WebGL-megjelenítést a **saját gépen kell ellenőrizni**.

A legördülő listából állapot választható; a csúszka szimulált
hangintenzitást állít. A `Test conversation cycle` gomb a
LISTENING → THINKING → SPEAKING → SUCCESS → IDLE folyamatot játssza le.
Az ablak saját UI-RAF mérőszámokat, a canvas méretét és a láthatóságot
mutatja. **Nem rögzít hangot**, nem tölt be semmilyen privát hangmintát,
nem indítja el a XTTS modellt és nem módosítja a JARVIS beállításait.

## C. Tesztek

```sh
npm test
python -m unittest discover -s tests -p "test_qt_bridge_contract.py" -v
python -m py_compile tools/qt_bridge_contract.py tools/qt_orb_lab.py
npm run build
```

A két független helyi kiszolgáló futtatásával
`npm run smoke` és `npm run benchmark` Playwright Chrome-teszt is
végrehajtható (CI-ben automatizált).

Az utóbbi két oldalt **ugyanabban a headless Chromium-környezetben**
vizsgálja: a régi Three.js háttér és az új Orb UI-képkocka közét,
p95 késleltetését, főszál-terhelését és JS heapméretét. Az eredmény
`perf-results/compare.json`, továbbá screenshotok és logok.

**Korlát:** Chrome UI RAF nem azonos a Three.js render FPS-sel.
GitHub CI esetén SwiftShader szoftveres GPU fut, így a relatív
eredmény sem tekinthető Windows Qt WebEngine teljesítményigazolásnak.

## D. Windows célgépes ellenőrzőlista

- [ ] Qt ablak elindul; canvas látható, nem csak CSS fallback
- [ ] A hétszintű JARVIS állapotválasztó helyes vizuális hatást ad
- [ ] A 0–100%-os hangszint a SPEAKING/LISTENING animációját módosítja
- [ ] 5 perc után nincs WebGL-kontextusvesztés vagy grafikai villogás
- [ ] `auto`, `balanced`, `performance` módok azonos gépen összevetve
- [ ] Egyidejű lokális XTTS beszédterhelés mellett is mért GPU/CPU/memória
- [ ] Ablak bezárásakor a helyi HTTP port felszabadul
- [ ] Régi JARVIS háttér és az összes produkciós felület változatlan

**Mérési feltétel:** felbontás, Windows-verzió, GPU típusa, driver,
Qt/PyQt verzió, Python-verzió és a kiválasztott mód dokumentálása.

## E. Biztonság, visszaállás és licencek

- A Qt bridge kizárólag előre meghatározott JARVIS-állapotot és
  0–1 közé korlátozott hangerőszintet fogad.
- A teszt nem továbbít semmilyen privát adatot vagy hangot.
- A csomag harmadik féltől származó MIT-függőség; az eredeti szerzői
  attribúció és szükséges licencek későbbi terjesztéskor megőrzendők.
- A `node_modules`, `dist` és `perf-results` nem kerülnek Gitbe.
- A visszaállítás a tesztablak bezárásával és a külön kísérleti
  mappa törlésével lehetséges; semmi nem kerül az aktív JARVIS felületbe.
- A PR draft marad; produkciós bekapcsolás és merge külön jóváhagyást igényel.
