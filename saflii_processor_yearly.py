# saflii_processor_yearly.py

import requests
import os
import re
import html2text
from bs4 import BeautifulSoup
import logging
import time

# --- Konfiguration ---
BASE_DATA_DIR = "saflii_daten"
USER_AGENT = "Mein KI Projekt Bot (Kontakt: ihre-email@example.com)" # BITTE ANPASSEN
REQUEST_DELAY = 1.0 # Sekunden Wartezeit zwischen Anfragen
MAX_CONSECUTIVE_FAILURES = 5 # Anzahl aufeinanderfolgender Fehler (404), bevor der Jahres-Download stoppt

# Logging einrichten
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# html2text Konverter
h_converter = html2text.HTML2Text()
h_converter.ignore_links = False
h_converter.ignore_images = True
h_converter.body_width = 0
h_converter.unicode_snob = True
h_converter.escape_snob = True

# --- Kernfunktionen ---

def parse_saflii_url(url):
    """Parst eine Saflii-URL, um Metadaten zu extrahieren."""
    match = re.search(r'/([a-z]{2})/cases/([A-Z][A-Z0-9]+)/(\d{4})/(\d+)\.html$', url)
    if match:
        country, court, year, case_number = match.groups()
        citation = f"[{year}] {court} {case_number}"
        filename_base = citation
        return {
            'country': country, 'court': court, 'year': year,
            'case_number': case_number, 'citation': citation,
            'filename_base': filename_base
        }
    else:
        logging.warning(f"URL konnte nicht geparst werden: {url}")
        return None

def process_saflii_page(url, html_content, base_dir):
    """Verarbeitet heruntergeladenen HTML-Inhalt: Speichert HTML und Markdown."""
    metadata = parse_saflii_url(url)
    if not metadata:
        return False

    target_dir = os.path.join(base_dir, metadata['country'], metadata['court'], metadata['year'])
    html_path = os.path.join(target_dir, f"{metadata['filename_base']}.html")
    md_path = os.path.join(target_dir, f"{metadata['filename_base']}.md")

    if os.path.exists(html_path) and os.path.exists(md_path):
        logging.info(f"Dateien existieren bereits für {metadata['citation']}, überspringe Speichern.")
        return True

    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as e:
        logging.error(f"Fehler beim Erstellen des Verzeichnisses {target_dir}: {e}")
        return False

    # HTML speichern
    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.debug(f"HTML gespeichert: {html_path}")
    except IOError as e:
        logging.error(f"Fehler beim Speichern der HTML-Datei {html_path}: {e}")
        if os.path.exists(html_path): try: os.remove(html_path) catch: pass
        return False

    # Markdown konvertieren und speichern
    try:
        # Optional: Hauptinhalt extrahieren mit BeautifulSoup, falls gewünscht
        # soup = BeautifulSoup(html_content, 'html.parser')
        # ... finde relevanten Tag ...
        # html_to_convert = str(relevanter_tag) if relevanter_tag else html_content
        html_to_convert = html_content
        markdown_content = h_converter.handle(html_to_convert)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logging.debug(f"Markdown gespeichert: {md_path}")
    except Exception as e:
        logging.error(f"Fehler beim Konvertieren/Speichern von Markdown für {url}: {e}")
        if os.path.exists(md_path): try: os.remove(md_path) catch: pass
        return False # Teilweiser Fehlschlag

    return True

def download_html(url):
    """Lädt HTML von einer URL herunter. Gibt HTML-Inhalt oder None bei Fehler zurück."""
    logging.debug(f"Versuche Download: {url}")
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30) # Timeout hinzufügen
        # Speziell auf 404 prüfen, bevor allgemeine Fehler ausgelöst werden
        if response.status_code == 404:
            logging.info(f"URL nicht gefunden (404): {url}")
            return None # Signalisiert "Nicht gefunden"
        response.raise_for_status() # Löst Fehler für andere 4xx, 5xx aus
        return response.text # Gibt den HTML-Inhalt zurück
    except requests.exceptions.HTTPError as e:
        # Fängt jetzt nur noch Nicht-404 HTTP-Fehler
        logging.error(f"HTTP Fehler beim Download von {url}: {e.response.status_code} {e.response.reason}")
        return None # Signalisiert allgemeinen Downloadfehler
    except requests.exceptions.RequestException as e:
        logging.error(f"Download-Fehler (Netzwerk/Timeout etc.) für {url}: {e}")
        return None # Signalisiert allgemeinen Downloadfehler
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Download für {url}: {e}")
        return None # Signalisiert unerwarteten Fehler


