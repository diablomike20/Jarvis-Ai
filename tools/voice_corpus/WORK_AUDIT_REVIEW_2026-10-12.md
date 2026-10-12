# 2026-10-12 Work HDMozi audit – minőségi átvétel

**Döntés: REJECTED_AS_TRAINING_DATA.** Kutatási segédletnek megtartható, de a jelenlegi hangkivágások nem kerülhetnek aktív JARVIS-hangmodell-tanításba. A színészazonosság és a beszéd minősége nincs meghallgatással igazolva.

## Ténylegesen kapott csomag

A felhasználó által feltöltött:
- `HDMozi-JARVIS-audit-20261012(1).zip`
- `ELLENORZES.md`
- `ellenorzott_jelenetek.csv`
- `forras_es_vagasok.json`
- `JARVIS_promo_01.wav`
- `JARVIS_promo_02.wav`
- `OLVASS_EL.md`

A dokumentált két WAV az 55.062 s hosszú Videa *Vasember 3 szinkronos promó* részlete:
- `JARVIS_promo_01.wav`: **1.36 másodperc**, promó 00:38.220–00:39.580;
- `JARVIS_promo_02.wav`: **0.88 másodperc**, promó 00:43.160–00:44.040;
- összesen **2.24 s**, sztereó 48 kHz, 16 bit PCM dekódolási/vágási kimenet (a metaadat alapján);
- eredeti promó URL: https://videa.hu/videok/film-animacio/vasember-3-szinkronos-promo-film-animacio-6RimasrrDVMbIYca
- a promó eredeti teljes hangja **nem** található meg a felhasználó által átadott dokumentumok között.

A `forras_es_vagasok.json` szerint a forrás nyelve gépi felismerés alapján magyar (0.991 körüli valószínűségi becslés), de a célszínész **nincs hallásos vagy független módon igazolva**. A promóban esetleg jelen lévő zene és filmhatások nincsenek eltávolítva.

## A jelenetlista valós státusza

A `ellenorzott_jelenetek.csv` 9 adatsora **8 JARVIS-jelenetjelölt és 1 Vízió-jelenetjelölt**. A `magyar_hang_ellenorizve`, `Karpati_hang_ellenorizve` és `HDMozi_valtozat_ellenorizve` mezők **MIND A KILENC SORBAN `Nem`**. Az időpontok angol nyelvű Clip.Cafe jelenetek filmidőhorgonyaiból számított jelzések; NEM a magyar filmhangban ellenőrzött vágáspontok.

A HDMozi teljesfilmek lejátszását a Work-beszámoló nem tudta igazolni:
- Vasember 3. rpmshare – Loading/üres player;
- Bosszúállók: Ultron kora Videa – embedded/video playback error;
- Bosszúállók Videa – embedded/video playback error.

A két valóban átadott WAV miatt ez nem nulla munka, de **hangmodell szempontból az átvételi küszöböt nem teljesíti**.

## Kötelező továbblépés

1. **Elsőként a már átadott, színésznevével azonosított MaRecord MP3** tényleges megvizsgálása. Ebből kell 5–15 s *meghallgatással ellenőrzött* beszédreferenciát előállítani, ha van alkalmas részlet.
2. Filmkeresésnél a siker kritériuma nem a link vagy a becsült időbélyeg, hanem egy **ténylegesen hozzáférhető, ellenőrzött magyar JARVIS-beszédű WAV** és pontos szöveges átirata.
3. Legalább egy önálló, érthető, 5–15 s tiszta referencia kell az első zero-shot motorpróbához; hosszabb, több mondatos és különböző stílusú filmes korpusz az első eredmény javításához.
4. Magyar szinkron és színészazonosság nélkül **nem szabad** automatikusan hozzáadni a filmes klipet a tanítókorpuszhoz.
5. A jelenetlista címét **keresési jelöltek** megnevezéssel kell kezelni.
6. A privát hanganyag nem kerül GitHubra. A JARVIS main és a Claude integráció változatlan marad.
7. A végrehajtó futtatókörnyezeti WAV-elemzés hibát jelzett; tehát a jelenlegi átvételi következtetések a feltöltött dokumentumokból és metadata alapján készültek, NEM függetlenül meghallgatott hang alapján.

**Minőségi kapu:** a következő kör csak akkor kész, ha valódi 5–15 másodperces beszédreferencia, pontos átirat és sikeresen elkészült F5 vagy XTTS WAV-próba áll rendelkezésre. A modellazonosság hitelesítéséhez emberi hallgatási ellenőrzés kell.
