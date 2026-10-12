# Magyar JARVIS filmes hangkorpusz – izolált előkészítés

**Állapot (2026-10-12):** eszközforrás elkészült a `prep/jarvis-hu-film-voice-corpus-20261012` ágon. **Nem futtatott Windows-teszt, nem letöltött filmes hanganyag, nem kész modell.** A stabil `main` és a Claude repository nincs módosítva.

## Hatókör

Ez az eszköz **nem** korábbi hangbranchekből származik, nem integrál TTS-modellt a JARVIS-ba és nem tölt le védett filmeket. A felhasználó által engedélyezetten rendelkezésre bocsátott **helyi hang- vagy videóállományokból** készít privát, ellenőrzött referenciakorpuszokat.

Minden eredeti fájl, dialógussáv, részlet, átírás, referencia, modell és finomhangolt súly **a GitHub repositoryn kívül** maradjon. A hang személyes és licencelt adat. Ne töltsd fel GitHubra vagy publikus AI-szolgáltatásba.

## Megerősített filmes források

| ID | Produkció | A JARVIS magyar hangja | Megjegyzés |
|---|---|---|---|
| `ironman3_hu` | Vasember 3. (2013) | Kárpáti Levente | 1. prioritás; magyar Blu-ray DD 5.1 igazolt |
| `avengers2012_hu` | Bosszúállók (2012) | Kárpáti Levente | 2. prioritás |
| `ultron2015_hu` | Bosszúállók: Ultron kora (2015) | Kárpáti Levente | 3. prioritás; Vízió **külön** megjelölendő |
| `marecord_01` | MaRecord színészhangminta (feltöltött MP3) | Kárpáti Levente (felhasználói azonosítás) | Tiszta hangazonosság-referencia, ellenőrzés még szükséges |

Ellenőrzött nyilvános szereposztási / kiadási források:

- https://iszdb.hu/?audio=12772
- https://iszdb.hu/?audio=11448
- https://iszdb.hu/?lap=munkassag&szemely=7940
- https://www.mediamarkt.hu/hu/product/_vasember-3-blu-ray-1491328.html
- https://www.rocky.hu/dvd/fantasy/bosszuallok-ultron-kora

**Nem tanítóforrás:** a korábbi Vasember 1–2 filmek magyar JARVIS-hangja más színész, ezért a célbeszélő adatkészletéből kizárandó.

## Futtatási feltételek

- Windows 10/11 x64
- Python 3.11 vagy újabb
- FFmpeg és FFprobe telepítve, a `PATH` változóban
- helyi, jogszerűen hozzáférhető forrásmédia (MP3, WAV, MKV, MP4 stb.)
- elegendő lemezterület: egy teljes többórás PCM sáv több GB lehet

Az előkészítéshez **nincs szükség fizetős API-ra, XTTS-re, F5-TTS-re, OpenRouterre vagy Claude-ra**.

## Windows PowerShell – használat

A JARVIS repository gyökerében futtatva:

```powershell
$ws = Join-Path $env:LOCALAPPDATA "JarvisAI\voice_private"
$tool = "tools/voice_corpus/prepare_corpus.py"
python $tool --workspace $ws init

# Már rendelkezésre álló MaRecord MP3 azonosítása; semmit nem tölt fel.
python $tool --workspace $ws register --id marecord_01 --input "C:\hangmintak\karpati_levente.mp3"

# Helyi magyar filmfájl hangsávjainak megvizsgálása.
python $tool --workspace $ws register --id ironman3_hu --input "D:\media\vasember_3_magyar.mkv"

# Ha a magyar DD 5.1 az első HANGSÁV, a center csatorna:
python $tool --workspace $ws extract --id ironman3_hu --input "D:\media\vasember_3_magyar.mkv" --audio-stream 0 --mode center

# FONTOS: --audio-stream az AUDIO streams 0-alapú sorszáma, nem a videóé.
# Másik audio stream vagy sztereó fájl esetén módosítsd a paramétereket:
# ... --audio-stream 1 --mode mono

# Emberileg ellenőrzendő időpontok CSV-sablonja.
python $tool --workspace $ws template --id ironman3_hu

# A CSV sorait kézzel feltöltve: start,end,text,style,actor_verified,rights_checked,notes
# A 'yes' mezőket kizárólag tényleges ellenőrzés után lehet kitölteni.

python $tool --workspace $ws cut --id ironman3_hu --input "$ws\dialogue\ironman3_hu_center.wav" --csv "$ws\metadata\ironman3_hu.segments.csv"
```

A sablon szándékosan **üres**: se filmidézetet, se időbélyeget, se színészazonosságot nem talál ki. A `cut` csak az `actor_verified=yes`, `rights_checked=yes` és szövegesen átiratozott, 1–30 másodperces jeleneteket engedi. Kimenet:

- `dialogue/*.wav`: kivont teljes hangsáv, 48 kHz/24 bit, eredeti másolat változatlan;
- `segments/*.wav`: célzott 24 kHz/16 bit mono beszédrészletek;
- `metadata/*.source.json`: eredet, SHA-256, codec és hangcsatornák;
- `metadata/*.manifest.jsonl`: átirat, stílus, kivágási időpont, ellenőrzési jelzők és SHA-256.

## Minőségbiztosítás

1. **Elsőként a nyers/center sávot hallgasd meg.** A center csatorna gyakran a dialógus nagy részét tartalmazza, de zene és effekt is lehet rajta. Nem garantált tiszta izolált beszéd.
2. Csak Kárpáti Levente **JARVIS-ként** előadott beszédét használjuk az első karaktermodellhez. `Ultron kora` esetén Vízió megszólalásait ne keverjük a JARVIS-címkével.
3. Egyenletes hangszint, recsegésmentesség, egy beszélő, nincs átfedés. Túl erős zajszűrés ellenjavallt.
4. A teljes magyar átirat legyen pontos, helyes írásjellel. A filmes zene, beszédleválasztás maradványa rontja a modell minőségét.
5. `neutral`, `confirmation`, `analytical`, `warning`, `urgent`, `ironic` jelzők csak tényleges megfigyelésből származhatnak.
6. A tanító-, validációs és ellenőrző részletek között ne legyen ugyanazon take-ből származó duplikáció.
7. A már előkészített WAV-okat meghallgatással újra ellenőrizni kell; a manifest kezdetben `pending_listening_review` állapotú.
8. Csak magáncélú, engedélyezett feldolgozás; nincs automatikus filmletöltés, DRM-megkerülés vagy ismeretlen eredetű fájl átvétele.

## Következő mérföldkövek, miután a filmhang lokálisan rendelkezésre áll

1. Korpuszmérés: beszédperc, zajminőség, stílusmegoszlás, duplikátumok.
2. Referencia A/B tesztek F5-TTS Hungarian és XTTS-v2 motorral, magyar tesztmondatokon.
3. Emberi hanghűség-értékelés; finomhangolás csak indokolt esetben.
4. Hangkezelő integrációja a stabil, később véglegesített Claude/JARVIS runtime-ba.
5. `Original Voice Only` esetén minden TTS hiba **szöveges fallback**, nem más beszélő hangja.
6. Valódi Windows 10/11 end-to-end teszt, a **meglévő eredeti HUD** hangállapotával.

## Határ

A `main` stabil ág változatlan. Ez a branch előkészítő eszköz, nem JARVIS-installer és nem kész hangmodell. A feldolgozást a jelenlegi távoli futtatókörnyezet hibája miatt még **nem sikerült lefuttatni** a felhasználó MP3-fájlján.
