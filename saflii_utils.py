# saflii_utils.py
import logging
import os
import re

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_DATA_DIR = "saflii_data"

# Characters that are invalid or problematic in filenames across platforms
_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
# Filename base budget in bytes: common filesystems allow 255 bytes per
# name; leave room for the extension. Kept as high as possible because
# lawyers need the full document title (RAGFlow shows it as the source).
MAX_FILENAME_BASE_LENGTH = 240

# Matches document URLs like /za/cases/ZAWCHC/2024/123.html (or .pdf/.rtf).
# The category segment ("cases", "other", "gaz", "journals", ...) separates
# SAFLII's document types and maps to distinct RAGFlow datasets. Collection
# codes outside "cases" contain lowercase letters (ZACCRolls, ZAGovGaz).
DOCUMENT_URL_PATTERN = re.compile(
    r"/([a-z]{2})/([a-z]+)/([A-Z][A-Za-z0-9]*)/(\d{4})/(\d+)\.(html|pdf|rtf)$"
)


def parse_saflii_url(url):
    """Extract metadata (country, category, court, year, case number, format) from a document URL."""
    match = DOCUMENT_URL_PATTERN.search(url)
    if not match:
        log.warning(f"URL could not be parsed: {url}")
        return None
    country, category, court, year, case_number, file_format = match.groups()
    return {
        "country": country,
        "category": category,
        "court": court,
        "year": year,
        "case_number": case_number,
        "citation": f"[{year}] {court} {case_number}",
        "format": file_format,
    }


def sanitize_filename(name, citation):
    """Strip invalid characters and cap the byte length.

    If the name is too long, the tail from the neutral citation onward
    (parallel citations and judgment date) is preserved and the party
    names are truncated instead — the citation and date must survive.
    """
    cleaned = _INVALID_FILENAME_CHARS.sub("-", name).strip(" .")
    if not cleaned:
        return citation
    if citation not in cleaned:
        cleaned = f"{cleaned} {citation}"
    if len(cleaned.encode("utf-8")) <= MAX_FILENAME_BASE_LENGTH:
        return cleaned
    tail = cleaned[cleaned.rfind(citation) :]
    head_budget = MAX_FILENAME_BASE_LENGTH - len(tail.encode("utf-8")) - 1
    if head_budget <= 0:
        return tail
    head = (
        cleaned.encode("utf-8")[:head_budget].decode("utf-8", "ignore").rstrip()
    )
    return f"{head} {tail}"


def generate_filename_from_title(html_content, fallback_citation):
    """Extract the HTML title and turn it into a safe filename base."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            if title_text:
                return sanitize_filename(title_text, fallback_citation)
        log.warning(f"No usable title found, using fallback: {fallback_citation}")
    except Exception as e:
        log.error(f"Error extracting title: {e}. Using fallback: {fallback_citation}")
    return fallback_citation


def build_file_path(metadata, filename_base, base_dir=BASE_DATA_DIR):
    """Target path for a document: base_dir/format/country/category/court/year/name.format

    The top format level keeps the RAGFlow-facing PDF tree free of the
    HTML/RTF companions so whole folders can be ingested per dataset.
    The country level (e.g. "za") is kept because SAFLII also hosts case
    law from other African countries; the category level ("cases",
    "gaz", ...) keeps document types apart for per-dataset ingestion.
    """
    target_dir = os.path.join(
        base_dir,
        metadata["format"],
        metadata["country"],
        metadata["category"],
        metadata["court"],
        metadata["year"],
    )
    return os.path.join(target_dir, f"{filename_base}.{metadata['format']}")


def _remove_partial_file(file_path):
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            log.warning(f"Removed partially written file: {file_path}")
        except OSError as e:
            log.error(f"Could not remove partially written file {file_path}: {e}")


def save_file(url, content, filename_base=None, base_dir=BASE_DATA_DIR):
    """Save document content (str is written as UTF-8 text, bytes as binary).

    Skips files that already exist. Returns True on success or skip.
    """
    metadata = parse_saflii_url(url)
    if not metadata:
        log.warning(f"Skipping URL (no match for save logic): {url}")
        return False

    if filename_base is None:
        if metadata["format"] == "html" and isinstance(content, str):
            filename_base = generate_filename_from_title(content, metadata["citation"])
        else:
            filename_base = metadata["citation"]

    file_path = build_file_path(metadata, filename_base, base_dir)
    if os.path.exists(file_path):
        log.info(f"File already exists, skipping: {file_path}")
        return True

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if isinstance(content, str):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(file_path, "wb") as f:
                f.write(content)
        log.info(f"Saved: {file_path}")
        return True
    except OSError as e:
        log.error(f"Error saving {file_path}: {e}")
        _remove_partial_file(file_path)
        return False


def process_saflii_page(url, html_content, base_dir=BASE_DATA_DIR):
    """Save a downloaded HTML document page."""
    return save_file(url, html_content, base_dir=base_dir)
