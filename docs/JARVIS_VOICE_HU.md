# Magyar, JARVIS-hangulatú beszéd – színészhang klónozása nélkül

Ez a változat a Microsoft magyar férfihangját használja a `edge-tts`
Python-csomagon keresztül:

- Hang: `hu-HU-TamasNeural`
- Beszédtempó: `-9%`
- Hangmagasság: `-8Hz`
- Hangerő: `+0%`

A lassabb, visszafogottabb előadás futurisztikus asszisztenshangulatot adhat.
**Ez NEM a Vasember-filmek szinkronszínészének hangklónja**, és nem
garantált a filmhanghoz való hasonlóság. Nem kell hozzá színész-hangminta,
mivel nem készül hangmásolat.

## Gyors hangpróba Windows alatt

Ugyanabban a Python-környezetben, amelyben a JARVIS fut:

```powershell
python -m pip install edge-tts
python -m edge_tts --voice hu-HU-TamasNeural --rate=-9% --pitch=-8Hz --text "Üdvözlöm, uram. A rendszerek készen állnak. Várom az utasításait." --write-media jarvis_hu_test.mp3
start jarvis_hu_test.mp3
```

A hálózati `edge-tts` szolgáltatás internetkapcsolatot igényel; nincs
külön Gemini-függőség vagy Gemini-kulcs. A szolgáltatás használatának
feltételei és elérhetősége változhatnak.

## Finomhangolás

A felhasználói `app_settings.json` fájlban állíthatók:

```json
{
  "tts_style": "jarvis_hu",
  "tts_voice": "hu-HU-TamasNeural",
  "tts_rate": "-9%",
  "tts_pitch": "-8Hz",
  "tts_volume": "+0%"
}
```

A `tts_style` lehet `jarvis_hu` (mérsékelten lassú/mély) vagy
`natural_hu` (semleges magyar beszéd). A `tts_rate` és a `tts_pitch`
külön is módosítható. A `tts_voice` megváltoztatásával más Microsoft
Neural hang választható, ha az elérhető.

## Offline működés

Ha a program „Offline Mode” módban fut, először a gépen telepített
Windows SAPI/OneCore hangot használja. Magyar hangot keres először,
de egyes Windows-telepítéseken nincs ilyen hang: ilyenkor a tartalék
angol férfihang szólalhat meg. A teljesen offline, természetes magyar
beszédhez külön helyi magyar TTS modellt kell integrálni.

## Hatókör

Ez a fejlesztés **beszédszintézis** (szöveg -> hang). A Gemini Live
eltávolítása utáni mikrofonos magyar beszédfelismerés és az azonnali
kétirányú beszélgetés külön fejlesztést igényel.
