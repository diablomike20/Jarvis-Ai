# JARVIS HU – online filmes források felderítése (2026-10-12)

**Cél:** Kárpáti Levente, mint a filmes magyar J.A.R.V.I.S. hangja. A felhasználó engedélyezett privát hangkutatást jelzett. A linkek tájékozódási források, **nem** letöltött hangfájlok. A beszéd jelenléte, a hangsáv nyelve és a jogosult hozzáférés minden videónál külön ellenőrizendő.

## A felhasználó által megadott filmoldalak

| ID | Film | Oldal | Oldal állapota | Hangállapot |
|---|---|---|---|---|
| HD-IM3 | Vasember 3. (2013) | https://hdmozi.hu/movies/vasember-3/ | Filmoldal és Video Sources blokk elérhető | Player-hang nem hozzáférhető a webes vizsgálatból |
| HD-AV2 | Bosszúállók: Ultron kora (2015) | https://hdmozi.hu/movies/bosszuallok-ultron-kora/ | Filmoldal és Video Sources blokk elérhető | Player-hang nem hozzáférhető a webes vizsgálatból |
| HD-AV1 | Bosszúállók (2012) | https://hdmozi.hu/movies/bosszuallok/ | A közvetlen webes lekérés cache/technikai hibát adott | Nem ellenőrzött |

A 'Video Sources' megnevezésből **nem következik**, hogy a teljes magyar filmhangsáv letölthető, hogy DD 5.1 csatornákat biztosít, vagy hogy a hangsávot megvizsgáltuk. Harmadik fél weboldaláról származó hozzáférés és DRM/engedélyek külön kérdés.

## Konkrét Indavideo találatok

| ID | Találat | Megadott hossz | Link | Jelölés |
|---|---|---:|---|---|
| IV-IM3-1 | Vasember 3 (Iron Man 3, 2013) szinkronos előzetes | keresésben nincs igazolt időadat | https://indavideo.hu/video/Vasember_3_Iron_Man_3_szinkronos_elozetes | Magyar szinkronos trailer, JARVIS hangot nem igazoltunk |
| IV-IM3-2 | IndaJones 'Vasember 3', szinkronos előzetes | 2:25 | https://indavideo.hu/search/text/Vasember%203. | Keresési oldalon szerepel; a konkrét videó URI-ja még nem ellenőrzött |
| IV-AV2-1 | Bosszúállók: Ultron kora - szinkronizált előzetes | keresésben nem igazolt | https://indavideo.hu/video/Bosszuallok_Ultron_kora_-_szinkronizalt_elozetes | Szinkronos trailer; beszélő jelenléte nem igazolt |
| IV-AV2-2 | Bosszúállók: Ultron kora (PORT.hu trailer profil) | nem igazolt | https://indavideo.hu/video/Bosszuallok_Ultron_kora_2 | Videóoldal, leírásban filmszereplők; nyelv és JARVIS hang nem igazolt |
| IV-AV1-1 | Bosszúállók (PORT.hu trailer profil) | nem igazolt | https://indavideo.hu/video/Bosszuallok_5 | 2012-es filmhez tartozó videóoldal, hangsáv nem vizsgált |

**Kizárandó hamis jelöltek:**
- https://indavideo.hu/video/vasember_3_resz_MAGYAR_SZINKRON_1 – **2011-es animációs sorozat harmadik része**, nem a 2013-as `Vasember 3.` film;
- https://indavideo.hu/video/Bosszuallok_Ultron_kora_Poroly_emelgetos_jelenet_Amator_magyar_szinkronnal – cím és leírás szerint **amatőr rajongói szinkron**, nem a célbeszélő hiteles JARVIS-mintája;
- A `Bosszúállók Újra Együtt` animációs sorozat részei, illetve `Bosszúállók: Végjáték` Edwin Jarvis figurája nem automatikusan azonos a filmes AI-asszisztens hangkarakterével; külön kizárási szabály.

## Feldolgozási döntés

1. Hangkönyvtárba kizárólag ténylegesen hozzáférhető, jogszerűen feldolgozható és meghallgatott magyar audiofájl kerül.
2. Sem cím, sem filmadatlap, sem előzetes 'magyar szinkronos' megnevezése nem elegendő a célbeszélő megállapítására.
3. Ha magyar 5.1-es lokális média rendelkezésre áll, az `tools/voice_corpus/prepare_corpus.py` regisztrálja és kezeli (dialógus center csatorna elsődleges vizsgálata).
4. Indavideo trailerből csak tényleges JARVIS-hangot tartalmazó és ellenőrzött részek jöhetnek szóba.
5. A `MaRecord` eredeti, feltöltött MP3 a rendelkezésre álló referencia; az akusztikai elemzés futtatókörnyezeti hiba miatt még nincs kész.
6. Nem igazoltunk és nem töltöttünk le közvetlen filmhangsávot; nincs kész filmes WAV-szegmens vagy tanított modell.

## Webes források a vizsgálat időpontjában

- HDMozi filmoldalak: https://hdmozi.hu/movies/vasember-3/ ; https://hdmozi.hu/movies/bosszuallok-ultron-kora/ ; https://hdmozi.hu/movies/bosszuallok/
- Indavideo Vasember 3 találati lista: https://indavideo.hu/search/text/Vasember%203.
- Indavideo Bosszúállók kategória: https://indavideo.hu/search/tag/Bossz%C3%BA%C3%A1ll%C3%B3k
- Magyar hangsáv / szereposztás: https://emsz.m.iszdb.hu/?szinkron=12772

**Határ:** Ez webes előkutatás, nem streamletöltés, sem auditált hangminta. A JARVIS `main` és Claude `master` nincs megváltoztatva.
