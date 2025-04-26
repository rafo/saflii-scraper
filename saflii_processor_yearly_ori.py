# saflii_html_downloader.py

import requests
import os
import re

# html2text wird nicht mehr benötigt
from bs4 import BeautifulSoup  # Wird weiterhin für Titel-Extraktion benötigt
import logging
import time

# --- Konfiguration ---
BASE_DATA_DIR = "saflii_daten"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"  # BITTE ANPASSEN
REQUEST_DELAY = 1.0  # Sekunden Wartezeit zwischen Anfragen
MAX_CONSECUTIVE_FAILURES = (
    5  # Anzahl aufeinanderfolgender Fehler (404), bevor der Jahres-Download stoppt
)

# Logging einrichten
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# html2text Konverter wird nicht mehr initialisiert

# --- Kernfunktionen ---


def parse_saflii_url(url):
    """
    Parst eine Saflii-URL, um Metadaten für Verzeichnisse und Logging zu extrahieren.
    """
    match = re.search(r"/([a-z]{2})/cases/([A-Z][A-Z0-9]+)/(\d{4})/(\d+)\.html$", url)
    if match:
        country, court, year, case_number = match.groups()
        citation = f"[{year}] {court} {case_number}"
        return {
            "country": country,
            "court": court,
            "year": year,
            "case_number": case_number,
            "citation": citation,
        }
    else:
        logging.warning(f"URL konnte nicht geparst werden: {url}")
        return None


