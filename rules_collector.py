# rules_collector.py
"""One-shot collector for SA Court Rules & Practice Directives (PDFs).

Sources (see "Datenquellen SA-Recht.md" in the RE3 Obsidian vault):
  - justice.gov.za/legislation/rules/rules.htm  — consolidated court rules
  - judiciary.org.za /index.php/judiciary/directives/... — practice
    directives per court/division (section pages discovered via the
    sitewide directives menu)
  - Bar Association practice manuals + court rules, via the Wayback
    Machine: the old nationalbar.co.za lost its /pdfs/ tree in the
    Wix relaunch (rsabar.net serves an empty JS-only page, the old
    file URLs soft-404 to the homepage), so the archived captures are
    the only reachable copies. Enumerated live via the CDX API, so
    newer captures are picked up automatically.

Unlike the SAFLII crawler this is not a long-running scraper: the corpus
is a few hundred PDFs that change rarely, so the intended use is an
occasional manual run (dry-run first, then --apply). Files land in their
own collection folder (one collection per corpus, next to the SAFLII
collection on the NAS), with the same inner layout convention:

    <base>/pdf/za/rules/<section>/<title> [<urlhash>].pdf

The 8-char URL hash keeps filenames unique and stable: directive titles
on the listing pages repeat (e.g. several near-identical COVID
directives per division), so the title alone cannot be the key. The
title stays first in the name because RAGFlow shows the filename to
lawyers as the source.

Usage:
    uv run python rules_collector.py                      # dry-run, all sections
    uv run python rules_collector.py --section western-cape
    uv run python rules_collector.py --apply
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
import urllib.parse

from bs4 import BeautifulSoup
from curl_cffi import requests

import saflii_utils
from saflii_utils import _INVALID_FILENAME_CHARS, MAX_FILENAME_BASE_LENGTH

log = logging.getLogger(__name__)

DEFAULT_DATA_DIR = "/Volumes/data/Work/RE3_scraper_rules_data"

JUSTICE_RULES_URL = "https://www.justice.gov.za/legislation/rules/rules.htm"
# Carries both the sitewide directives menu (section discovery) and a few
# PDFs of its own that rules.htm does not list.
JUDICIARY_SEED_URL = (
    "https://www.judiciary.org.za/index.php/news-category/"
    "625-rules-and-practice-directions"
)
DIRECTIVES_LINK_PATTERN = re.compile(r"^/index\.php/judiciary/directives/(.+)$")

# Pseudo-section slugs for the two seed pages themselves.
JUSTICE_SECTION = "consolidated-rules"
SEED_SECTION = "rules-and-practice-directions"

# Bar Association PDFs, reachable only through the Wayback Machine (see
# module docstring). Copyright of the practice manuals is unclear
# (editorial work of the Bar, not official texts) — inclusion is a
# deliberate decision by Rafael, 2026-07-18.
BAR_SECTION = "bar-association"
CDX_API_BASE = (
    "https://web.archive.org/cdx/search/cdx"
    "?output=json&fl=urlkey,timestamp,original&filter=statuscode:200"
)
WAYBACK_RAW_URL = "https://web.archive.org/web/{timestamp}id_/{original}"

REQUEST_DELAY_SECONDS = 2.5
URL_HASH_LENGTH = 8


def fetch_html(session, url):
    time.sleep(REQUEST_DELAY_SECONDS)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.text


def absolutize(base_url, href):
    """Resolve a link and percent-encode non-ASCII (some justice.gov.za
    filenames contain curly quotes); already-encoded sequences survive."""
    joined = urllib.parse.urljoin(base_url, href.strip())
    return urllib.parse.quote(joined, safe=":/?&=%()[]'")


def extract_pdf_links(page_url, html):
    """Yield (absolute_url, link_text) for every PDF linked on the page."""
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        url = absolutize(page_url, anchor["href"])
        if not urllib.parse.urlparse(url).path.lower().endswith(".pdf"):
            continue
        yield url, anchor.get_text(" ", strip=True)


def extract_section_links(html):
    """Section slugs/URLs from the sitewide directives menu, in page order."""
    soup = BeautifulSoup(html, "html.parser")
    sections = {}
    for anchor in soup.find_all("a", href=True):
        match = DIRECTIVES_LINK_PATTERN.match(anchor["href"].strip())
        if match:
            slug = match.group(1).strip("/")
            sections.setdefault(slug, f"https://www.judiciary.org.za{anchor['href'].strip()}")
    return sections


def filename_for(url, title):
    """`<title> [<urlhash>].pdf`, byte-capped with the hash always kept."""
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:URL_HASH_LENGTH]
    if not title:
        title = os.path.splitext(os.path.basename(urllib.parse.urlparse(url).path))[0]
        title = urllib.parse.unquote(title)
    cleaned = _INVALID_FILENAME_CHARS.sub("-", title).strip(" .") or "untitled"
    suffix = f" [{url_hash}]"
    budget = MAX_FILENAME_BASE_LENGTH - len(suffix.encode("utf-8"))
    head = cleaned.encode("utf-8")[:budget].decode("utf-8", "ignore").rstrip()
    return f"{head}{suffix}.pdf"


def cdx_query(session, url_pattern, extra_filter=None):
    """Wayback CDX rows [urlkey, timestamp, original] for a URL (pattern)."""
    time.sleep(REQUEST_DELAY_SECONDS)
    query = f"{CDX_API_BASE}&url={urllib.parse.quote(url_pattern, safe='')}"
    if extra_filter:
        query += f"&filter={extra_filter}"
    response = session.get(query, timeout=60)
    response.raise_for_status()
    rows = response.json()
    return rows[1:]  # row 0 is the header


def wayback_fallback_url(session, url):
    """Raw-download URL of the newest archived capture, or None.

    Rescue path for link rot on the live sites (justice.gov.za and
    judiciary.org.za both list PDFs that 404). No mimetype filter — some
    captures are stored as octet-stream; the %PDF check in download()
    guards against archived HTML error pages.
    """
    try:
        rows = cdx_query(session, url)
    except Exception as e:
        log.warning(f"CDX lookup failed for {url}: {e}")
        return None
    if not rows:
        return None
    _, timestamp, original = max(rows, key=lambda row: row[1])
    return WAYBACK_RAW_URL.format(timestamp=timestamp, original=original)


def collect_bar_documents(session):
    """Bar Association PDFs from the Wayback Machine, newest capture each.

    Returns {key_url: (section, title, download_url)}; the key is the
    stable SURT urlkey (filename hash input), the download URL points at
    the raw capture (`id_` suffix = original bytes, no archive banner).
    """
    rows = cdx_query(
        session, "nationalbar.co.za/pdfs/*", "mimetype:application/pdf"
    )
    newest = {}
    for urlkey, timestamp, original in rows:
        if urlkey not in newest or timestamp > newest[urlkey][0]:
            newest[urlkey] = (timestamp, original)
    documents = {}
    for urlkey, (timestamp, original) in newest.items():
        basename = os.path.basename(urllib.parse.urlparse(original).path)
        title = urllib.parse.unquote(os.path.splitext(basename)[0])
        download_url = WAYBACK_RAW_URL.format(timestamp=timestamp, original=original)
        documents[urlkey] = (BAR_SECTION, title, download_url)
    log.info(f"Wayback CDX lists {len(documents)} Bar Association PDFs")
    return documents


def collect_documents(session, section_filter=None):
    """Walk all sources; return {key_url: (section, title, download_url)}.

    First occurrence of a URL wins so the canonical consolidated-rules
    listing takes precedence over duplicates on directive pages.
    """
    documents = {}

    def add_page(section, page_url, html):
        for url, title in extract_pdf_links(page_url, html):
            documents.setdefault(url, (section, title, url))

    def wanted(slug):
        return section_filter is None or section_filter in slug

    log.info(f"Fetching seed: {JUDICIARY_SEED_URL}")
    seed_html = fetch_html(session, JUDICIARY_SEED_URL)
    sections = extract_section_links(seed_html)
    log.info(f"Discovered {len(sections)} directives sections")

    if wanted(JUSTICE_SECTION):
        log.info(f"Fetching {JUSTICE_RULES_URL}")
        add_page(JUSTICE_SECTION, JUSTICE_RULES_URL, fetch_html(session, JUSTICE_RULES_URL))
    if wanted(SEED_SECTION):
        add_page(SEED_SECTION, JUDICIARY_SEED_URL, seed_html)

    for slug, url in sections.items():
        if not wanted(slug):
            continue
        log.info(f"Fetching section: {slug}")
        try:
            add_page(slug, url, fetch_html(session, url))
        except Exception as e:
            log.error(f"Section {slug} failed, continuing: {e}")

    if wanted(BAR_SECTION):
        try:
            for key, doc in collect_bar_documents(session).items():
                documents.setdefault(key, doc)
        except Exception as e:
            log.error(f"Bar Association source failed, continuing: {e}")
    return documents


def target_path(base_dir, section, url, title):
    return os.path.join(base_dir, "pdf", "za", "rules", section, filename_for(url, title))


def download(session, url, referer, path):
    time.sleep(REQUEST_DELAY_SECONDS)
    response = session.get(url, headers={"Referer": referer}, timeout=120)
    response.raise_for_status()
    # Dead file URLs often soft-404 into an HTML page with status 200
    # (nationalbar.co.za does exactly that) — never save those as .pdf.
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"Response is not a PDF (starts with {response.content[:8]!r})")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "wb") as f:
            f.write(response.content)
    except OSError:
        saflii_utils._remove_partial_file(path)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="actually download (default: dry-run)")
    parser.add_argument("--section", help="only sections whose slug contains this substring")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("RULES_DATA_DIR", DEFAULT_DATA_DIR),
        help="collection base directory (default: $RULES_DATA_DIR or NAS mount)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    session = requests.Session(impersonate="chrome")
    documents = collect_documents(session, args.section)

    new, existing, failed = [], [], []
    for key, (section, title, download_url) in documents.items():
        path = target_path(args.data_dir, section, key, title)
        (existing if os.path.exists(path) else new).append((download_url, section, path))

    per_section = {}
    for _, section, _ in new:
        per_section[section] = per_section.get(section, 0) + 1
    log.info(f"Found {len(documents)} PDFs: {len(existing)} already present, {len(new)} new")
    for section, count in sorted(per_section.items()):
        log.info(f"  {count:4d} new in {section}")

    if not args.apply:
        for download_url, section, path in new:
            print(f"DRY-RUN would download: {download_url}\n              -> {path}")
        if new:
            print(f"\nDry-run only. Re-run with --apply to download {len(new)} files.")
        return

    referer = JUDICIARY_SEED_URL
    for i, (download_url, section, path) in enumerate(new, 1):
        log.info(f"[{i}/{len(new)}] {download_url}")
        try:
            download(session, download_url, referer, path)
        except Exception as e:
            rescued = False
            if "web.archive.org" not in download_url:
                fallback = wayback_fallback_url(session, download_url)
                if fallback:
                    log.info(f"Live download failed ({e}), retrying from Wayback: {fallback}")
                    try:
                        download(session, fallback, referer, path)
                        rescued = True
                    except Exception as fallback_error:
                        e = fallback_error
            if not rescued:
                log.error(f"Download failed for {download_url}: {e}")
                failed.append(download_url)
    log.info(
        f"Done: {len(new) - len(failed)} downloaded, {len(failed)} failed, "
        f"{len(existing)} skipped (already present)"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
