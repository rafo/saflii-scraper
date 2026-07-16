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

Konfiguration über Umgebungsvariablen; fehlt eine Variable, wird im Terminal
interaktiv nachgefragt (Enter = Default). Ohne Terminal (Docker, Cron,
Pipe) gelten automatisch Env-Wert bzw. Default:

| Env-Variable | Prompt | Bedeutung | Default |
|---|---|---|---|
| `SAFLII_FILTER_COURT` | `FILTER_COURT` | Gerichtskürzel, z.B. `ZAWCHC` | alle Gerichte |
| `SAFLII_FILTER_YEAR` | `FILTER_YEAR` | Jahr, z.B. `2024` | alle Jahre |
| `SAFLII_FORMATS` | Format(e) | `html`, `pdf`, `rtf`, `all` oder Kombination wie `pdf,html` | `pdf,html` |
| `SAFLII_DATA_DIR` | Zielverzeichnis | Ablageort der Downloads | `/Volumes/data/Work/RE3_scraper_saflii_data` (NAS via SMB) |
| `SAFLII_LOG_DIR` | — | Ablageort der Logfiles | `<SAFLII_DATA_DIR>/logs` |
| `SAFLII_LOG_RETENTION_DAYS` | — | Logfiles älter als N Tage werden beim Start gelöscht (`0` = nie) | `30` |
| `SAFLII_NTFY_URL` | — | ntfy-Topic-URL für Push-Benachrichtigungen, z.B. `https://ntfy.sh/<topic>` | aus (keine Benachrichtigung) |

Jeder Lauf schreibt zusätzlich zur Konsole ein eigenes Logfile
(`logs/scrape_<zeitstempel>.log`, neben der Sammlung → überlebt
Container-Redeploys). Die letzte Zeile `Scrape finished: …` enthält die
Abschluss-Statistik (Requests, Fehler, Laufzeit) und ist das
„Fertig"-Signal, nach dem man greppen kann; alte Logs räumt der Scraper
beim nächsten Start selbst ab.

