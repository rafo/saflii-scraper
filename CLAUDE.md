# CLAUDE.md

Anleitung für Claude Code in diesem Repository.

## Kontext

SAFLII-Scraper für RE3: lädt südafrikanische Gerichtsurteile von saflii.org
als Datengrundlage für die RAGFlow-Instanz (lokal auf Rafaels Mac, später
Kunden-Server). **Das README.md ist die maßgebliche Doku** für Benutzung,
Env-Variablen, Datenablage und den Update-Workflow (Scrape → Reconcile →
Sync) — dort nachlesen und bei Änderungen mitpflegen, hier nicht duplizieren.

Zugehörige Orte außerhalb dieses Repos:

- RAGFlow-Betrieb/Branding: `/Users/rafael/docker/ragflow` (eigene
  Claude-Session dort starten, wenn es um RAGFlow selbst geht)
- RE3-Planung/Notizen (Obsidian): `/Users/rafael/data/Work/RE3/`
  (`RE3.AI.md`, `RE3 Deployment Plan.md`, `ToDo.md`)
- Scrape-Sammlung: NAS `/volume1/data/Work/RE3_scraper_saflii_data`,
  vom Mac aus als SMB-Mount `/Volumes/data/Work/RE3_scraper_saflii_data`

## Git-Remotes (Achtung)

- `ghfork` = https://github.com/rafo/saflii-scraper — **das aktive Remote**,
  `main` trackt es, hierhin pushen. Push auf `main` triggert den
  GitHub-Actions-Build (amd64-Image → `ghcr.io/rafo/saflii-scraper:latest`).
- `origin` = iTeamGo/saflii — **veraltetes Team-Repo, nicht pushen.**

## Deployment

Produktiv läuft der Scraper als Container auf dem NAS „Birdsnest" (x86_64),
verwaltet als UI-defined Stack in Komodo (Compose-Inhalt liegt in der
Komodo-UI, nicht im Repo). Ablauf: `git push` → Actions baut das Image →
Stack in Komodo redeployen (pullt `:latest`). Details im README.

## Code-Landkarte

- `saflii_processor_yearly.py` — der Voll-Crawler (produktiv genutzt)
- `main.py` — gezielter Test-Crawl, Konstanten im Code
- `saflii_utils.py` — gemeinsame Helfer (URL-Parsing, Dateinamen, Pfade);
  einzige Quelle für diese Logik, von beiden Crawlern genutzt
- `reconcile.py` — Duplikat-Auflösung nach Titelkorrekturen
  (Schlüssel: neutrale Zitierung, neueste Datei gewinnt)
- `ragflow_sync.py` — Abgleich lokaler PDF-Ordner ↔ RAGFlow-Dataset
  (ragflow-sdk; braucht `RAGFLOW_API_KEY`, Default-URL `http://127.0.0.1`)
- `saflii_processor_yearly_ori.py` — eingefrorener Originalstand, nicht
  weiterentwickeln
- `docker-compose.yml` — Altlast aus der Kotaemon-Evaluierung, gehört nicht
  zum Scraper (das Produktiv-Compose liegt in Komodo)

## Harte Randbedingungen (nicht „optimieren")

- **Rate-Limit:** saflii.org blockt ab ~25 Anfragen/Minute mit 429 und
  sperrt dann die IP. Concurrency/Rate im Crawler nicht erhöhen.
- **403-Schutz:** Nur mit `CurlImpersonateHttpClient(impersonate="chrome")`
  kommt man durch; PDF/RTF brauchen zusätzlich einen `Referer`-Header.
- **Dateinamen sind API:** Voller SAFLII-Titel als Dateiname (RAGFlow zeigt
  ihn Anwälten als Quelle); die neutrale Zitierung (z. B. `[2024] ZAWCHC 147`)
  ist der stabile Schlüssel für reconcile/sync — Kürzungslogik bei Überlänge
  erhält Zitierung + Datum immer. Änderungen an `generate_filename_from_title`
  /`sanitize_filename` gefährden den gesamten Abgleich-Workflow.
- **Ablage-Layout** `<base>/<format>/<land>/<kategorie>/<gericht>/<jahr>/`
  ist mit den RAGFlow-Datasets verzahnt (Datasets binden Ordner aus dem
  `pdf/`-Baum ein) — nicht umstrukturieren, ohne den Sync mitzudenken.

## Bekannte Lücken / geplante Arbeiten

- Crawler erfasst nur `cases`; Journals, Gazettes, Rolls haben eigene
  URL-Strukturen → separates Vorhaben.
- Inhaltsänderungen ohne Titeländerung werden nicht erkannt
  (Skip-Logik ist rein dateinamensbasiert).
- Periodischer Re-Scrape + Reconcile + Sync soll als Cron laufen
  (SAFLII korrigiert Titel nachträglich); bisher manuell.
- Stand Juli 2026: Erster Voll-Scrape (alle Courts, pdf+html) am
  14.07.2026 auf dem NAS gestartet, Laufzeit mehrere Tage.

## Entwicklung

```bash
uv sync                                    # Python 3.13 + Dependencies
uv run python saflii_processor_yearly.py   # interaktive Prompts lokal
uv run python reconcile.py                 # Dry-Run
uv run python ragflow_sync.py <pdf-Ordner> <Dataset>   # Dry-Run
```

- Immer erst Dry-Run prüfen, dann `--apply` (gilt für reconcile und sync).
- Kleine Test-Crawls über `SAFLII_FILTER_COURT`/`SAFLII_FILTER_YEAR`
  eingrenzen, nie ungefiltert „kurz testen" (Rate-Limit, tagelange Läufe).
- Kein Test-Framework im Repo; Verifikation läuft über Dry-Runs und
  gezielte Mini-Crawls.
