import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import timedelta

from crawlee import ConcurrencySettings, Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.http_clients import CurlImpersonateHttpClient

from saflii_utils import (
    build_file_path,
    generate_filename_from_title,
    parse_saflii_url,
    save_file,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Safety net against runaway crawls when no filters are set
MAX_REQUESTS_PER_CRAWL = 100_000

COURT_PAGE_RE = re.compile(r"/cases/([A-Z][A-Z0-9]*)/?$")
YEAR_PAGE_RE = re.compile(r"/cases/([A-Z][A-Z0-9]*)/(\d{4})/$")
DOCUMENT_RE = re.compile(r"/cases/[A-Z][A-Z0-9]*/\d{4}/\d+\.html$")


@dataclass
class ScraperConfig:
    filter_court: str | None
    filter_year: str | None
    download_format: str  # "html" | "pdf" | "rtf" | "all"

    @property
    def formats(self):
        if self.download_format == "all":
            return ["html", "pdf", "rtf"]
        return [self.download_format]


def get_user_config() -> ScraperConfig:
    """Ask user for court/year filters and download format preferences."""
    print("\n--- Saflii Scraper Configuration ---")

    filter_court = input(
        "Enter FILTER_COURT (e.g., 'ZAWCHC' or press Enter for all courts): "
    ).strip() or None

    filter_year = input(
        "Enter FILTER_YEAR (e.g., '2024' or press Enter for all years): "
    ).strip() or None

    while True:
        download_format = input("Choose download format (html/pdf/rtf/all): ").strip().lower()
        if download_format in ("html", "pdf", "rtf", "all"):
            break
        print("Please enter one of: html, pdf, rtf, all")

    print("\nConfiguration:")
    print(f"  FILTER_COURT: {filter_court if filter_court else 'All courts'}")
    print(f"  FILTER_YEAR: {filter_year if filter_year else 'All years'}")
    print(f"  DOWNLOAD_FORMAT: {download_format}")
    print()

    return ScraperConfig(filter_court, filter_year, download_format)


async def download_and_save_file(url, http_client, filename_base, referer_url):
    """Download a file (PDF/RTF) and save it. Skips files that already exist."""
    metadata = parse_saflii_url(url)
    if not metadata:
        return False

    file_path = build_file_path(metadata, filename_base)
    if os.path.exists(file_path):
        log.info(f"File already exists, skipping download: {file_path}")
        return True

    try:
        # Small delay before direct downloads; these bypass the crawler's rate limiting
        await asyncio.sleep(random.uniform(0.5, 1.5))

        # saflii.org rejects PDF/RTF requests without a Referer (403)
        request = Request.from_url(url, headers={"Referer": referer_url})
        crawl_result = await http_client.crawl(request)
        http_response = crawl_result.http_response

        if http_response.status_code >= 400:
            if http_response.status_code in (404, 410):
                log.info(f"File not available ({http_response.status_code}): {url}")
            else:
                log.error(f"HTTP error downloading {url}: {http_response.status_code}")
            return False

        return save_file(url, http_response.read(), filename_base)

    except asyncio.CancelledError:
        log.warning(f"Download cancelled: {url}")
        raise
    except Exception as e:
        log.error(f"Error downloading {url}: {e}")
        return False


async def main():
    config = get_user_config()

    # saflii.org blocks plain HTTP clients (403); impersonate a real browser
    http_client = CurlImpersonateHttpClient(
        impersonate="chrome",
        timeout=120,  # generous timeout for slow downloads
    )

    crawler = BeautifulSoupCrawler(
        http_client=http_client,
        max_request_retries=5,
        max_requests_per_crawl=MAX_REQUESTS_PER_CRAWL,
        request_handler_timeout=timedelta(minutes=8),
        use_session_pool=True,
        # Polite crawling: few parallel requests, capped request rate
        concurrency_settings=ConcurrencySettings(
            max_concurrency=3, max_tasks_per_minute=60
        ),
    )

    @crawler.router.default_handler
    async def handle_page(context: BeautifulSoupCrawlingContext):
        url = context.request.url
        log.info(f"Processing page: {url}")

        if "databases.html" in url:
            # Stage 1: Enqueue links from table (courts only)
            await context.enqueue_links(
                selector="div.accordion-body table a[href]", strategy="same-origin"
            )
            return

        court_match = COURT_PAGE_RE.search(url)
        if court_match:
            if config.filter_court and court_match.group(1) != config.filter_court:
                log.info(f"Skipping court (filter active): {url}")
                return
            # Stage 2: Court -> Enqueue year links
            await context.enqueue_links(
                selector="a[href^='19'], a[href^='20']", strategy="same-origin"
            )
            return

        year_match = YEAR_PAGE_RE.search(url)
        if year_match:
            court, year = year_match.groups()
            if config.filter_court and court != config.filter_court:
                log.info(f"Skipping court (filter active): {url}")
                return
            if config.filter_year and year != config.filter_year:
                log.info(f"Skipping year (filter active): {url}")
                return
            # Stage 3: Year page -> Enqueue document links
            await context.enqueue_links(
                selector="a[href$='.html']", strategy="same-origin"
            )
            return

        if DOCUMENT_RE.search(url):
            # Stage 4: Document -> Save in requested formats
            metadata = parse_saflii_url(url)
            if not metadata:
                return

            html_content = str(context.soup)
            filename_base = generate_filename_from_title(
                html_content, metadata["citation"]
            )

            success_count = 0
            for fmt in config.formats:
                if fmt == "html":
                    if save_file(url, html_content, filename_base):
                        success_count += 1
                else:
                    target_url = f"{url[:-len('html')]}{fmt}"
                    if await download_and_save_file(
                        target_url, http_client, filename_base, referer_url=url
                    ):
                        success_count += 1

            if success_count < len(config.formats):
                log.info(
                    f"Download summary for {url}: "
                    f"{success_count}/{len(config.formats)} successful"
                )

    start_urls = ["https://www.saflii.org/content/databases.html"]
    await crawler.run(start_urls)


if __name__ == "__main__":
    asyncio.run(main())