def download_year(country_code, court_code, year_str, base_dir):
    """
    Versucht, alle Fälle für ein bestimmtes Land, Gericht und Jahr herunterzuladen,
    indem Fallnummern sequenziell hochgezählt werden.
    """
    logging.info(f"--- Beginne Download für Jahr: {country_code}/{court_code}/{year_str} ---")
    case_number = 1
    consecutive_failures = 0 # Zähler für aufeinanderfolgende Fehler (hauptsächlich 404)

    while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
        # URL für die aktuelle Fallnummer konstruieren
        url = f"https://www.saflii.org/{country_code}/cases/{court_code}/{year_str}/{case_number}.html"

        html_content = download_html(url) # Ruft die Download-Funktion auf

        if html_content is not None:
            # Erfolg! HTML wurde heruntergeladen.
            logging.info(f"Erfolgreich heruntergeladen: {url}")
            consecutive_failures = 0 # Fehlerzähler zurücksetzen
            # Heruntergeladene Seite verarbeiten (HTML/MD speichern)
            success = process_saflii_page(url, html_content, base_dir)
            if not success:
                logging.warning(f"Verarbeitung fehlgeschlagen für {url}, setze Jahres-Download fort.")
                # Hier könnte man entscheiden, ob ein Verarbeitungsfehler den Jahres-Download abbrechen soll
        else:
            # Download fehlgeschlagen (war wahrscheinlich ein 404 oder anderer Fehler)
            logging.info(f"Download fehlgeschlagen oder Seite nicht gefunden für Fall {case_number}. Erhöhe Fehlerzähler.")
            consecutive_failures += 1

        # Höflichkeitspause *nach* jedem Versuch (egal ob erfolgreich oder nicht)
        logging.debug(f"Warte {REQUEST_DELAY} Sekunden...")
        time.sleep(REQUEST_DELAY)

        # Zur nächsten potenziellen Fallnummer übergehen
        case_number += 1

        # Optional: Sicherheitslimit für case_number hinzufügen, falls etwas schiefgeht
        # if case_number > 5000: # Beispiel: Max. 5000 Fälle pro Jahr annehmen
        #    logging.warning(f"Sicherheitslimit für Fallnummern erreicht für {year_str}. Breche ab.")
        #    break

    logging.info(f"--- Jahres-Download für {country_code}/{court_code}/{year_str} beendet. "
                 f"Gestoppt nach {consecutive_failures} aufeinanderfolgenden Fehlern "
                 f"(letzter Versuch war Fallnummer {case_number - 1}). ---")


# --- Hauptausführungspunkt (Beispiel) ---
if __name__ == "__main__":
    # Beispiel: Lade alle Fälle für ZAWCHC im Jahr 2023 herunter
    target_country = "za"
    target_court = "ZAWCHC"
    target_year = "2023" # Als String, da es Teil der URL ist

    logging.info(f"===== Starte Beispiel: Download für {target_court} / {target_year} =====")
    download_year(target_country, target_court, target_year, BASE_DATA_DIR)
    logging.info(f"===== Beispiel abgeschlossen =====")

    # Sie könnten hier weitere Aufrufe hinzufügen:
    # logging.info(f"\n===== Starte Beispiel: Download für ZASCA / 2022 =====")
    # download_year("za", "ZASCA", "2022", BASE_DATA_DIR)
    # logging.info(f"===== Beispiel abgeschlossen =====")

    # Hinweis zur Crawlee-Integration:
    # In Crawlee würden Sie wahrscheinlich nicht `download_year` direkt verwenden.
    # Stattdessen würden Sie Crawlee eine Liste von Start-URLs geben oder
    # eine Logik implementieren, die diese URLs generiert (z.B. case 1 bis N für jedes Jahr)
    # und Crawlee die Abarbeitung überlassen. Die Funktion `process_saflii_page`
    # bliebe jedoch zentral für die Verarbeitung jeder erfolgreich heruntergeladenen Seite.
    # Die Logik zum Erkennen des "Endes" eines Jahres (durch 404-Fehler) müsste
    # in die Fehlerbehandlung von Crawlee integriert werden.