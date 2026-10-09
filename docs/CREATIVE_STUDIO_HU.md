# JARVIS Creative Studio — három teljes szerkesztőmotorhoz kapcsolható

**Cél:** ne három külön program indítója legyen a JARVIS, hanem egyetlen
magyarul vezérelhető kreatív asszisztens, amely az **eredeti Rust-motorok**
tényleges parancsaival dolgozik. Az integráció a PhotoCraft, LightCraft,
FilmCraft saját MCP-protokollján keresztül történik, fej nélküli (headless)
szerkesztőfolyamattal. A külön alkalmazásablak nem szükséges.

**Jelenlegi állapot:** első működő vezérlőréteg és megerősítéses műveleti
végrehajtás. A három szerkesztő natív grafikus felülete még nincs beépítve
a JARVIS ablakába. A tényleges kép-/videófeldolgozás az editor-CLI
telepítését és célgépes tesztelését igényli.

## Milyen képességeket lehet elérni?

| PhotoCraft | LightCraft | FilmCraft |
|---|---|---|
| PSD, rétegek, maszkok | RAW, fotókatalogizálás | Videó- és hangimport |
| Vektorgrafika, szöveg | Expozíció, fehéregyensúly | Többsávos idővonal |
| Ecsetek, kijelölések | Görbék, színkeverő | Klip- és hangszerkesztés |
| Szűrők, effektek | Presetek, maszkolás | Színkorrekció, LUT-ok |
| Képkivágás, transzformálás | Értékelés, metaadatok | Videoeffektek, animáció |
| Export és kötegelt műveletek | Kötegelt fotóexport | Felirat, hangmix, export |

A táblázat a három *motor* funkcióterületeit mutatja. Egy adott művelet
akkor végezhető el, ha a telepített program MCP-parancsként valóban
közzéteszi, és annak paraméterei megfelelően megadhatók. A JARVIS
\`discover\` művelete **a futó szerver valós eszközlistáját** adja vissza.

## Windows telepítés

Rust és Cargo szükséges a forrásból építéshez (ha nincs kész kompatibilis
CLI-kiadás). A három GitHub repót ugyanabba a szülőkönyvtárba klónozd:

\`\`\`powershell
git clone https://github.com/diablomike20/photocraft.git
git clone https://github.com/diablomike20/lightcraft.git
git clone https://github.com/diablomike20/filmcraft.git

cd photocraft
cargo build --release -p photocraft-cli
cd ..\lightcraft
cargo build --release -p lightcraft-cli
cd ..\filmcraft
cargo build --release -p filmcraft-cli
\`\`\`

Ha a szerkesztők **a JARVIS könyvtárával egy szinten** találhatók, a
JARVIS automatikusan keresi a CLI-fájlokat a
\`<app>/target/release/<app>-cli.exe\` útvonalon.

Bármelyik szerkesztő másik helyről is használható:

\`\`\`powershell
$env:JARVIS_PHOTOCRAFT_CLI = "D:\Apps\photocraft-cli.exe"
$env:JARVIS_LIGHTCRAFT_CLI = "D:\Apps\lightcraft-cli.exe"
$env:JARVIS_FILMCRAFT_CLI = "D:\Apps\filmcraft-cli.exe"
python main.py
\`\`\`

Ezek a beállítások csak a parancs futtatására indított környezetben
érvényesek. A JARVIS nem telepíti és nem fordítja le magától a Rust motorokat.

## A JARVIS működése

1. Hang- vagy szöveges utasítás: „JARVIS, LightCraft, módosítsd az expozíciót.”
2. A JARVIS lekérdezi az eredeti LightCraft MCP-szervertől az elérhető eszközöket.
3. Az aktuális AI modell a **regisztrált** eszközökből készít 1–8 lépéses tervet.
4. Az olvasó/ellenőrző műveletek azonnal futnak.
5. Módosítás esetén a JARVIS saját, megbízható **CONFIRM / CANCEL**
   felületén kér jóváhagyást. Modell által beküldött \`confirmed: true\`
   nem kerüli meg a megerősítést.
6. Jóváhagyás esetén a helyi Rust-szerkesztő végrehajtja a feladatot.

Példaparancsok:

- „JARVIS, sorold fel a PhotoCraft rétegműveleteit!”
- „JARVIS, milyen LightCraft presetek és fotóbeállítások érhetők el?”
- „JARVIS, FilmCraft, mutasd a videó idővonalát.”
- „JARVIS, szerkeszd a PSD fájlt a PhotoCrafttal!”
- „JARVIS, LightCraft, állítsd az expozíciót 0,5-re!”
- „JARVIS, FilmCraft, importálj videót és alkalmazz színkorrekciót!”

**Fontos:** ha egy parancshoz fájlútvonal, azonosító vagy kontextus kell,
a JARVIS-nak ezt tisztáznia kell — nem találhat ki fájlneveket.

## Biztonság

- Csak konfigurált vagy felismerhető **CLI-fájlokat** indítunk,
  \`subprocess.Popen(argv)\` formában, \`shell=True\` nélkül.
- A PhotoCraft motor olvasási és írási jogosultságát a saját MCP
  \`--automation-read-root\` és \`--automation-write-root\` opciói
  a helyi JARVIS Creative Studio mappához kötik:
  \`%LOCALAPPDATA%\BrahmaAI\creative_studio\`.
- LightCraft és FilmCraft saját fájlelérésére **nem** állítható ilyen
  általános korlát ebből a modulból; ezért minden szerkesztő művelethez
  felhasználói HUD-jóváhagyás kell.
- A szerkesztők projektállapotot a futó headless MCP-munkamenetben
  őrizhetnek, amíg a JARVIS fut; mentetlen módosítások a processz
  leállásával elveszhetnek.
- A \`tools/list\` névellenőrzés és a modell eszközválasztása
  **nem jogosultsági határ**; a tényleges jóváhagyást a
  \`core.confirm\` biztosítja.
- A videó/fotó export erőforrás-igényes; a JARVIS nem garantálja az
  összes codec vagy hardver támogatását.
- A projektek forráskódját nem másoltuk a JARVIS-ba. Az eredeti
  licenceket, védjegyeket és az alap JARVIS-fork licenceit
  külön ellenőrizni kell minden nyilvános terjesztés előtt.

## Fejlesztői felület

A JARVIS \`creative_studio\` eszköz \`app\` paramétere:
\`photocraft\`, \`lightcraft\`, \`filmcraft\`, vagy katalógushoz \`all\`.

Műveletek: \`catalogue\`, \`status\`, \`discover\`, \`inspect\`,
\`execute\`, \`batch\`.

\`\`\`python
from actions.creative_studio import creative_studio

print(creative_studio({"app":"all", "operation":"catalogue"}))
print(creative_studio({"app":"filmcraft", "operation":"status"}))
print(creative_studio({
    "app":"lightcraft", "operation":"discover", "filter":"develop"
}))
\`\`\`

## Ellenőrzés

\`\`\`powershell
python -m pip install pytest numpy requests
python -m pytest -q tests/test_creative_studio.py
\`\`\`

A tesztek az eszközfelderítést, hibakezelést, engedélyezési kaput,
parancsterveket és konfigurációt fedik le. A tényleges képszerkesztést,
RAW-exportot és videó-renderelést külön kell Windows-on, telepített
Rust-motorokkal integrációsan ellenőrizni.

A teljes réteg-/maszk-/idővonal-szerkesztő JARVIS-ba ágyazott
**grafikus felülete** külön fejlesztési szakasz, nem része ennek
az első motorintegrációnak.
