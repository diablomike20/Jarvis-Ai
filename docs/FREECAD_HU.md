# JARVIS FreeCAD — natív 3D CAD source-plugin

A FreeCAD a PhotoCraft, LightCraft és FilmCraft mellé **negyedik
kreatív source-pluginként** csatlakozik a JARVIS-hoz. A modell **valódi
FreeCAD-motort** használ: a `FreeCADCmd` futtatja a FreeCAD Python API-ján
alapuló szerkesztő scriptet, külön FreeCAD GUI-ablak nélkül.

A JARVIS a magyar parancsból eszköztervet állít össze, majd az eredeti
FreeCAD-program végzi a geometriaműveletet. A műveletindítás előtt a
JARVIS saját megerősítő felületén jóváhagyást kér.

## Jelenleg megvalósított CAD-műveletek

| Tool | Képesség |
|---|---|
| `list_projects` | A JARVIS helyi FreeCAD-projektjei |
| `new_project` | Üres natív `.FCStd` projekt létrehozása |
| `import_fcstd` | Létező `.FCStd` dokumentum behozatala |
| `inspect_project` | Valódi geometria, méret, térfogat, objektumlista |
| `import_geometry` | STEP, IGES, BREP, STL vagy OBJ geometria importálása meglévő projektbe |
| `add_primitive` | Parametrikus doboz, henger, gömb, kúp |
| `sketch_pad` | PartDesign Body + Sketcher téglalapvázlat + Pad |
| `boolean` | Egyesítés, kivonás, közös térfogat |
| `transform` | 3D pozíció és Z tengely körüli forgatás |
| `remove_object` | Objektum törlése |
| `export` | STEP, IGES, BREP, STL vagy OBJ export |

A tényleges CAD-eszközök az `actions/freecad_plugin.py` fájlban
vannak meghirdetve. Az AI nem futtathat szabadon generált Python-kódot
a FreeCAD alatt: csak a megengedett, ellenőrzött paramétereket adhatja
át az `integrations/sources/freecad/freecad_worker.py` programnak.

**Ez az első FreeCAD-integrációs réteg**, nem FreeCAD teljes GUI-jának
beágyazása. A GUI-kötött workbenchek, rajznézetek, összes FreeCAD
munkaterület/funkció teljes elérése további integrációt igényel.

## Magyar JARVIS-példaparancsok

- „JARVIS, FreeCAD, milyen funkcióid vannak?”
- „JARVIS, FreeCAD, készíts új projektet `motorhaz` néven.”
- „JARVIS, FreeCAD, tegyél a `motorhaz` projektbe 60 × 40 × 25 mm-es dobozt `Base` néven.”
- „JARVIS, FreeCAD, hozz létre 20 mm sugarú, 45 mm magas hengert.”
- „JARVIS, FreeCAD, vonj ki egy testet a másikból.”
- „JARVIS, FreeCAD, mutasd az objektumok geometriai adatait.”
- „JARVIS, FreeCAD, exportáld a modellt STEP formátumba.”

Hiányzó projekt- vagy objektumazonosítók esetén a JARVIS-nak vissza
kell kérdeznie, és nem találhat ki fájlokat vagy geometriai adatokat.

## Követelmények fejlesztéskor

A JARVIS-hoz most **nem készül telepítő**. A futtatáshoz egy helyi
FreeCAD-telepítés és annak `FreeCADCmd.exe` programja szükséges.
Ha elérhető a rendszer PATH-jában vagy a szokásos Windows
Program Files/FreeCAD… könyvtárban, az adapter megkeresi.

Ha más helyen van, PowerShellben:

```powershell
$env:JARVIS_FREECAD_CMD = "C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe"
python main.py
```

A példában szereplő útvonalat az *aktuálisan telepített FreeCAD*
helyéhez kell igazítani. A JARVIS nem telepít FreeCAD-et a háttérben.

A szerkesztett dokumentumok helye:

```text
%LOCALAPPDATA%\BrahmaAI\cad_studio\
  motorhaz.FCStd
  exports\
    model.step
    model.stl
```

A FreeCAD motor a parancsok között az `.FCStd` projektfájlból
tölti vissza a geometriát. Ez megőrzi a paraméteres szerkesztési
állapotot, bár nem egyetlen folyamatos FreeCAD GUI-munkamenet.

## Biztonság

- A JARVIS csak a szűken meghirdetett CAD-parancsokat futtatja.
- Projekt- és objektumneveket ellenőrzi, nem engedi a `../`
  útvonalbejárást vagy a tetszőleges kódfuttatást.
- Import csak kézzel megadott, valóban létező `.FCStd` fájlból,
  legfeljebb 100 MB méretben.
- Az exportok csak a JARVIS CAD export-mappájába kerülnek.
- Fájlfelülíráskor külön `overwrite=true` opció szükséges.
- A végrehajtás nem `shell=True` módban történik; a FreeCADCmd
  környezetében statikus, felülvizsgált Python-szkript fut.
- Az MCP/source adapteren keresztüli tools/call felhasználói
  **HUD-jóváhagyást** igényel.

## Tesztelés és korlátok

```powershell
python -m pytest -q tests/test_freecad_plugin.py
# Telepített FreeCADCmd esetén célgépes, izolált CAD-próba:
python scripts/verify_freecad.py
```

A GitHub CI szintaxis- és unit-teszteket futtat. Ezek a bemenetek,
fájlkezelés, jóváhagyás és indítás ellenőrzésére szolgálnak. A valódi
FreeCADCmd folyamat létrehozását, Sketcher/PartDesign Pad működését,
a STEP/STL exportot és a Windows futtatást **helyi FreeCAD-telepítéssel
külön ellenőrizni kell**. A projekt nem állítja, hogy ezek a GUI
nélküli műveletek minden FreeCAD-verzión tesztelten működnek.

A FreeCAD dokumentációja a `FreeCADCmd` headless Python futtatást
és a `Part` API-t is támogatja:

- https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md
- https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Python_scripting_tutorial.md
