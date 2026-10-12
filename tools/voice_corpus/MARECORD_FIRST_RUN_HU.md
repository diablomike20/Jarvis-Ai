# A feltöltött MaRecord hangminta – első helyi feldolgozás

## Melyik konkrét fájl?

A felhasználó a következő hangmintát töltötte fel a beszélgetésbe:

\`marecord_produkcios_hangstudio-www_marecord_hu_-_karpati_levente_hangminta.mp3\`

Fájlméret a beszélgetés rendszeradata szerint: **1 016 134 byte**, MIME: **audio/mpeg**.
A fájl **itt a beszélgetéshez van csatolva**, nem került át a GitHubra.

**Elvégzett munka:** az MP3-hoz célzott konvertáló/szegmentáló eszköz és offline unit tesztek elkészültek.
**Elmaradt:** az eredeti MP3 gépi vizsgálata, az első WAV-ok tényleges előállítása és a beszéd meghallgatása. A Python/container futtatókörnyezet ismételt ClientError hibát adott.

## Egyetlen parancs Windows PowerShellből

Először töltsd le a már feltöltött MP3 csatolmányt Windows gépedre, például a Letöltések mappába. **Nem kell új hangminta.**

A \`prep/jarvis-hu-film-voice-corpus-20261012\` ág repository-gyökeréből:

\`\`\`powershell
$inputAudio = Join-Path $env:USERPROFILE "Downloads\marecord_produkcios_hangstudio-www_marecord_hu_-_karpati_levente_hangminta.mp3"
$private = Join-Path $env:LOCALAPPDATA "JarvisAI\voice_private"

python tools/voice_corpus/bootstrap_marecord.py --input $inputAudio --output-dir $private --max-clips 8
\`\`\`

Követelmény: Python 3.11+ és FFmpeg/FFprobe a \`PATH\` alatt. A program **nem** tölt fel hangot, és **nem** használ modellt vagy fizetős API-t.

Kimenet:

\`\`\`text
%LOCALAPPDATA%\JarvisAI\voice_private\marecord_<SHA256-azonosító>\
  full_reference_24k_mono.wav
  candidate_01_...wav
  candidate_02_...wav
  ...
  review_candidates.csv
  technical_report.json
\`\`\`

A \`full_reference_24k_mono.wav\` a teljes hanganyag konvertált **munkapéldánya**, **nem ellenőrzött** TTS-hangklón-referencia. A jelölt klippek 4–12 másodperces, a csendek alapján kiválasztott részletek, amelyek **tartalmazhatnak zenét vagy más beszélőt is**. A program nem talál ki átiratot és nem állítja, hogy a hangot felismerte.

A \`review_candidates.csv\` fájlban a pontos szöveg és az emberi ellenőrzés mezői eleve üresek, illetve \`no\` értékűek. Csak kézi meghallgatás és a szöveg pontos ellenőrzése után lehet hangklónozási referenciát kijelölni.

## A következő hangtechnikai lépés

Ha elkészült egy tiszta, ellenőrzött 5–15 másodperces WAV és annak pontos magyar TXT-átirata, az \`TTS_LAB_HU.md\` dokumentumban leírt helyi F5-TTS Hungarian / XTTS-v2 A/B hangpróba indítható. Az első valóban generált fájlig **nincs kész JARVIS hangmodell**.

A stabil JARVIS \`main\`, a Claude-integráció és a három félretett fejlesztési ág változatlan.
