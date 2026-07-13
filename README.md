# SAFLII Scraper

Lädt südafrikanische Gerichtsurteile und andere Rechtsdokumente von
[SAFLII](https://www.saflii.org/) (Southern African Legal Information
Institute) herunter — als Datengrundlage für RE3 (RAGFlow).

## Setup

```bash
uv sync   # installiert Python 3.13 + Dependencies (Crawlee, BeautifulSoup, ...)
```

## Benutzung

### Vollständiger Crawl (empfohlen): `saflii_processor_yearly.py`

```bash
uv run python saflii_processor_yearly.py
```

Fragt beim Start interaktiv ab (Enter übernimmt jeweils den Default):

| Prompt | Bedeutung | Default |
|---|---|---|
| `FILTER_COURT` | Gerichtskürzel, z.B. `ZAWCHC` | alle Gerichte |
| `FILTER_YEAR` | Jahr, z.B. `2024` | alle Jahre |
| Format(e) | `html`, `pdf`, `rtf`, `all` oder Kombination wie `pdf,html` | `pdf,html` |
| Zielverzeichnis | Ablageort der Downloads | `/Users/rafael/data/Work/RE3_scraper_saflii_data` |

**Warum `pdf,html` als Default:** Das PDF ist das Original-Gerichtsdokument
(aus Word erzeugt, kein Scan) und das primäre Ingest-Format für RAGFlow
(Zitat-Highlighting im PDF-Viewer). HTML ist der sauberste Rohtext als
Archiv/Fallback — einzelne Urteile existieren nur als HTML. RTF ist redundant
zum PDF, von RAGFlow nicht parsebar und das mit Abstand größte Format.

### Gezielter Test-Crawl: `main.py`

Crawlt ein fest im Code eingestelltes Gericht/Jahr (Konstanten anpassen):

```bash
uv run python main.py
```

## Datenablage

```
<Zielverzeichnis>/<Land>/<Kategorie>/<Gericht>/<Jahr>/<Urteilstitel>.<format>
z.B. RE3_scraper_saflii_data/za/cases/ZAWCHC/2024/Abrahams v S (A188-2022) [2024] ZAWCHC 147 (20 May 2024).pdf
```

Die Länderebene (`za`, …) bleibt erhalten, da SAFLII auch Urteile anderer
afrikanischer Länder führt. Die Kategorie-Ebene (`cases`, `other`, `gaz`,
`journals`, …) trennt SAFLIIs Dokumenttypen, sodass sie in RAGFlow als
getrennte Datasets mit eigener Chunk-Konfiguration eingebunden werden können.
Der Crawler selbst erfasst derzeit nur `cases` (Urteile); die anderen
Bereiche folgen teils eigenen URL-Strukturen und sind ein separates Vorhaben.

Bereits vorhandene Dateien werden übersprungen — ein abgebrochener Lauf kann
einfach neu gestartet werden. Crawlee legt seinen Queue-/Fortschritts-State
unter `storage/` ab.

## Wichtige Betriebs-Hinweise

- **Rate-Limit:** saflii.org (hinter Cloudflare) blockt ab ca. 25 Anfragen/Minute
  mit 429 und sperrt danach die IP. Der Scraper fährt deshalb mit 1 paralleler
  Anfrage und leitet die Task-Rate aus der Formatanzahl ab. Nicht erhöhen.
- **Browser-Impersonation:** Plain-HTTP-Clients bekommen 403; es wird ein
  Chrome-Fingerprint verwendet (`CurlImpersonateHttpClient`). PDF/RTF-Downloads
  brauchen zusätzlich einen `Referer`-Header.
- **Site-Struktur** (falls sich am Crawler etwas ändern muss):
  `https://www.saflii.org/content/databases.html` listet alle Gerichte/Datenbanken
  → Gerichtsseite (z.B. `/za/cases/ZAWCHC/`) listet Jahre
  → Jahresseite (z.B. `/za/cases/ZAWCHC/2024/`) listet Dokumente
  → Dokument: `/za/cases/ZAWCHC/2024/<nr>.html` (`.pdf`/`.rtf` unter gleicher URL).