def generate_filename_from_title(html_content, fallback_citation):
    """
    Extrahiert den Titel aus dem HTML, bereinigt ihn für die Dateibenennung.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title_text = title_tag.get_text(strip=True)
            filename_base = title_text.replace("/", "-")
            # Optional: Entferne weitere potenziell problematische Zeichen (außer Leerzeichen)
            # filename_base = re.sub(r'[\\:*?"<>|]', '', filename_base)
            if filename_base:
                logging.debug(f"Generierter Dateiname aus Titel: '{filename_base}'")
                return filename_base
            else:
                logging.warning(
                    f"Titel gefunden, aber nach Bereinigung leer. Verwende Fallback."
                )
                return fallback_citation
        else:
            logging.warning(
                f"Kein Titel-Tag oder leerer Titel gefunden. Verwende Fallback: {fallback_citation}"
            )
            return fallback_citation
    except Exception as e:
        logging.error(
            f"Fehler beim Extrahieren des Titels: {e}. Verwende Fallback: {fallback_citation}"
        )
        return fallback_citation


def process_saflii_page(url, html_content, base_dir):
    """Verarbeitet heruntergeladenen HTML-Inhalt: Speichert nur die HTML-Datei."""
    metadata = parse_saflii_url(url)
    if not metadata:
        return False

    filename_base = generate_filename_from_title(html_content, metadata["citation"])
    target_dir = os.path.join(
        base_dir, metadata["country"], metadata["court"], metadata["year"]
    )
    html_path = os.path.join(target_dir, f"{filename_base}.html")
    # md_path wird nicht mehr benötigt

    # Prüfen, ob die HTML-Datei bereits existiert
    if os.path.exists(html_path):
        logging.info(
            f"HTML-Datei existiert bereits für '{filename_base}', überspringe Speichern."
        )
        return True

    # Verzeichnis erstellen
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as e:
        logging.error(f"Fehler beim Erstellen des Verzeichnisses {target_dir}: {e}")
        return False

    # HTML speichern
    try:
        with open(
            html_path, "w", encoding="utf-8"
        ) as f:  # utf-8 sollte gut sein, da wir vom Response-Encoding kommen
            f.write(html_content)
        logging.info(
            f"HTML gespeichert: {html_path}"
        )  # Geändert zu INFO, da es das Hauptergebnis ist
    except IOError as e:
        logging.error(f"Fehler beim Speichern der HTML-Datei {html_path}: {e}")
        if os.path.exists(html_path):
            try:
                os.remove(html_path)
                logging.warning(
                    f"Teilweise geschriebene HTML-Datei entfernt: {html_path}"
                )
            except OSError as remove_error:
                logging.error(
                    f"Konnte teilweise geschriebene HTML-Datei nicht entfernen {html_path}: {remove_error}"
                )
        return False

    # --- Block für Markdown-Konvertierung und -Speicherung wurde entfernt ---

    return True  # Erfolg, wenn HTML gespeichert wurde


def download_html(url):
    """Lädt HTML von einer URL herunter. Gibt HTML-Inhalt oder None bei Fehler zurück."""
    logging.debug(f"Versuche Download: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 404:
            logging.info(f"URL nicht gefunden (404): {url}")
            return None
        response.raise_for_status()
        # Versuche das Encoding zu ermitteln und setze es für response.text
        response.encoding = response.apparent_encoding
        logging.debug(f"Verwende erkanntes Encoding: {response.encoding} für {url}")
        return response.text
    except requests.exceptions.HTTPError as e:
        logging.error(
            f"HTTP Fehler beim Download von {url}: {e.response.status_code} {e.response.reason}"
        )
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Download-Fehler (Netzwerk/Timeout etc.) für {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Download für {url}: {e}")
        return None


def download_year(country_code, court_code, year_str, base_dir):
    """
    Versucht, alle Fälle für ein bestimmtes Land, Gericht und Jahr herunterzuladen
    und als HTML zu speichern.
    """
    logging.info(
        f"--- Beginne HTML-Download für Jahr: {country_code}/{court_code}/{year_str} ---"
    )
    case_number = 1
    consecutive_failures = 0
    download_count = 0  # Zähler für erfolgreiche Downloads in diesem Lauf

    while consecutive_failures < MAX_CONSECUTIVE_FAILURES:
        url = f"https://www.saflii.org/{country_code}/cases/{court_code}/{year_str}/{case_number}.html"
        html_content = download_html(url)

        if html_content is not None:
            # Download erfolgreich
            logging.debug(f"Erfolgreich heruntergeladen: {url}")  # Detail-Log
            consecutive_failures = 0
            success = process_saflii_page(url, html_content, base_dir)
            if success:
                download_count += 1
                # Kein separates Logging hier, process_saflii_page loggt den Speicherpfad
                pass
            else:
                logging.warning(
                    f"HTML-Verarbeitung/Speicherung fehlgeschlagen für {url}, setze Jahres-Download fort."
                )
        else:
            # Download fehlgeschlagen (404 oder anderer Fehler)
            logging.debug(
                f"Download fehlgeschlagen oder Seite nicht gefunden für Fall {case_number} ({url}). Erhöhe Fehlerzähler."
            )
            consecutive_failures += 1

        # Pause nach jedem Versuch
        logging.debug(f"Warte {REQUEST_DELAY} Sekunden...")
        time.sleep(REQUEST_DELAY)
        case_number += 1

    logging.info(
        f"--- Jahres-Download für {country_code}/{court_code}/{year_str} beendet. ---"
    )
    logging.info(
        f"Gestoppt nach {consecutive_failures} aufeinanderfolgenden Fehlern (letzter Versuch war Fallnummer {case_number - 1})."
    )
    logging.info(
        f"Insgesamt {download_count} neue HTML-Dateien in diesem Lauf gespeichert."
    )


# --- Hauptausführungspunkt (Beispiel) ---
if __name__ == "__main__":
    # Beispiel: Lade Fälle für ZAWCHC im Jahr 2023 herunter
    target_country = "za"
    target_court = "ZAWCHC"
    target_year = "2023"  # Beispieljahr

    logging.info(
        f"===== Starte Beispiel: HTML-Download für {target_court} / {target_year} ====="
    )
    download_year(target_country, target_court, target_year, BASE_DATA_DIR)
    logging.info(f"===== Beispiel abgeschlossen =====")

    # Fügen Sie hier bei Bedarf weitere Aufrufe für andere Gerichte/Jahre hinzu
    # target_year_2 = "2024"
    # logging.info(f"\n===== Starte Beispiel: HTML-Download für {target_court} / {target_year_2} =====")
    # download_year(target_country, target_court, target_year_2, BASE_DATA_DIR)
    # logging.info(f"===== Beispiel abgeschlossen =====")
