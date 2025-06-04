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
    response = requests.get(main_url, timeout=10)
    response.raise_for_status()  # Raise exception if the request fails

    soup = BeautifulSoup(response.text, "html.parser")

    # Create a dictionary to store journal links
    # Example: { 'South Africa: African Disability Rights Yearbook': 'https://www.saflii.org/za/journals/ADRY' }
    journal_links = {}

    # We look for <td><a href="/za/journals/...">Some Journal Name</a></td>
    # Then build the full link using urljoin
    for td_tag in soup.find_all("td"):
        link_tag = td_tag.find("a", href=True)
        if link_tag:
            journal_title = link_tag.get_text(strip=True)
            relative_journal_url = link_tag["href"]
            full_journal_url = urljoin(main_url, relative_journal_url)
            # Filter or store the desired journals
            # In this example, we store them all, but you might want to filter by name
            journal_links[journal_title] = full_journal_url

    return journal_links


def get_year_links(journal_url):
    """
    Loads the specific journal page and extracts links to each year.

    :param journal_url: URL pointing to a specific journal overview (e.g., ADRY).
    :type journal_url: str
    :return: A list of full URLs for each year in the journal.
    :rtype: list
    """
    response = requests.get(journal_url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    year_links = []

    # Based on the example, the years are in <a href="2013/">2013</a>
    # We want to build the absolute URLs for each year.
    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]
        # If the link is a year like "2013/", we store it
        # We can do a simple check if it looks like a year or if it ends with '/'
        if href.endswith("/"):
            full_year_url = urljoin(journal_url, href)
            year_links.append(full_year_url)

    return year_links


def get_article_links(year_url):
    """
    From the page of a specific year, extract all article links.

    :param year_url: URL of a year's article overview.
    :type year_url: str
    :return: A list of full URLs for each article.
    :rtype: list
    """
    response = requests.get(year_url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    article_links = []

    # Look for <li class="make-database"><a href="../2013/1.html">...</a></li>
    # We'll retrieve each link and build the absolute URL
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
    response = requests.get(article_url, timeout=10)
    response.raise_for_status()

    # The filename could be the last part of the URL, e.g. '1.html'
    file_name = article_url.strip("/").split("/")[-1]

    # Create folder if it doesn't exist
    os.makedirs(download_folder, exist_ok=True)

    # Save HTML
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
    # Create the folder for md file if it doesn't exist
    os.makedirs(os.path.dirname(md_file_path), exist_ok=True)

    with open(html_file_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()

    # Use html2text to convert HTML to markdown
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False  # We want to keep links in the markdown
    h2t.ignore_images = False  # If we want images to be preserved as Markdown

    markdown_content = h2t.handle(html_content)

    # Save the markdown
    with open(md_file_path, "w", encoding="utf-8") as md_file:
        md_file.write(markdown_content)


def run_scraper():
    """
    Executes the entire scraping workflow:
    1. Get all journal links from the main page.
    2. Select the desired journal link (in this case, ADRY).
    3. Get the year links for that journal.
    4. For each year, get article links, download them, and convert to Markdown.
    """
    main_url = "https://www.saflii.org/content/databases.html"
    all_journals = get_journal_links(main_url)

    # Identify the exact name of the desired journal, e.g. "South Africa: African Disability Rights Yearbook"
    # This name must match what was found on the main page
    journal_name = "South Africa: African Disability Rights Yearbook"
    if journal_name not in all_journals:
        print(f"Journal '{journal_name}' not found on the main page.")
        return

    journal_url = all_journals[journal_name]
    print(f"Selected Journal: {journal_name} -> {journal_url}")

    # Get the list of year links
    year_urls = get_year_links(journal_url)

    for year_url in year_urls:
        print(f"Scraping year: {year_url}")

        # Extract the year from the URL path for folder naming
        # e.g. 'https://www.saflii.org/za/journals/ADRY/2013/'
        year_str = year_url.strip("/").split("/")[-1]

        # Prepare local folder to store HTML and Markdown
        base_folder = os.path.join(
            "downloaded_articles", journal_name.replace(" ", "_"), year_str
        )
        html_folder = os.path.join(base_folder, "html")
        md_folder = os.path.join(base_folder, "md")

        article_urls = get_article_links(year_url)

        for article_url in article_urls:
            # Download each article as HTML
            html_file_path = download_html(article_url, html_folder)

            # Convert the downloaded HTML file to Markdown
            file_name_without_extension = os.path.splitext(
                os.path.basename(html_file_path)
            )[0]
            md_file_name = file_name_without_extension + ".md"
            md_file_path = os.path.join(md_folder, md_file_name)

            convert_html_to_markdown(html_file_path, md_file_path)

            print(f"Article downloaded and converted to Markdown: {md_file_path}")


if __name__ == "__main__":
    run_scraper()
