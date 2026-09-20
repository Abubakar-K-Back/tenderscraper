import logging

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class ScrapeError(Exception):
    pass


def _text(el):
    return el.get_text(strip=True) if el else ""


def _parse_details_cell(cell):
    """Extract title, description and category from the 'Tender Details' cell."""
    title = _text(cell.find("strong"))

    description_parts = []
    for small in cell.find_all("small", class_="text-muted"):
        classes = small.get("class", [])
        if "badge" in classes:
            continue
        text = small.get_text(strip=True)
        if text:
            description_parts.append(text)

    category = ""
    for small in cell.find_all("small", class_="badge"):
        if small.find("i") is not None:
            # badges with an icon are org/location duplicates, not category
            continue
        text = small.get_text(strip=True)
        if text:
            category = text
            break

    return title, " | ".join(description_parts), category


def _parse_org_cell(cell):
    org_span = cell.find("span", class_="tender-org")
    organization = _text(org_span)

    smalls = cell.find_all("small")
    location = _text(smalls[-1]) if smalls else ""

    return organization, location


def _parse_row(row):
    cells = row.find_all("td", recursive=False)
    if len(cells) < 8:
        return None

    tender_no = _text(cells[1].find("strong"))
    if not tender_no:
        return None

    title, description, category = _parse_details_cell(cells[2])
    organization, location = _parse_org_cell(cells[3])

    status_badges = [
        _text(span) for span in cells[4].find_all("span", class_="tender-badge")
    ]
    status = ", ".join(b for b in status_badges if b)

    advertised_date = cells[5].get_text(strip=True)

    closing_date = _text(cells[6].find("strong"))
    closing_time = _text(cells[6].find("small"))

    detail_link = cells[7].find("a")
    detail_url = ""
    if detail_link and detail_link.get("href"):
        href = detail_link["href"]
        detail_url = href if href.startswith("http") else config.SITE_BASE_URL + href

    return {
        "tender_no": tender_no,
        "title": title,
        "description": description,
        "category": category,
        "organization": organization,
        "location": location,
        "status": status,
        "advertised_date": advertised_date,
        "closing_date": closing_date,
        "closing_time": closing_time,
        "detail_url": detail_url,
    }


def fetch_page_html(page_num: int) -> str:
    url = f"{config.SITE_BASE_URL}{config.ACTIVE_TENDERS_PATH}"
    params = {"page": page_num} if page_num > 1 else {}
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if response.status_code != 200:
        raise ScrapeError(
            f"Unexpected status {response.status_code} fetching page {page_num}"
        )
    return response.text


def parse_tenders(html: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.table-card.tender-card table tbody tr")
    tenders = []
    for row in rows:
        parsed = _parse_row(row)
        if parsed:
            tenders.append(parsed)
    return tenders


def scrape_active_tenders(num_pages: int = None):
    """Scrape the first `num_pages` listing pages, newest tenders first."""
    num_pages = num_pages or config.PAGES_TO_SCRAPE
    all_tenders = []
    for page_num in range(1, num_pages + 1):
        logger.info("Fetching active tenders page %d", page_num)
        html = fetch_page_html(page_num)
        tenders = parse_tenders(html)
        if not tenders:
            logger.warning("No tenders found on page %d, stopping pagination", page_num)
            break
        all_tenders.extend(tenders)
    return all_tenders


def fetch_tender_detail_html(tender_no: str) -> str:
    url = f"{config.SITE_BASE_URL}/public/tenders/tender-details/{tender_no}"
    response = requests.get(url, headers=HEADERS, timeout=30)
    if response.status_code != 200:
        raise ScrapeError(
            f"Unexpected status {response.status_code} fetching detail for {tender_no}"
        )
    return response.text


def parse_tender_detail(html: str) -> dict:
    """Parse the label/value rows on a tender's detail page (Organization/Office
    Details, Tender Information, Important Dates, Financial Information, etc).
    Every row on that page follows the same `.detail-label` + value-span pattern,
    so this stays generic instead of hardcoding each section."""
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for item in soup.select(".list-group-item"):
        label_el = item.find(class_="detail-label")
        if not label_el:
            continue
        label = label_el.get_text(strip=True).rstrip(":")
        value_el = label_el.find_next_sibling()
        if value_el is None:
            continue
        value = value_el.get_text(" ", strip=True)
        if value:
            fields[label] = value
    return fields


def fetch_tender_detail(tender_no: str) -> dict:
    html = fetch_tender_detail_html(tender_no)
    return parse_tender_detail(html)
