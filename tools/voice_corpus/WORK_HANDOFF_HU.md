# JARVIS HU – átadás a Work hangforráskutató kollégától

**Átadás helye:** privát Windows könyvtár, NEM GitHub. Csak ténylegesen ellenőrzött részletekről készüljön rekord; a mezők nem tölthetők ki találgatással.

## Feladatmegosztás

**Work:** a három megadott filmoldal/engedélyezett egyéb források megnyitása; a valós magyar JARVIS-megszólalások időpontjának, forrásának, elérhető hangsávjának, tényleges beszélőjének ellenőrzése. Átadás esetén megadni eredeti video/audio helyi fájlt és a jelenetek időpontját. Más szereplő, amatőr szinkron, Vízió és nem Kárpáti Levente JARVIS-hangját a filmes JARVIS-tanítóanyagból kizárni. Ne állítson kész letöltést puszta weboldallink alapján.

**Voice Lab:** hangfájl-elővizsgálat, tisztaság és klippontosság, helyi referenciák, F5/XTTS A/B kiértékelés. Az eredeti JARVIS/Claude `main`/`master` módosítása nélkül.

## Átadási jegyzék: azonosítók és mezők

```json
{
  "version": 1,
  "source_id": "ironman3_hu",
  "title": "Vasember 3. (2013)",
  "origin_url": "https://hdmozi.hu/movies/vasember-3/",
  "local_source_path": null,
  "source_sha256": null,
  "language_verified": false,
  "actor_verified": false,
  "audio_stream_ordinal": null,
  "channel_layout": null,
  "rights_checked": true,
  "scenes": []
}
```

**Figyelem:** `rights_checked=true` csak a felhasználó által jelzett, erre a felhasználásra szóló jogalap és a konkrét fájl eredete alapján értelmezhető. `local_source_path=null` addig marad, amíg nincs tényleges helyi médiafájl. `language_verified=false` és `actor_verified=false` addig marad, amíg nincs meghallgatással ellenőrzött nyelv és beszélő.

Ha megvan a ténylegesen ellenőrzött dialógussáv, a Voice Lab `metadata/ironman3_hu.segments.csv` formátumban fogadja a sorokat:

```csv
start,end,text,style,actor_verified,rights_checked,notes
```

Az üres CSV fejléc szándékos; **nem tartalmaz kitalált mondatot vagy kitalált időpontot**. A `prepare_corpus.py cut` csak `yes/yes` ellenőrzött, 1–30 másodperces sorokkal fut, és utólag továbbra is kézi hangminőség-ellenőrzés szükséges.

## Minimális kész átvétel

- Legalább egy jogszerűen rendelkezésre álló, ténylegesen meghallgatott magyar JARVIS-hang.
- Egy 5–15 másodperces tiszta referencia WAV (beszélőazonosság ellenőrizve).
- Pontos magyar UTF-8 referenciaátirat TXT-ben.
- Minden eredeti forrás SHA-256, pontos megnevezés, az audio sáv száma és a kinyerési mód.
- A WAV-ok és a jövőbeli modellfájlok kizárólag a privát helyi adatmappában.

A késznek tekintés feltétele **nem** a linkek száma: legalább egy valódi, ellenőrzött, helyben hozzáférhető hangreferencia.
