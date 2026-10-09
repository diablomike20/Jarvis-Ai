# JARVIS — ellenőrzött önfejlesztés

A **Skill Forge** továbbra is készít új Python-funkciókat a felhasználó
által megfogalmazott igényből. Az új folyamatban azonban különválik a
**tervezet**, a **felhasználói jóváhagyás**, a **tesztelés** és az **aktiválás**.

## Új skill létrehozása

1. JARVIS felismeri a „készíts új skillt” vagy „build a skill” kérést.
2. Az AI előállítja az új Python-funkciót, manifestet és teszteseteket.
3. A Python-szintaxist *futtatás nélkül* ellenőrzi, hiba esetén legfeljebb
   két alkalommal új kódot generáltathat.
4. A fájl megjelenik a felhasználói `skill_reviews/<azonosító>/candidate.py`
   könyvtárban, változatlan forráskóddal és SHA-256 azonosítóval.
5. A JARVIS HUD megerősítést kér. A teljes fájl átnézhető a megadott
   elérési úton. A generált kód **nem futott, még tesztként sem**.
6. Ha a felhasználó elutasítja vagy a HUD hiányzik, **nem indul teszt,
   nem települ csomag, nem aktiválódik a modul**.
7. Jóváhagyás után a JARVIS ellenőrzi, hogy a fájl változatlan-e,
   a szükséges csomagok rendelkezésre állnak-e, majd subprocessben
   lefuttatja a generált teszteket.
8. Ha minden teszt sikeres, a modul `features/<név>/` alá kerül, és
   a Dynamic Tool Registry külön parancsként elérhetővé teszi.

A `core/skill_crucible.py` **sosem telepít automatikusan pip-csomagot**.
A hiányzó függőségek esetén tájékoztat, és a skill nem aktiválódik.

**Biztonsági megjegyzés:** a jóváhagyott kód tesztfuttatása Python
subprocessben történik, a JARVIS felhasználói jogosultságaival.
Ez **nem operációs rendszer szintű izoláció és nem megbízható malware
sandbox**. Csak ellenőrzött kódot szabad jóváhagyni. Valós
Windows Sandbox / AppContainer / VM elszigetelés még külön fejlesztés.

## Saját hibáinak javítása (Auto-Heal)

1. Hibajelentés alapján azonosítja a projekt *nem védett* Python-fájlját.
2. Az AI pontos cserét és rövid magyarázatot javasol.
3. Az új forráskódot memóriában szintaktikailag ellenőrzi, de nem írja ki.
4. A HUD jóváhagyást kér. A modell saját `confirmed` mezővel ezt
   nem tudja megkerülni.
5. Jóváhagyás után ismét ellenőrzi, hogy az eredeti fájl változatlan.
   Azután biztonsági másolatot készít, módosít és `py_compile` tesztet futtat.
6. Sikertelen fordításnál az eredetit visszaállítja. Sikeres javítás után
   az Auto-Heal meglévő rollback műveletével visszavonható a módosítás.

A JARVIS kritikus fájljai (`main.py`, `skill_forge.py`,
`skill_crucible.py`, `auto_heal_engine.py`, `confirm.py`,
`dynamic_registry.py`, stb.) **Auto-Heal célpontként védettek**.
A projekt gyökerén kívüli Python-fájlokat sem módosítja.

**A szintaxisellenőrzés nem működésbizonyítás**: a jóváhagyott hotfix
nem garantáltan javítja az eredeti hibát. A JARVIS tehát nem állíthatja,
hogy a hiba biztosan megszűnt, amíg célzott integrációs teszt nem készült.

## Skill visszavonása

A `DynamicToolRegistry.delete_skill` csak név szerint azonosított,
AI által létrehozott **önálló skillcsomagot** vonhat vissza. Nem törölheti
a teljes `features/` könyvtárat vagy annak natív Python-fájljait.
A visszavont modul a `skill_backups/` könyvtárba kerül megőrzésre,
és a többi skill tovább működik.

Ez a módosítás csak a `feature/controlled-self-evolution` fejlesztői
ágon van. Nem készült telepítő, és nem került be a JARVIS főágába.

## Automatikus tesztek

```powershell
python -m pytest -q tests/test_skill_forge.py tests/test_controlled_autoheal.py
```

A tesztcsomag ellenőrzi a jóváhagyás nélküli futtatás tiltását,
a megváltozott kód elutasítását, a hiányzó függőségeket, a
hibás teszteredmények elutasítását, a védett fájlokat és a skill
visszavonásának hatókörét.
