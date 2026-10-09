# JARVIS AI — izolált 3D Orb tesztlabor

Ez a könyvtár kizárólag kísérleti React + Three.js prototípus. **Nem módosítja**
a meglévő assets/web_background/index.html fájlt, a PyQt6 felületet,
a mikrofonszolgáltatást vagy a magyar XTTS-v2 ágat.

## Indítás
\`\`\`sh
cd experiments/jarvis-orb-web-demo
npm install
npm run dev
\`\`\`
A Vite a http://127.0.0.1:5173/ oldalt nyitja meg.
A komponens: jarvis-ai-web-animation@0.1.2 (MIT, cyber1443).

## Hangállapotok
IDLE=idle; LISTENING=custom orb; THINKING=thinking; SPEAKING=custom,
audio-intenzitással; SUCCESS=success; ERROR=alert; OFFLINE=custom tompított.

Kipróbálható a böngésző konzoljából:
\`\`\`js
setBrahmaState('SPEAKING')
setAudioLevel(0.75)
\`\`\`
Csak vizuális szimuláció, valós hangot vagy privát hangmintát nem kér és nem
küld semmilyen szolgáltatásnak. Külső postMessage csak saját originről érkezhet.

## Teszt és teljesítmény
\`npm test\`: tiszta JavaScript állapot- és hangerőhíd-tesztek.
\`npm run build\`: valódi npm komponensből Vite-bundle.
\`npm run smoke\`: Playwright ellenőrzi az állapotgombokat és a Qt-kompatibilis
JavaScript hidat, valamint ment screenshotot és JSON-t a perf-results mappába.
A teszthez futnia kell a Vite szervernek. Az opcionális ORB_LEGACY_URL az
eredeti Three.js háttérről is készít képernyőképet külön helyi webszerverről.

**Metrika-korlát:** a lapon mért requestAnimationFrame FPS a böngésző UI
üteme, nem a tényleges orb-render FPS vagy GPU-idő. A CI szoftveres Chromium
nem azonos a JARVIS Windows Qt WebEngine célgépével. A két látvány ugyanazon
gép/böngésző alatt összevethető, végleges mérés csak a Windows gépen.

## Biztonság
Nincs XtTS modelltelepítés, mikrofonjogosultság, GitHub hangminta-feltöltés,
main merge vagy automatikus meglévő animációcsere.
Forrás / licenc: https://github.com/cyber1443/jarvis-ai-orb-web-animation
