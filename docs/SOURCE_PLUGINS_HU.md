# JARVIS Source Plugin Framework

A JARVIS **forrásprojekt-bővítési rendszere** nem előre meghatározott
kategóriákhoz kötött. Ha adsz egy GitHub-tárolót vagy egy lokális
projektet, annak képességeit egy *integrációs adapter* segítségével
beépíthetjük a JARVIS-ba. A felhasználó ugyanabban az alkalmazásban
elérheti a funkciókat és magyarul utasíthatja a JARVIS-t.

**Az első három beépített source plugin:** PhotoCraft, LightCraft és
FilmCraft. Az eredeti Rust-motorokat használják, nem másolt vagy újraírt
helyettesítőket.

## Hogyan csatlakoztatható egy tetszőleges source?

A source-t **először át kell vizsgálni** (licenc, futtatás, API,
jogosultságok). Az integrációtól függően:

1. **MCP-kompatibilis program**: megadod a lokális CLI-fájl helyét.
   A JARVIS közvetlenül tudja lekérdezni a valódi MCP-eszközöket,
   és képes végrehajtani őket a saját engedélyezési felületén keresztül.
2. **Python library**: kis, ellenőrzött adaptert kell írni, amely
   a kívánt függvényeket egy MCP/CLI-szolgáltatásként elérhetővé teszi.
3. **Rust, C++, Java vagy más natív projekt**: a projekt meglévő API-ja
   köré lokális szervizt, MCP-adaptert vagy külön natív kötést kell készíteni.
4. **Csak grafikus felülete van**: célzott GUI-automatizálás lehetséges,
   de a megbízható teljes funkcionalitáshoz API/belső parancsréteg kell.

**Nem igaz**, hogy bármelyik nyilvános GitHub URL automatikusan,
kockázat és adapter nélkül, teljes funkcionalitással beépíthető.
A JARVIS ezért nem klónoz, telepít, fordít vagy futtat ismeretlen
forráskódot egy puszta szöveges utasítás hatására.

## Példa: új MCP source hozzáadása

Hozz létre egy fájlt itt:

\`integrations/sources/my-project/manifest.json\`

\`\`\`json
{
  "schema_version": 1,
  "id": "my-project",
  "name": "My Project",
  "source_url": "https://github.com/OWNER/REPO",
  "adapter": "mcp_stdio",
  "enabled": true,
  "executable_env": "JARVIS_MY_PROJECT_CLI",
  "args": ["mcp"],
  "capabilities": ["saját modulom funkcionalitása"]
}
\`\`\`

A \`my-project\` mappanévnek és az \`id\` mezőnek egyeznie kell.
A \`schema_version\` mező jövőbeli verziózásra szolgál. Az
\`enabled: true\` beállítás előtt az exe és a source biztonságát
ellenőrizni kell. Az MCP-programot csak akkor indítja el a JARVIS,
ha konkrét MCP-műveletet kérsz; puszta betöltéskor nem.

Windows PowerShell példa a telepített szerver megadására:

\`\`\`powershell
$env:JARVIS_MY_PROJECT_CLI = "C:\Tools\MyProject\myproject-cli.exe"
python main.py
\`\`\`

Egy másik repo integrációja **újrafordítás nélkül** (csak manifest +
helyi CLI) elkészülhet, *ha* támogatja az MCP stdio protokollt.

## JARVIS parancsok

- „JARVIS, mutasd a source pluginokat!”
- „JARVIS, My Project, milyen funkcióid vannak?”
- „JARVIS, My Project, hajtsd végre ezt a műveletet!”

A központi eszköz: \`source_plugins\`.

| Művelet | Funkció |
|---|---|
| \`list\` | Bejegyzett forrásprojektek, adapterek, státusz |
| \`status\` | Telepítés és futás ellenőrzése |
| \`discover\` | Valós eszköznevek, leírások és sémák lekérdezése |
| \`inspect\` | Egy MCP eszköz kérése |
| \`execute\` | Művelet végrehajtása, HUD megerősítéssel |
| \`batch\` | 1–8 művelet egymás után, közös jóváhagyással |

Az ismert Creative Studio motorokhoz a meglévő \`creative_studio\`
adapter közvetít, és ott a kipróbált, szűk olvasási műveletek közvetlenek.
**Ismeretlen új source esetén minden MCP tools/call felhasználói
jóváhagyást igényel** — még a látszólag olvasó eszközök is.

## Biztonság és határok

- Az új source-t a JARVIS **nem tölti le automatikusan** GitHubról.
- Külső kódot kizárólag a gépen már meglévő, kifejezetten beállított
  futtatható programként indít.
- Nem használ \`shell=True\` indítást, az AI nem adhat saját végrehajtandó
  shell-parancsot a manifestből.
- Egy MCP tool neve csak akkor hívható, ha a szerver valóban közzéteszi.
- A műveletekhez a \`core.confirm\` megbízható képernyős
  CONFIRM/CANCEL felülete szükséges, nem az AI által generált \`confirmed\`.
- A megerősítés **nem tesz biztonságossá egy rosszindulatú binárist**:
  a CLI indításkor önállóan is hozzáférhet a felhasználói fájlokhoz.
  Ismeretlen source futtatásához külön sandbox/virtuális gép célszerű.
- A jelenlegi általános MCP-adapter **headless** vezérlést kínál, nem
  integrálja automatikusan a forrásprogram grafikus felületét.
- Új projekt teljes funkcióköre attól függ, mennyit tesz elérhetővé
  az MCP/API/CLI. A hiányzó funkciókhoz célzott Rust/Python/egyéb
  adapter-fejlesztés szükséges.

## Fejlesztői próba

\`\`\`powershell
python -m pip install pytest requests numpy
python -m pytest -q tests/test_source_plugins.py tests/test_creative_studio.py
\`\`\`

A tesztek nem indítanak külső exe-t és nem tesztelik az ismeretlen
source valódi szerkesztési képességeit. Azokat külön kell ellenőrizni
a telepített programmal és mintaadatokkal.
