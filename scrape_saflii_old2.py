import requests
from bs4 import BeautifulSoup
import os
import html2text
from urllib.parse import urljoin


def get_journal_links(main_url):
    """
    Loads the main page that lists various legal databases (journals).
    Extracts and returns the links to the desired journals.

    :param main_url: The URL of the page that lists different databases.
    :type main_url: str
    :return: A dictionary mapping journal titles to journal URLs.
    :rtype: dict
    """
    # Set a custom header to pretend we are a "normal" browser
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(main_url, headers=headers, timeout=10)
    response.raise_for_status()  # Raise exception if the request fails

    soup = BeautifulSoup(response.text, "html.parser")

    journal_links = {}

    # We look for <td><a href="/za/journals/...">Some Journal Name</a></td>
    # Then build the full link using urljoin
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
    but only from the relevant <h3> block that mentions 'Articles for the years'.

    :param journal_url: URL pointing to a specific journal overview (e.g., ADRY).
    :type journal_url: str
    :return: A list of full URLs for each year in the journal.
    :rtype: list
    """
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(journal_url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    year_links = []

    # Finde alle <h3>-Elemente und checke, ob "Articles for the years" im Text steht
    h3_elements = soup.find_all("h3")
    for h3 in h3_elements:
        if "Articles for the years" in h3.get_text():
            # Nur innerhalb dieses <h3> suchen wir die Jahres-Links
            for link_tag in h3.find_all("a", href=True):
                href = link_tag["href"]
                if href.endswith("/"):
                    # Bau die absolute URL
                    full_year_url = urljoin(journal_url, href)
                    year_links.append(full_year_url)
            # Wir brechen ab, nachdem wir den relevanten Block verarbeitet haben
            break

    return year_links


def get_article_links(year_url):
    """
    From the page of a specific year, extract all article links.

    :param year_url: URL of a year's article overview.
    :type year_url: str
    :return: A list of full URLs for each article.
    :rtype: list
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(year_url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    article_links = []

    # Looking for <li class="make-database"><a href="../2013/1.html" ...>
    for li_tag in soup.find_all("li", class_="make-database"):
        a_tag = li_tag.find("a", href=True)
        if a_tag:
            relative_article_link = a_tag["href"]
            full_article_url = urljoin(year_url, relative_article_link)
            article_links.append(full_article_url)

    return article_links


def download_html(article_url, download_folder):
    """
    Downloads the HTML from the specified article URL and saves it locally.

    :param article_url: Full URL to the article HTML page.
    :type article_url: str
    :param download_folder: Path to the folder where the HTML file should be saved.
    :type download_folder: str
    :return: The local path to the saved HTML file.
    :rtype: str
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(article_url, headers=headers, timeout=10)
    response.raise_for_status()

    file_name = article_url.strip("/").split("/")[-1]

    os.makedirs(download_folder, exist_ok=True)

    local_file_path = os.path.join(download_folder, file_name)
    with open(local_file_path, "w", encoding="utf-8") as file:
        file.write(response.text)

    return local_file_path


def convert_html_to_markdown(html_file_path, md_file_path):
    """
    Converts a local HTML file to Markdown and saves the result.

    :param html_file_path: Path to the local HTML file.
    :type html_file_path: str
    :param md_file_path: Path where the Markdown file will be stored.
    :type md_file_path: str
    """
    import html2text  # ensure installed via pip install html2text

    os.makedirs(os.path.dirname(md_file_path), exist_ok=True)

    with open(html_file_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False

    markdown_content = converter.handle(html_content)

    with open(md_file_path, "w", encoding="utf-8") as md_file:
        md_file.write(markdown_content)


def run_scraper():
    """
    Executes the entire scraping workflow:
    1. Get all journal links from the main page.
    2. Select the desired journal link (e.g. 'South Africa: African Disability Rights Yearbook').
    3. Get the year links for that journal.
    4. For each year, get article links, download them, and convert to Markdown.
    """
    main_url = "https://www.saflii.org/content/databases.html"
    all_journals = get_journal_links(main_url)

    journal_name = "South Africa: African Disability Rights Yearbook"
    if journal_name not in all_journals:
        print(f"Journal '{journal_name}' not found on the main page. Available keys:")
        for key in all_journals.keys():
            print("  -", key)
        return

    journal_url = all_journals[journal_name]
    print(f"Selected Journal: {journal_name} -> {journal_url}")

    year_urls = get_year_links(journal_url)

    for year_url in year_urls:
        print(f"Scraping year: {year_url}")
        year_str = year_url.strip("/").split("/")[-1]

        base_folder = os.path.join(
            "downloaded_articles", journal_name.replace(" ", "_"), year_str
        )
        html_folder = os.path.join(base_folder, "html")
        md_folder = os.path.join(base_folder, "md")

        article_urls = get_article_links(year_url)

        for article_url in article_urls:
            html_file_path = download_html(article_url, html_folder)
            file_name_without_extension = os.path.splitext(
                os.path.basename(html_file_path)
            )[0]
            md_file_name = file_name_without_extension + ".md"
            md_file_path = os.path.join(md_folder, md_file_name)

            convert_html_to_markdown(html_file_path, md_file_path)
            print(f"Article downloaded and converted to Markdown: {md_file_path}")


if __name__ == "__main__":
    run_scraper()
