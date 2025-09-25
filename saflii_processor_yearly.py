import asyncio
from datetime import timedelta
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import Request
from crawlee.http_clients import HttpxHttpClient
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
from bs4 import BeautifulSoup
import re
import os
import random

BASE_DATA_DIR = "saflii_data"

def get_user_filters():
    """Ask user for FILTER_COURT, FILTER_YEAR, and download format preferences"""
    print("\n--- Saflii Scraper Configuration ---")
    
    # Get court filter
    filter_court = input("Enter FILTER_COURT (e.g., 'ZAWCHC' or press Enter for all courts): ").strip()
    if not filter_court:
        filter_court = None
    
    # Get year filter
    filter_year = input("Enter FILTER_YEAR (e.g., '2024' or press Enter for all years): ").strip()
    if not filter_year:
        filter_year = None
    
    # Get format preference
    while True:
        download_format = input("Choose download format (html/pdf/rtf/all): ").strip().lower()
        if download_format in ['html', 'pdf', 'rtf', 'all']:
            break
        print("Please enter one of: html, pdf, rtf, all")
    
    print(f"\nConfiguration:")
    print(f"  FILTER_COURT: {filter_court if filter_court else 'All courts'}")
    print(f"  FILTER_YEAR: {filter_year if filter_year else 'All years'}")
    print(f"  DOWNLOAD_FORMAT: {download_format}")
    print()
    
    return filter_court, filter_year, download_format

# These will be set by user input at startup
FILTER_COURT = None
FILTER_YEAR = None
DOWNLOAD_FORMAT = None

def convert_url_format(url, target_format):
    """Convert URL from one format to another (html -> pdf/rtf)"""
    if target_format == "html":
        return url
    
    # Replace file extension
    if url.endswith('.html'):
        base_url = url[:-5]  # Remove .html
        return f"{base_url}.{target_format}"
    return url

def get_format_urls(html_url, download_format):
    """Generate list of URLs to download based on format preference"""
    if download_format == "all":
        return [
            convert_url_format(html_url, "html"),
            convert_url_format(html_url, "pdf"), 
            convert_url_format(html_url, "rtf")
        ]
    else:
        return [convert_url_format(html_url, download_format)]

def parse_saflii_url(url):
    # Updated regex to handle html, pdf, rtf extensions
    match = re.search(r"/([a-z]{2})/cases/([A-Z][A-Z0-9]+)/(\d{4})/(\d+)\.(html|pdf|rtf)$", url)
    if match:
        country, court, year, case_number, file_format = match.groups()
        citation = f"[{year}] {court} {case_number}"
        return {
            "country": country,
            "court": court,
            "year": year,
            "case_number": case_number,
            "citation": citation,
            "format": file_format
        }
    else:
        log.warning(f"URL could not be parsed: {url}")
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
        log.error(f"Error extracting title: {e}")
        return fallback_citation

def save_file(url, content, content_type="text/html"):
    """Generic file saving function for HTML, PDF, RTF"""
    log.info(f"Processing URL for saving: {url}")
    metadata = parse_saflii_url(url)
    if not metadata:
        log.warning(f"Skipping URL (no match for save logic): {url}")
        return False

    file_format = metadata["format"]
    target_dir = os.path.join(BASE_DATA_DIR, metadata["country"], metadata["court"], metadata["year"])
    os.makedirs(target_dir, exist_ok=True)
    
    # For HTML files, use title extraction, for others use citation
    if file_format == "html" and isinstance(content, str):
        filename_base = generate_filename_from_title(content, metadata["citation"])
    else:
        filename_base = metadata["citation"]
    
    file_path = os.path.join(target_dir, f"{filename_base}.{file_format}")

    if os.path.exists(file_path):
        log.info(f"File already exists: {file_path}")
        return True

    try:
        # Write mode depends on content type
        if file_format == "html":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:  # PDF, RTF - binary mode
            with open(file_path, "wb") as f:
                f.write(content)
        
        log.info(f"Saved: {file_path}")
        return True
    except Exception as e:
        log.error(f"Error saving {url}: {e}")
        return False

def save_html(url, html_content):
    """Legacy function for backwards compatibility"""
    return save_file(url, html_content, "text/html")

def save_file_with_name(url, content, filename_base):
    """Save file with custom filename base"""
    log.info(f"Processing URL for saving: {url}")
    metadata = parse_saflii_url(url)
    if not metadata:
        log.warning(f"Skipping URL (no match for save logic): {url}")
        return False

    file_format = metadata["format"]
    target_dir = os.path.join(BASE_DATA_DIR, metadata["country"], metadata["court"], metadata["year"])
    os.makedirs(target_dir, exist_ok=True)
    
    file_path = os.path.join(target_dir, f"{filename_base}.{file_format}")

    if os.path.exists(file_path):
        log.info(f"File already exists: {file_path}")
        return True

    try:
        # Write mode depends on content type
        if file_format == "html":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:  # PDF, RTF - binary mode
            with open(file_path, "wb") as f:
                f.write(content)
        
        log.info(f"Saved: {file_path}")
        return True
    except Exception as e:
        log.error(f"Error saving {url}: {e}")
        return False

