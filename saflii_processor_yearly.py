import asyncio
import logging
import os
import random
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta

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


VALID_FORMATS = ("html", "pdf", "rtf")
# PDF is the primary ingest format for RAGFlow (original look, citation
# highlighting); HTML is the clean-text archive/fallback. RTF on request only.
DEFAULT_FORMATS = "pdf,html"

# Central collection on the NAS (Birdsnest), as seen from the Mac via SMB.
# The scraper container on the NAS overrides this with SAFLII_DATA_DIR.
DEFAULT_DATA_DIR = "/Volumes/data/Work/RE3_scraper_saflii_data"

# One logfile per run (like reconcile's per-run JSON logs), kept next to
# the collection so it survives container redeploys. Old logs are removed
# at startup after SAFLII_LOG_RETENTION_DAYS (0 disables the cleanup).
DEFAULT_LOG_RETENTION_DAYS = 30
LOG_FILE_PREFIX = "scrape_"


@dataclass
class ScraperConfig:
    filter_court: str | None
    filter_year: str | None
    download_format: str  # "all" or comma-separated subset of VALID_FORMATS, e.g. "pdf,html"
    data_dir: str = DEFAULT_DATA_DIR

    @property
    def formats(self):
        if self.download_format == "all":
            return list(VALID_FORMATS)
        seen = []
        for fmt in self.download_format.split(","):
            fmt = fmt.strip()
            if fmt and fmt not in seen:
                seen.append(fmt)
        return seen


def get_user_config() -> ScraperConfig:
    """Configuration from SAFLII_* env vars (container/cron) or prompts (TTY).

    Every setting first checks its environment variable. Missing values are
    prompted for only when stdin is a terminal; otherwise the default applies,
    so the scraper runs unattended in Docker or cron without any input.
    """
    interactive = sys.stdin.isatty()

    def setting(env_key, prompt_text):
        value = os.environ.get(env_key)
        if value is not None:
            return value.strip()
        if interactive:
            return input(prompt_text).strip()
        return ""

    if interactive:
        print("\n--- Saflii Scraper Configuration ---")

    filter_court = setting(
        "SAFLII_FILTER_COURT",
        "Enter FILTER_COURT (e.g., 'ZAWCHC' or press Enter for all courts): ",
    ) or None

    filter_year = setting(
        "SAFLII_FILTER_YEAR",
        "Enter FILTER_YEAR (e.g., '2024' or press Enter for all years): ",
    ) or None

    while True:
        download_format = (
            setting(
                "SAFLII_FORMATS",
                "Choose download format(s) (html/pdf/rtf/all, combine with comma; "
                f"press Enter for '{DEFAULT_FORMATS}'): ",
            ).lower()
            or DEFAULT_FORMATS
        )
        if download_format == "all":
            break
        chosen = [fmt.strip() for fmt in download_format.split(",") if fmt.strip()]
        if chosen and all(fmt in VALID_FORMATS for fmt in chosen):
            break
        if not interactive:
            log.error(f"Invalid SAFLII_FORMATS: {download_format!r}")
            sys.exit(1)
        print("Please enter 'all' or a comma-separated combination of: html, pdf, rtf")

    data_dir = os.path.expanduser(
        setting(
            "SAFLII_DATA_DIR",
            f"Enter target directory (press Enter for '{DEFAULT_DATA_DIR}'): ",
        )
        or DEFAULT_DATA_DIR
    )

    print("\nConfiguration:")
    print(f"  FILTER_COURT: {filter_court if filter_court else 'All courts'}")
    print(f"  FILTER_YEAR: {filter_year if filter_year else 'All years'}")
    print(f"  DOWNLOAD_FORMAT: {download_format}")
    print(f"  DATA_DIR: {data_dir}")
    print()

    return ScraperConfig(filter_court, filter_year, download_format, data_dir)


def setup_file_logging(data_dir):
    """Write a per-run logfile to <data_dir>/logs (or SAFLII_LOG_DIR).

    The file handler sits on the root logger so saflii_utils messages are
    captured as well. Returns the logfile path, or None if the directory
    cannot be created (console logging still works then).
    """
    log_dir = os.environ.get("SAFLII_LOG_DIR") or os.path.join(data_dir, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        log.warning(f"Cannot create log directory {log_dir}, file logging disabled: {e}")
        return None

    log_path = os.path.join(
        log_dir, f"{LOG_FILE_PREFIX}{datetime.now():%Y%m%d_%H%M%S}.log"
    )
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)

    cleanup_old_logs(log_dir)
    return log_path


