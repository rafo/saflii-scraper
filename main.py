import asyncio
import logging
import re

from crawlee import ConcurrencySettings
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.http_clients import CurlImpersonateHttpClient

from saflii_utils import BASE_DATA_DIR, process_saflii_page

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Target parameters
COUNTRY_CODE = "za"
COURT_CODE = "ZAWCHC"
YEAR = "2024"

MAX_REQUESTS_PER_CRAWL = 2000

DOCUMENT_URL_RE = re.compile(r"/cases/[A-Z][A-Z0-9]*/\d{4}/\d+\.html$")


async def main() -> None:
    crawler = BeautifulSoupCrawler(
        # saflii.org blocks plain HTTP clients (403); impersonate a real browser
        http_client=CurlImpersonateHttpClient(impersonate="chrome", timeout=120),
        max_requests_per_crawl=MAX_REQUESTS_PER_CRAWL,
        max_request_retries=2,
        # Polite crawling: few parallel requests, capped request rate
        concurrency_settings=ConcurrencySettings(
            max_concurrency=3, max_tasks_per_minute=60
        ),
    )

    @crawler.router.default_handler
    async def handle_request(context: BeautifulSoupCrawlingContext) -> None:
        url = context.request.url

        if DOCUMENT_URL_RE.search(url):
            html_content = str(context.soup)
            if process_saflii_page(url, html_content, BASE_DATA_DIR):
                context.log.info(f"Saved document: {url}")
            else:
                context.log.error(f"Failed to process document: {url}")
        else:
            # Year index page: enqueue the actual document links
            await context.enqueue_links(
                selector="a[href$='.html']", strategy="same-origin"
            )

    year_index_url = (
        f"https://www.saflii.org/{COUNTRY_CODE}/cases/{COURT_CODE}/{YEAR}/"
    )
    await crawler.run([year_index_url])


if __name__ == "__main__":
    asyncio.run(main())
