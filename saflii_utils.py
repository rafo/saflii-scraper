# saflii_utils.py
import os
import re
import logging
from bs4 import BeautifulSoup

# Ihre Funktionen parse_saflii_url, generate_filename_from_title,
# und process_saflii_page hier einfügen...
# (Stellen Sie sicher, dass sie nur diese drei Funktionen enthält
# und keine Download-Logik wie download_html oder download_year)

BASE_DATA_DIR = "saflii_daten"  # Definieren Sie dies hier oder übergeben Sie es anders


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


# Fügen Sie hier den tatsächlichen Code der drei Funktionen ein
# aus der Datei saflii_html_downloader.py
# Beispiel für process_saflii_page (gekürzt):
# def process_saflii_page(url, html_content, base_dir):
#     """Verarbeitet heruntergeladenen HTML-Inhalt: Speichert nur die HTML-Datei."""
#     metadata = parse_saflii_url(url)
#     if not metadata:
#         return False

#     filename_base = generate_filename_from_title(html_content, metadata['citation'])
#     target_dir = os.path.join(base_dir, metadata['country'], metadata['court'], metadata['year'])
#     html_path = os.path.join(target_dir, f"{filename_base}.html")

#     if os.path.exists(html_path):
#         logging.info(f"HTML-Datei existiert bereits für '{filename_base}', überspringe Speichern.")
#         return True

#     try:
#         os.makedirs(target_dir, exist_ok=True)
#     except OSError as e:
#         logging.error(f"Fehler beim Erstellen des Verzeichnisses {target_dir}: {e}")
#         return False

#     try:
#         # Stellen Sie sicher, dass html_content ein String ist und korrektes Encoding hat
#         # Crawlee liefert normalerweise einen dekodierten String in context.body
#         with open(html_path, 'w', encoding='utf-8') as f:
#             f.write(html_content)
#         logging.info(f"HTML gespeichert: {html_path}")
#         return True
#     except IOError as e:
#         logging.error(f"Fehler beim Speichern der HTML-Datei {html_path}: {e}")
#         # Aufräumlogik...
#         return False
#     except Exception as e:
#         logging.error(f"Unerwarteter Fehler beim Speichern von {html_path}: {e}")
#         return False

# Stellen Sie sicher, dass die tatsächlichen Implementierungen hier stehen!