async def download_and_save_file(url, http_client, filename_base):
    """Download a file (PDF/RTF) via Crawlee HttpxHttpClient and save it"""
    try:
        # Add small delay before download for anti-blocking (0.5-1.5 seconds)
        delay = random.uniform(0.5, 1.5)
        log.debug(f"Waiting {delay:.1f} seconds before downloading {url}")
        await asyncio.sleep(delay)

        # Use Crawlee's HttpxHttpClient with built-in header generation
        crawl_result = await http_client.crawl(Request.from_url(url))
        http_response = crawl_result.http_response

        if http_response.status_code >= 400:
            if http_response.status_code in [404, 410]:
                log.info(f"File not available ({http_response.status_code}): {url}")
            else:
                log.error(f"HTTP error downloading {url}: {http_response.status_code}")
            return False

        # Access content using Crawlee's HttpxResponse read method
        content = http_response.read()

        # Save the file content with provided filename
        return save_file_with_name(url, content, filename_base)

    except asyncio.TimeoutError as e:
        log.warning(f"Download timeout for {url}: {e}")
        return False
    except asyncio.CancelledError as e:
        log.warning(f"Download cancelled for {url}: {e}")
        return False
    except Exception as e:
        log.error(f"Error downloading {url}: {e}")
        return False

class SafliiCrawler(BeautifulSoupCrawler):
    pass

async def main():
    global FILTER_COURT, FILTER_YEAR, DOWNLOAD_FORMAT
    
    # Get user preferences for filters
    FILTER_COURT, FILTER_YEAR, DOWNLOAD_FORMAT = get_user_filters()
    
    # Create HttpxHttpClient with timeout, redirect settings, and SSL verification disabled
    http_client = HttpxHttpClient(
        timeout=120,  # Increased to 120-second timeout for slow downloads
        follow_redirects=True,  # Enable redirect following
        verify=False  # Disable SSL certificate verification
    )

    # Initialize crawler with anti-blocking settings
    crawler = SafliiCrawler(
        http_client=http_client,
        max_request_retries=5,  # Increase retries
        request_handler_timeout=timedelta(minutes=8),  # Increased to 8 minutes timeout for processing with delays
        use_session_pool=True  # Enable session management for consistent behavior
    )

    @crawler.router.default_handler
    async def handle_page(context: BeautifulSoupCrawlingContext):
        log.info(f"Processing page: {context.request.url}")
        
        # Add random delay at start of each request (1-3 seconds) for anti-blocking
        delay = random.uniform(1, 3)
        log.debug(f"Waiting {delay:.1f} seconds before processing...")
        await asyncio.sleep(delay)
        
        url = context.request.url
        if "databases.html" in url:
            # Stage 1: Enqueue links from table (courts only)
            await context.enqueue_links(selector="div.accordion-body table a[href]", strategy="same-origin")
        elif re.search(r"/cases/[A-Z]+/?$", url):
            if FILTER_COURT and FILTER_COURT not in url:
                log.info(f"Skipping court (filter active): {url}")
                return
            # Stage 2: Court -> Enqueue year links
            await context.enqueue_links(selector="a[href^='19'], a[href^='20']", strategy="same-origin")
        elif re.search(r"/cases/[A-Z]+/\d{4}/$", url):
            if FILTER_YEAR and FILTER_YEAR not in url:
                log.info(f"Skipping year (filter active): {url}")
                return
            # Stage 3: Year page -> Enqueue document links
            await context.enqueue_links(selector="a[href$='.html']", strategy="same-origin")
        elif re.search(r"/cases/[A-Z]+/\d{4}/\d+\.html$", url):
            # Stage 4: Document -> Download based on format preference
            urls_to_download = get_format_urls(url, DOWNLOAD_FORMAT)
            
            success_count = 0
            total_count = len(urls_to_download)
            
            # Extract title from HTML for consistent naming across all formats
            html_content = str(context.soup)
            metadata = parse_saflii_url(url)
            filename_base = generate_filename_from_title(html_content, metadata["citation"]) if metadata else "unknown"
            
            for download_url in urls_to_download:
                if download_url.endswith('.html'):
                    # HTML content is already available from crawler
                    if save_html(download_url, html_content):
                        success_count += 1
                else:
                    # Download PDF/RTF files via Crawlee HttpxHttpClient  
                    if await download_and_save_file(download_url, http_client, filename_base):
                        success_count += 1
            
            if success_count < total_count:
                log.info(f"Download summary for {url}: {success_count}/{total_count} successful")

    start_urls = ["https://www.saflii.org/content/databases.html"]
    await crawler.run(start_urls)

if __name__ == "__main__":
    asyncio.run(main())