Ist `SAFLII_NTFY_URL` gesetzt, schickt der Scraper am Ende des Laufs eine
Push-Benachrichtigung mit derselben Statistik an das [ntfy](https://ntfy.sh)-
Topic (Handy-App abonniert das Topic, kein Account nötig); stirbt der Lauf
mit einer Exception, kommt stattdessen eine `Scrape CRASHED`-Meldung mit
hoher Priorität. Eine fehlgeschlagene Benachrichtigung wird nur geloggt
und beeinflusst den Lauf nicht. Für den Produktivbetrieb bietet sich eine
selbst gehostete ntfy-Instanz auf dem NAS an (privates Topic).

### Betrieb als Docker-Container (NAS/Komodo)

Der Scraper läuft dauerhaft am besten auf dem NAS (Birdsnest, x86_64) —
tagelange Crawls hängen dann nicht am Mac, und die Daten entstehen direkt
auf dem NAS-Volume.

Das Image wird von **GitHub Actions** gebaut (bei jedem Push auf `main`)
und liegt öffentlich unter `ghcr.io/rafo/saflii-scraper:latest` — das NAS
pullt es ohne Anmeldung. In Komodo läuft er als **UI-defined Stack**; der
Compose-Inhalt liegt direkt in der Komodo-UI, nicht im Repo (nichts muss
auf dem Server liegen).

```bash
docker logs -f saflii-scraper
```

- Der Stack mountet `/volume1/data/Work/RE3_scraper_saflii_data`
  (NAS) nach `/downloads` und setzt `SAFLII_DATA_DIR` entsprechend —
  Volume-Nummer in DSM prüfen.
- Das benannte Volume `saflii-storage` hält die Crawlee-Queue → nach
  Container-Neustart wird fortgesetzt statt neu begonnen; zusätzlich
  überspringt der Scraper ohnehin alle bereits vorhandenen Dateien.
- Der Container beendet sich nach vollständigem Durchlauf selbst
  (`restart: on-failure` startet nur Abstürze neu). Re-Scrape = Stack in
  Komodo neu deployen.
- Filter per Env im Stack setzen, z.B. `SAFLII_FILTER_COURT=ZAWCHC`.

**Entwicklungs-Workflow:** Entwickelt und getestet wird lokal auf dem Mac
(dieses Repo, `uv run …` — die interaktiven Prompts funktionieren weiter).
Deployment:

```bash
git push                      # GitHub Actions baut + pusht das Image
# danach: Stack in Komodo redeployen (pullt :latest)
```

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
<Zielverzeichnis>/<Format>/<Land>/<Kategorie>/<Gericht>/<Jahr>/<Urteilstitel>.<format>
z.B. RE3_scraper_saflii_data/pdf/za/cases/ZAWCHC/2024/Abrahams v S (A188-2022) [2024] ZAWCHC 147 (20 May 2024).pdf
```

- **Format-Ebene** (`pdf`, `html`, …): trennt die Formate, damit RAGFlow-Datasets
  komplette Ordner aus dem `pdf/`-Baum einbinden können, ohne dass HTML-Duplikate
  mit importiert werden. `html/` ist Rohtext-Archiv und Fallback.
- **Länderebene** (`za`, …): bleibt erhalten, da SAFLII auch Urteile anderer
  afrikanischer Länder führt.
- **Kategorie-Ebene** (`cases`, `other`, `gaz`, `journals`, …): trennt SAFLIIs
  Dokumenttypen für getrennte RAGFlow-Datasets mit eigener Chunk-Konfiguration.
  Der Crawler selbst erfasst derzeit nur `cases` (Urteile); die anderen Bereiche
  folgen teils eigenen URL-Strukturen und sind ein separates Vorhaben.

Dateinamen entsprechen dem vollen SAFLII-Dokumenttitel (Parteien, Aktenzeichen,
neutrale Zitierung, Datum) — Anwälte brauchen den exakten Namen, und RAGFlow
zeigt ihn als Quelle an. Bei Überlänge (>240 Bytes) werden die Parteinamen
gekürzt, Zitierung und Datum bleiben immer erhalten.

Bereits vorhandene Dateien werden übersprungen — ein abgebrochener Lauf kann
einfach neu gestartet werden. Crawlee legt seinen Queue-/Fortschritts-State
unter `storage/` ab.

## Aktualisierungs-Workflow: Scrape → Reconcile → Sync

**Hintergrund:** SAFLII korrigiert Dokumenttitel nachträglich (2026-07-13 bei 12
von ~440 ZAWCHC-2024-Urteilen beobachtet). Deshalb muss periodisch über den
Bestand gescrapt werden — und danach müssen Sammlung und RAGFlow ohne Handarbeit
nachziehen. Der stabile Schlüssel dafür ist die **neutrale Zitierung** im
Dateinamen (z.B. `[2024] ZAWCHC 147`): Titel ändern sich, die Zitierung nie.

### Schritt 1: Re-Scrape

```bash
uv run python saflii_processor_yearly.py   # Enter-Defaults genügen
```

Vorhandene Dateinamen werden übersprungen; heruntergeladen werden nur neue
Urteile und titelkorrigierte (= neuer Dateiname). **Bekannte Lücke:** Ändert
SAFLII den *Inhalt* ohne den Titel, wird das nicht erkannt (Abgleich läuft nur
über Dateinamen).

### Schritt 2: Duplikate auflösen — `reconcile.py`

Nach Titelkorrekturen liegt dasselbe Urteil doppelt da (alter + neuer Name).

```bash
uv run python reconcile.py            # Dry-Run: zeigt nur, was passieren würde
uv run python reconcile.py --apply    # löscht die Alt-Dateien wirklich
```

Gruppiert pro Ordner nach Zitierung + Endung, behält je Gruppe die neueste
Datei (mtime) und löscht ältere. `--apply` schreibt ein JSON-Protokoll
(`reconcile_log_<zeitstempel>.json`) mit jeder Löschung.

### Schritt 3: RAGFlow abgleichen — `ragflow_sync.py`

Gleicht einen lokalen PDF-Ordner (rekursiv) mit einem RAGFlow-Dataset ab.
Lokal ist die Quelle der Wahrheit.

```bash
export RAGFLOW_API_KEY=ragflow-...    # RAGFlow-UI → Avatar → API → API-Key
uv run python ragflow_sync.py \
  "/Volumes/data/Work/RE3_scraper_saflii_data/pdf/za/cases/ZAWCHC" \
  "SA Case Law ZAWCHC"                # Dry-Run
# … Ausgabe prüfen, dann:
uv run python ragflow_sync.py … --apply
```

Was pro Datei passiert:

| Situation | Aktion | Kosten |
|---|---|---|
| Lokal neu, Zitierung unbekannt in RAGFlow | Upload + Parsing wird angestoßen | Embedding nur für neue Urteile |
| Zitierung in RAGFlow unter altem Namen | Dokument wird **umbenannt** | keine — Inhalt identisch, kein Re-Parsing |
| In RAGFlow, lokal nicht mehr vorhanden | nur mit `--delete` entfernt | — |

Weitere Optionen: `--no-parse` (Parsing nicht anstoßen), `--base-url` bzw.
`RAGFLOW_BASE_URL` (Default `http://127.0.0.1`), `--delete` (verwaiste
Dokumente entfernen; bewusst kein Default).

**Dataset-Zuordnung:** Ein Aufruf = ein Ordner → ein Dataset (wird bei
`--apply` automatisch angelegt). Ob ein Dataset pro Gericht, pro Kategorie
oder ein großes — das entscheidet einfach der übergebene Ordner-Pfad.

### Alles zusammen (z.B. monatlich per Cron)

```bash
uv run python saflii_processor_yearly.py < /dev/null   # ohne TTY: alle Defaults
uv run python reconcile.py --apply
uv run python ragflow_sync.py "<pdf-Ordner>" "<Dataset>" --apply
```

(Läuft der Scraper als NAS-Container, ersetzt „Stack redeployen" die erste
Zeile; Reconcile + Sync laufen weiterhin dort, wo RAGFlow erreichbar ist.)

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
