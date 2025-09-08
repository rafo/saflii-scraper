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

1. **main.py** - Primary scraper targeting specific court documents
   - Uses `SafliiHtmlCrawler` class extending BeautifulSoupCrawler
   - Configured for targeted scraping (specific court, year, case number range)
   - Includes random delays (1-3 seconds) between requests
   - Processes 900 documents with 2 retry attempts

2. **saflii_processor_yearly.py** - Comprehensive hierarchical scraper
   - Follows the complete Saflii site structure:
     1. Starts at databases.html (institution list)
     2. Navigates to court/institution pages
     3. Follows year links for each court
     4. Downloads individual case documents
   - Supports filtering by court (`FILTER_COURT`) and year (`FILTER_YEAR`)

3. **saflii_utils.py** - Core utility functions
   - `parse_saflii_url()` - Extracts metadata (country, court, year, case number) from URLs
   - `generate_filename_from_title()` - Creates filenames from HTML title tags
   - `process_saflii_page()` - Saves HTML content with proper directory structure

### Data Structure

Documents are saved in a hierarchical structure:
```
saflii_daten/
├── za/              # Country code (South Africa)
│   └── ZAWCHC/      # Court code
│       └── 2024/    # Year
│           ├── [Case Title 1].html
│           └── [Case Title 2].html
```

### Key Dependencies

- **Crawlee** - Web crawling framework with BeautifulSoup integration
- **BeautifulSoup4** - HTML parsing and processing
- **Requests** - HTTP library (though primarily using Crawlee's built-in capabilities)

### URL Pattern Recognition

The scraper handles these URL patterns:
- Database index: `https://www.saflii.org/content/databases.html`
- Court pages: `https://www.saflii.org/za/cases/{COURT_CODE}/`
- Year pages: `https://www.saflii.org/za/cases/{COURT_CODE}/{YEAR}/`
- Documents: `https://www.saflii.org/za/cases/{COURT_CODE}/{YEAR}/{NUMBER}.html`

### Error Handling

- HTTP errors (4xx/5xx) are logged with warnings
- Missing HTML content is handled gracefully
- File system operations include proper exception handling
- Existing files are skipped to avoid duplication
- Partial writes are cleaned up on failure

### Configuration

Key configuration variables in `saflii_processor_yearly.py`:
- `FILTER_COURT` - Restrict to specific court (e.g., "ZAWCHC")
- `FILTER_YEAR` - Restrict to specific year (e.g., "2024")
- `BASE_DATA_DIR` - Output directory ("saflii_daten")

In `main.py`:
- `country_code`, `court_code`, `year_str` - Target parameters
- `max_requests_per_crawl` - Request limit (900)
- `max_request_retries` - Retry attempts (2)