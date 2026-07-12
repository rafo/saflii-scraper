# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python web scraper for the South African Legal Information Institute (Saflii) database at https://www.saflii.org/. The scraper extracts legal documents, court cases, journals, gazettes, and rolls from South African courts and legal institutions.

## Commands

### Development Setup
```bash
# Install dependencies using uv (Python package manager)
uv sync
```

### Running the Scrapers
```bash
# Run the main targeted scraper (specific court/year range)
python main.py

# Run the comprehensive yearly processor (all courts and years)
python saflii_processor_yearly.py
```

### Docker Development
```bash
# Start the kotaemon service (document analysis platform)
docker-compose up -d
```

## Architecture

### Core Components

1. **main.py** - Primary scraper targeting a specific court/year
   - Uses `BeautifulSoupCrawler` directly
   - Starts at the year index page and enqueues the actual document links
   - Rate-limited via `ConcurrencySettings` (max 3 parallel, 60 requests/minute)

2. **saflii_processor_yearly.py** - Comprehensive hierarchical scraper
   - Follows the complete Saflii site structure:
     1. Starts at databases.html (institution list)
     2. Navigates to court/institution pages
     3. Follows year links for each court
     4. Downloads individual case documents (HTML, PDF, RTF, or all)
   - Interactive startup prompts for court filter, year filter, and download format
     (collected into a `ScraperConfig` dataclass)

3. **saflii_utils.py** - Shared utility functions (single source of truth, used by both scrapers)
   - `parse_saflii_url()` - Extracts metadata (country, court, year, case number, format) from URLs
   - `generate_filename_from_title()` / `sanitize_filename()` - Create safe, length-capped filenames from HTML titles
   - `build_file_path()` - Computes the target path (used to skip downloads for existing files)
   - `save_file()` / `process_saflii_page()` - Save documents with proper directory structure

### Data Structure

Documents are saved in a hierarchical structure:
```
saflii_data/
├── za/              # Country code (South Africa)
│   └── ZAWCHC/      # Court code
│       └── 2024/    # Year
│           ├── [Case Title 1].html
│           └── [Case Title 2].html
```

### Key Dependencies

- **Crawlee** - Web crawling framework with BeautifulSoup integration
- **BeautifulSoup4** - HTML parsing and processing

### URL Pattern Recognition

The scraper handles these URL patterns:
- Database index: `https://www.saflii.org/content/databases.html`
- Court pages: `https://www.saflii.org/za/cases/{COURT_CODE}/`
- Year pages: `https://www.saflii.org/za/cases/{COURT_CODE}/{YEAR}/`
- Documents: `https://www.saflii.org/za/cases/{COURT_CODE}/{YEAR}/{NUMBER}.html`

### Anti-Blocking

- saflii.org returns 403 for plain HTTP clients (curl, httpx); both scrapers therefore use
  `CurlImpersonateHttpClient(impersonate="chrome")` for browser-like TLS fingerprints
- PDF/RTF downloads additionally require a `Referer` header (the document's HTML URL),
  otherwise the server responds with 403

### Error Handling

- HTTP errors (4xx/5xx) are logged with warnings
- Missing HTML content is handled gracefully
- File system operations include proper exception handling
- Existing files are skipped to avoid duplication
- Partial writes are cleaned up on failure

### Configuration

`saflii_processor_yearly.py` asks interactively at startup (see `get_user_config()`):
- Court filter (e.g., "ZAWCHC", exact match) - empty for all courts
- Year filter (e.g., "2024", exact match) - empty for all years
- Download format: html, pdf, rtf, or all

Constants:
- `BASE_DATA_DIR` in `saflii_utils.py` - Output directory ("saflii_data", shared by both scrapers)
- `MAX_REQUESTS_PER_CRAWL` in `saflii_processor_yearly.py` - Safety limit (100,000)

In `main.py`:
- `COUNTRY_CODE`, `COURT_CODE`, `YEAR` - Target parameters
- `MAX_REQUESTS_PER_CRAWL` - Request limit (2000)