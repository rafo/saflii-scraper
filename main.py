import asyncio
import logging
import os
import random

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from saflii_utils import process_saflii_page, BASE_DATA_DIR

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
os.makedirs(BASE_DATA_DIR, exist_ok=True)


class SafliiHtmlCrawler(BeautifulSoupCrawler):
    async def pre_navigation_hook(self, context, *_):
        await asyncio.sleep(random.uniform(1, 3))  # Delay zwischen Requests
        self.log.info(f"Starte Request: {context.request.url}")

    async def post_navigation_hook(self, context, *_):
        if context.response.status >= 400:
            self.log.warning(
                f"HTTP Fehler {context.response.status} bei: {context.request.url}"
            )


async def main() -> None:
    # --- URLs vorbereiten ---
    start_urls = []
    country_code = "za"
    court_code = "ZAWCHC"
    year_str = "2024"

    for i in range(1, 901):
        start_urls.append(
            f"https://www.saflii.org/{country_code}/cases/{court_code}/{year_str}/{i}.html"
        )

    # --- Crawler konfigurieren ---
    crawler = SafliiHtmlCrawler(
        max_requests_per_crawl=900,
        max_request_retries=2,
    )

    # --- Request-Handler ---
    @crawler.router.default_handler
    async def handle_request(context: BeautifulSoupCrawlingContext) -> None:
        url = context.request.url
        html_content = context.body

        if not html_content:
            context.log.warning(f"Kein HTML-Inhalt empfangen für: {url}")
            return

        context.log.info(f"Verarbeite heruntergeladene Seite: {url}")

        success = process_saflii_page(url, html_content, BASE_DATA_DIR)

        if success:
            context.log.info(f"Erfolgreich verarbeitet und gespeichert: {url}")
        else:
            context.log.error(f"Fehler bei der Verarbeitung/Speicherung von: {url}")

    # --- Crawler starten ---
    await crawler.run(start_urls)


if __name__ == "__main__":
    asyncio.run(main())