def cleanup_old_logs(log_dir):
    """Delete this scraper's logfiles older than the retention period."""
    try:
        retention_days = int(
            os.environ.get("SAFLII_LOG_RETENTION_DAYS", DEFAULT_LOG_RETENTION_DAYS)
        )
    except ValueError:
        log.warning("Invalid SAFLII_LOG_RETENTION_DAYS, using default")
        retention_days = DEFAULT_LOG_RETENTION_DAYS
    if retention_days <= 0:
        return

    cutoff = time.time() - retention_days * 86400
    for name in os.listdir(log_dir):
        if not (name.startswith(LOG_FILE_PREFIX) and name.endswith(".log")):
            continue
        path = os.path.join(log_dir, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                log.info(f"Deleted old logfile: {name}")
        except OSError as e:
            log.warning(f"Could not delete old logfile {name}: {e}")


def notify_ntfy(message, priority="default"):
    """Push a notification to the ntfy topic in SAFLII_NTFY_URL.

    Default ist die ntfy-Instanz im Komodo-Netz auf dem NAS; leerer Wert
    (`SAFLII_NTFY_URL=`) schaltet Benachrichtigungen ab. Never raises — a
    failed notification must not take down or mask the actual scrape result.
    """
    url = os.environ.get("SAFLII_NTFY_URL", "http://ntfy:8080/scraper-saflii")
    if not url:
        return
    headers = {"Title": "SAFLII Scraper", "Priority": priority}
    token = os.environ.get("SAFLII_NTFY_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        request = urllib.request.Request(
            url,
            data=message.encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=15):
            pass
        log.info(f"ntfy notification sent to {url}")
    except Exception as e:
        log.warning(f"Could not send ntfy notification to {url}: {e}")


def write_collection_readme(config, stats):
    """Self-describing marker at the collection root: source + last run.

    Lets anyone browsing the NAS see where and when the files came from
    without opening the repo. Overwritten each run (history is in logs/);
    never raises — a failed marker must not mask the scrape result.
    """
    path = os.path.join(config.data_dir, "README.md")
    content = (
        "# RE3-Sammlung: SAFLII (südafrikanische Rechtsprechung)\n\n"
        "Automatisch erzeugt vom SAFLII-Scraper "
        "(Repo `saflii-scraper`) — nicht von Hand bearbeiten, wird nach "
        "jedem Lauf überschrieben.\n\n"
        "- Quelle: https://www.saflii.org (Kategorie `cases`)\n"
        "- Ablage: `<format>/<land>/<kategorie>/<gericht>/<jahr>/"
        "<Urteilstitel>.<format>`\n"
        f"- Letzter Lauf: {datetime.now():%Y-%m-%d %H:%M} "
        f"(court={config.filter_court or 'alle'}, "
        f"year={config.filter_year or 'alle'}, "
        f"Formate {','.join(config.formats)})\n"
        f"- Ergebnis: {stats.requests_finished} Requests, "
        f"{stats.requests_failed} Fehler, Laufzeit {stats.crawler_runtime}\n"
        "- Lauf-Historie: siehe `logs/`\n"
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        log.info(f"Collection README updated: {path}")
    except OSError as e:
        log.warning(f"Could not write collection README {path}: {e}")


def build_start_urls(config):
    """Start as deep in the site hierarchy as the filters allow.

    Visiting the databases index costs one request per court just to skip
    them, which quickly exhausts saflii.org's rate limit. Note: direct
    start URLs assume South African courts (za).
    """
    if config.filter_court and config.filter_year:
        return [
            f"https://www.saflii.org/za/cases/{config.filter_court}/{config.filter_year}/"
        ]
    if config.filter_court:
        return [f"https://www.saflii.org/za/cases/{config.filter_court}/"]
    return ["https://www.saflii.org/content/databases.html"]


async def download_and_save_file(url, http_client, filename_base, referer_url, base_dir):
    """Download a file (PDF/RTF) and save it. Skips files that already exist."""
    metadata = parse_saflii_url(url)
    if not metadata:
        return False

    file_path = build_file_path(metadata, filename_base, base_dir)
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

        return save_file(url, http_response.read(), filename_base, base_dir)

    except asyncio.CancelledError:
        log.warning(f"Download cancelled: {url}")
        raise
    except Exception as e:
        log.error(f"Error downloading {url}: {e}")
        return False


async def main():
    config = get_user_config()

    log_path = setup_file_logging(config.data_dir)
    log.info(
        f"Scrape started: court={config.filter_court or 'all'}, "
        f"year={config.filter_year or 'all'}, formats={config.formats}, "
        f"data_dir={config.data_dir}, logfile={log_path}"
    )

    # saflii.org blocks plain HTTP clients (403); impersonate a real browser
    http_client = CurlImpersonateHttpClient(
        impersonate="chrome",
        timeout=120,  # generous timeout for slow downloads
    )

    # saflii.org (behind Cloudflare) rate-limits with 429 at roughly
    # 25 requests/minute and then blocks the IP entirely. Each document
    # task makes one request per format (HTML fetch + PDF/RTF downloads),
    # so derive the task rate from the format count to stay below ~20/min.
    tasks_per_minute = max(20 // len(config.formats), 5)

    crawler = BeautifulSoupCrawler(
        http_client=http_client,
        max_request_retries=5,
        max_requests_per_crawl=MAX_REQUESTS_PER_CRAWL,
        request_handler_timeout=timedelta(minutes=8),
        use_session_pool=True,
        concurrency_settings=ConcurrencySettings(
            max_concurrency=1, max_tasks_per_minute=tasks_per_minute
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
                    if save_file(url, html_content, filename_base, config.data_dir):
                        success_count += 1
                else:
                    target_url = f"{url[:-len('html')]}{fmt}"
                    if await download_and_save_file(
                        target_url,
                        http_client,
                        filename_base,
                        referer_url=url,
                        base_dir=config.data_dir,
                    ):
                        success_count += 1

            if success_count < len(config.formats):
                log.info(
                    f"Download summary for {url}: "
                    f"{success_count}/{len(config.formats)} successful"
                )

    stats = await crawler.run(build_start_urls(config))

    # Explicit completion marker: crawlee's own loggers do not propagate to
    # the root logger, so the statistics would otherwise never reach the file
    log.info(
        f"Scrape finished: {stats.requests_finished} requests finished, "
        f"{stats.requests_failed} failed, runtime {stats.crawler_runtime}\n"
        f"{stats.to_table()}"
    )
    notify_ntfy(
        f"Scrape finished (court={config.filter_court or 'all'}, "
        f"year={config.filter_year or 'all'}): "
        f"{stats.requests_finished} requests, {stats.requests_failed} failed, "
        f"runtime {stats.crawler_runtime}"
    )
    write_collection_readme(config, stats)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        raise
    except Exception as e:
        notify_ntfy(f"Scrape CRASHED: {e!r}", priority="high")
        raise
