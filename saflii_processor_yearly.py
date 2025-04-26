import asyncio
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import Request
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
from bs4 import BeautifulSoup
import re
import os

BASE_DATA_DIR = "saflii_daten"

FILTER_COURT = None  # Beispiel: "ZAWCHC"
FILTER_YEAR = None   # Beispiel: "2023"
FILTER_COURT = "ZAWCHC"  # Beispiel: "ZAWCHC"
FILTER_YEAR = "2024"   # Beispiel: "2023"

def parse_saflii_url(url):
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
        log.warning(f"URL konnte nicht geparst werden: {url}")
        return None

def generate_filename_from_title(html_content, fallback_citation):
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title_text = title_tag.get_text(strip=True)
            filename_base = title_text.replace("/", "-")
            return filename_base if filename_base else fallback_citation
        else:
            return fallback_citation
    except Exception as e:
        log.error(f"Fehler beim Extrahieren des Titels: {e}")
        return fallback_citation

def save_html(url, html_content):
    log.info(f"Verarbeite URL zum Speichern: {url}")
    metadata = parse_saflii_url(url)
    if not metadata:
        log.warning(f"Überspringe URL (kein Match für Speicherlogik): {url}")
        return False

    filename_base = generate_filename_from_title(html_content, metadata["citation"])
    target_dir = os.path.join(BASE_DATA_DIR, metadata["country"], metadata["court"], metadata["year"])
    os.makedirs(target_dir, exist_ok=True)
    html_path = os.path.join(target_dir, f"{filename_base}.html")

    if os.path.exists(html_path):
        log.info(f"HTML existiert bereits: {html_path}")
        return True

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        log.info(f"Gespeichert: {html_path}")
        return True
    except Exception as e:
        log.error(f"Fehler beim Speichern: {e}")
        return False

class SafliiCrawler(BeautifulSoupCrawler):
    pass

async def main():
    crawler = SafliiCrawler()

    @crawler.router.default_handler
    async def handle_page(context: BeautifulSoupCrawlingContext):
        log.info(f"Verarbeite Seite: {context.request.url}")
        url = context.request.url
        if "databases.html" in url:
            # Stufe 1: Enqueue Links aus der Tabelle (nur Gerichte)
            await context.enqueue_links(selector="div.accordion-body table a[href]", strategy="same-origin")
        elif re.search(r"/cases/[A-Z]+/?$", url):
            if FILTER_COURT and FILTER_COURT not in url:
                log.info(f"Überspringe Gericht (Filter aktiv): {url}")
                return
            # Stufe 2: Gericht -> Jahreslinks enqueuen
            await context.enqueue_links(selector="a[href^='19'], a[href^='20']", strategy="same-origin")
        elif re.search(r"/cases/[A-Z]+/\d{4}/$", url):
            if FILTER_YEAR and FILTER_YEAR not in url:
                log.info(f"Überspringe Jahr (Filter aktiv): {url}")
                return
            # Stufe 3: Jahresseite -> Schriftstück-Links speichern
            await context.enqueue_links(selector="a[href$='.html']", strategy="same-origin")
        elif re.search(r"/cases/[A-Z]+/\d{4}/\d+\.html$", url):
            # Stufe 4: Schriftstück -> speichern
            html = str(context.soup)
            save_html(url, html)

    start_urls = ["https://www.saflii.org/content/databases.html"]
    await crawler.run(start_urls)

if __name__ == "__main__":
    asyncio.run(main())
