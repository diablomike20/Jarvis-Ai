# JARVIS — egy telepítő, három beépített kreatív motor

## Mit kapsz?

A telepítő egyetlen `BrahmaEvo_Setup.exe` fájl, amely a JARVIS-t és
a három szerkesztőmotor **MCP/CLI futtatókörnyezetét** tartalmazza:

- PhotoCraft — képszerkesztő motor, PSD és képexport
- LightCraft — RAW-képek, fotófeldolgozás és export
- FilmCraft — videó-, hang- és idővonal-szerkesztő motor

**A kész JARVIS használatához nem kell külön PhotoCraftot, LightCraftot
vagy FilmCraftot telepíteni**, és nincs szükség Rust/Cargo/Python
telepítésére a célgépen. A szükséges programok a JARVIS telepítési
mappájába kerülnek, automatikusan felismeri őket.

Ez első lépésben *motorintegráció*: a három teljes eredeti grafikus
alkalmazásablak nincs átültetve a JARVIS saját felületére.
A műveleteket magyar utasításokkal és MCP-n keresztül tudja végrehajtani.

## Telepítő elkészítése egyszer, a saját Windows-gépeden

Az előállításhoz Windows x64, Git, Rust/Cargo, Python 3.11 és a
Rust fordításhoz megfelelő MSVC Build Tools szükséges.
A JARVIS repó gyökeréből futtasd:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_all.ps1
```

A script automatikusan:

1. beszerzi a három fork rögzített forráskód-verzióját;
2. lefordítja a három Rust CLI-motort;
3. telepíti a JARVIS Python build-függőségeit a helyi `.venv` környezetbe;
4. a PhotoCraft, LightCraft és FilmCraft CLI-fájlokat a JARVIS
   PyInstaller-csomagjába helyezi a szükséges DLL-ekkel;
5. létrehozza az **egyetlen telepítőfájlt** itt:
   `dist\BrahmaEvo_Setup.exe`.

A telepítőből feltelepített JARVIS-hoz nem kell forrásokat klónozni
vagy külön szerkesztőprogramokat letölteni.

A build a fordító környezetben internetet használhat. A programok
MCP-eszközeinek egy része offline is működik; más JARVIS funkciók,
például az OpenRouter vagy az Edge TTS, külön internetet igényelhetnek.

## Beépített motorok helye a telepített programon belül

```text
BrahmaEvo/
  BrahmaEvo.exe
  _internal/
    editor_engines/
      photocraft/photocraft-cli.exe
      lightcraft/lightcraft-cli.exe
      filmcraft/filmcraft-cli.exe
    integrations/sources/
      photocraft/manifest.json
      lightcraft/manifest.json
      filmcraft/manifest.json
```

A `creative_studio._binary_path()` először ezeket keresi.
A `source_plugins` manifestjei az eredeti programokhoz kapcsolják
a JARVIS funkcióit. A szerkesztőprogramokat nem kell külön elindítani.

## Használati próba

Telepítés után, a JARVIS szöveges vagy mikrofonos bemenetén:

- „JARVIS, mutasd a source pluginokat!”
- „JARVIS, PhotoCraft, milyen parancsaid vannak?”
- „JARVIS, LightCraft, milyen képkorrekciós eszközök vannak?”
- „JARVIS, FilmCraft, mutasd a videó idővonalának parancsait!”

A módosításokat a JARVIS saját jóváhagyási felülete védi.

## Jelenlegi fejlesztési állapot

A csomagolási script és a telepítő integrációja elkészült a
`feature/one-installer-creative-suite` fejlesztői ágon.

**A tényleges Windows x64 buildet és a telepítőn belüli három CLI
valós működését még ellenőrizni kell.** A sikeres forráskódtesztek
nem helyettesítik a három Rust CLI lefordítását, futtatását és egy
valódi fotó/video exportját.

A külön grafikus PhotoCraft, LightCraft és FilmCraft felületeket
nem csomagoljuk; a JARVIS saját egységes Creative Studio felülete
külön fejlesztési feladat.
