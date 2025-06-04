import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import html2text


def sanitize_filename(filename):
    """
    Replaces all critical characters with underscores
    so that the filename can be used safely on most file systems.
    """
    safe_str = re.sub(r"[^\w\-\(\)\[\]\s]", "_", filename)
    safe_str = re.sub(r"[_\s]+", "_", safe_str).strip("_")
    return safe_str[:120]


def create_session_with_retries(
    total_retries=5, backoff_factor=1, status_forcelist=(500, 502, 503, 504), timeout=30
):
    session = requests.Session()
    retries = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    def request_with_timeout(method, url, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = timeout
        return session.request(method, url, **kwargs)

    session.request = request_with_timeout
    return session


session = create_session_with_retries(total_retries=3, backoff_factor=2, timeout=30)


def fetch_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }
    response = session.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def get_journal_links(main_url):
    html_content = fetch_html(main_url)
    soup = BeautifulSoup(html_content, "html.parser")

    journal_links = {}
    for td_tag in soup.find_all("td"):
        link_tag = td_tag.find("a", href=True)
        if link_tag:
            journal_title = link_tag.get_text(strip=True)
            relative_journal_url = link_tag["href"]
            full_journal_url = urljoin(main_url, relative_journal_url)
            journal_links[journal_title] = full_journal_url
    return journal_links


def get_year_links(journal_url):
    """
    Loads the specific journal page and extracts links to each year,
    but only from the <h3> that mentions 'Articles for the years'.
    Ensures that journal_url has a trailing slash so urljoin works properly.
    """
    # **WICHTIG**: trailing slash erzwingen, um "ADRY/2013/" statt "2013/" zu bekommen
    if not journal_url.endswith("/"):
        journal_url += "/"

    html_content = fetch_html(journal_url)
    soup = BeautifulSoup(html_content, "html.parser")
    year_links = []

    h3_elements = soup.find_all("h3")
    for h3 in h3_elements:
        if "Articles for the years" in h3.get_text():
            for link_tag in h3.find_all("a", href=True):
                href = link_tag["href"]
                if href.endswith("/"):
                    full_year_url = urljoin(journal_url, href)
                    year_links.append(full_year_url)
            break
    return year_links


def get_article_links(year_url):
    """
    Extract all article links and their text from the year's page.
    Also ensure trailing slash on year_url for urljoin.
    """
    if not year_url.endswith("/"):
        year_url += "/"

    html_content = fetch_html(year_url)
    soup = BeautifulSoup(html_content, "html.parser")
    article_data = []

    for li_tag in soup.find_all("li", class_="make-database"):
        a_tag = li_tag.find("a", href=True)
        if a_tag:
            relative_article_link = a_tag["href"]
            full_article_url = urljoin(year_url, relative_article_link)
            link_text = a_tag.get_text(strip=True)
            article_data.append({"url": full_article_url, "title": link_text})
    return article_data


def convert_html_to_markdown(html_file_path, md_file_path):
    with open(html_file_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False

    markdown_content = converter.handle(html_content)
    os.makedirs(os.path.dirname(md_file_path), exist_ok=True)
    with open(md_file_path, "w", encoding="utf-8") as md_file:
        md_file.write(markdown_content)


def run_scraper():
    main_url = "https://www.saflii.org/content/databases.html"
    journal_name = "South Africa: African Disability Rights Yearbook"

    all_journals = get_journal_links(main_url)
    if journal_name not in all_journals:
        print(f"Journal '{journal_name}' not found.")
        return

    # Journal-URL
    journal_url = all_journals[journal_name]
    print(f"Selected Journal: {journal_name} -> {journal_url}")

    # Hol dir "DATABASENAME" aus der URL (z.B. "ADRY")
    databasename = journal_url.rstrip("/").split("/")[-1]

    # Jahres-Links
    year_urls = get_year_links(journal_url)

    for year_url in year_urls:
        print(f"Scraping year: {year_url}")
        year_str = year_url.rstrip("/").split("/")[-1]

        articles = get_article_links(year_url)

        # Verzeichnis: downloaded_articles/www.saflii.org/DATABASENAME/YEAR
        base_folder = os.path.join(
            "downloaded_articles", "www.saflii.org", databasename, year_str
        )

        for article_info in articles:
            article_url = article_info["url"]
            article_title = article_info["title"]
            safe_name = sanitize_filename(article_title)

            html_file_path = os.path.join(base_folder, f"{safe_name}.html")
            md_file_path = os.path.join(base_folder, f"{safe_name}.md")

            # HTML herunterladen
            html_content = fetch_html(article_url)
            os.makedirs(os.path.dirname(html_file_path), exist_ok=True)
            with open(html_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Markdown konvertieren
            convert_html_to_markdown(html_file_path, md_file_path)
            print(f"Saved & converted: {md_file_path}")


if __name__ == "__main__":
    run_scraper()
