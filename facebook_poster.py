import logging

import requests

import config

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 140
SEPARATOR = "-" * 40


class FacebookPostError(Exception):
    pass


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cutoff = text.rfind(" ", 0, max_len)
    if cutoff == -1:
        cutoff = max_len
    return text[:cutoff].rstrip(",.;- ") + "…"


def shorten_url(url: str, attempts: int = 2) -> str:
    """Shorten via TinyURL (free, no API key). Retries once since free
    shortener endpoints occasionally hiccup, and falls back to the original
    URL if it still fails, so a link is never dropped."""
    if not url:
        return url
    for attempt in range(attempts):
        try:
            response = requests.get(
                "https://tinyurl.com/api-create.php",
                params={"url": url},
                timeout=10,
            )
            short = response.text.strip()
            if response.status_code == 200 and short.startswith("http"):
                return short
        except requests.RequestException:
            pass
    logger.warning("URL shortening failed for %s, using original URL", url)
    return url


def _status_label(status_raw: str) -> str:
    if "Corrigendum" in status_raw:
        return "Corrigendum Issued"
    if "Cancelled" in status_raw:
        return "Cancelled"
    return "Active"


def extract_fields(tender: dict) -> dict:
    """Derive all the display fields used by both the text notice and the
    generated image, from the listing row plus the tender's detail page
    (scraper.fetch_tender_detail). Fields the site doesn't have for a given
    tender (conditional sections) fall back to "N/A" / empty so callers get
    a consistent shape."""
    detail = tender.get("detail_fields") or {}

    city = detail.get("City") or tender.get("location", "").split(" - ")[0].strip()

    department = detail.get("Organization Name") or tender.get("organization", "")

    ref_no = detail.get("Tender No / Reference No / Tender Inquiry No")
    tender_ref = tender["tender_no"]
    if ref_no and ref_no != tender["tender_no"]:
        tender_ref += f" / {ref_no}"

    category = detail.get("Procurement Category") or tender.get("category", "") or "N/A"

    deadline = tender.get("closing_date", "")
    if tender.get("closing_time"):
        deadline += f" at {tender['closing_time']}"

    bid_security = detail.get("Bid Security")
    bid_security = f"PKR {bid_security}" if bid_security else "N/A"

    bid_validity = detail.get("Bid Validity", "N/A")
    bidding_method = detail.get("Procurement Procedure", "N/A")

    location_parts = [
        detail.get("Office Name") or tender.get("organization", ""),
        detail.get("Office Address", ""),
        detail.get("City") or tender.get("location", ""),
    ]
    location = ", ".join(p for p in location_parts if p)

    contact_bits = []
    if detail.get("Contact Person"):
        contact_bits.append(detail["Contact Person"])
    reach = [v for v in [detail.get("Contact Email"), detail.get("Contact Phone")] if v]
    if reach:
        contact_bits.append(" / ".join(reach))
    inquiries = " | ".join(contact_bits)

    return {
        "city": city,
        "department": department,
        "tender_ref": tender_ref,
        "category": category,
        "status_label": _status_label(tender.get("status", "")),
        "deadline": deadline,
        "bid_security": bid_security,
        "bid_validity": bid_validity,
        "bidding_method": bidding_method,
        "location": location,
        "inquiries": inquiries,
    }


def format_tender_message(tender: dict) -> str:
    """Formal tender-notice template:

    TENDER NOTICE: [City / Region]

    Project: [Project / Tender Title]
    Department: [Organization / Authority Name]
    Tender Ref / TS No: [Reference Numbers]
    Category: [...]
    Status: [...]
    ----------------------------------------
    KEY DETAILS
    - Submission Deadline: [...]
    - Bid Security: [...]
    - Bid Validity: [...]
    - Bidding Method: [...]
    ----------------------------------------

    Location: [Office Name, Address, City]
    Inquiries: [Contact Person] | [Email / Phone]

    Full Details & Documents:
    [link]
    """
    f = extract_fields(tender)

    lines = [
        f"TENDER NOTICE: {f['city']}",
        "",
        f"Project: {_truncate(tender['title'].strip(), MAX_TITLE_LENGTH)}",
        f"Department: {f['department']}",
        f"Tender Ref / TS No: {f['tender_ref']}",
        f"Category: {f['category']}",
        f"Status: {f['status_label']}",
        "",
        SEPARATOR,
        "KEY DETAILS",
        f"- Submission Deadline: {f['deadline']}",
        f"- Bid Security: {f['bid_security']}",
        f"- Bid Validity: {f['bid_validity']}",
        f"- Bidding Method: {f['bidding_method']}",
        SEPARATOR,
        "",
        f"Location: {f['location']}",
    ]
    if f["inquiries"]:
        lines.append(f"Inquiries: {f['inquiries']}")
    lines.append("")
    lines.append("Full Details & Documents:")
    lines.append(shorten_url(tender.get("detail_url", "")))

    return "\n".join(lines)


def post_to_page(message: str) -> dict:
    if not config.FB_PAGE_ID or not config.FB_PAGE_ACCESS_TOKEN:
        raise FacebookPostError(
            "FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not configured. See .env.example."
        )

    url = f"https://graph.facebook.com/{config.FB_GRAPH_API_VERSION}/{config.FB_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": config.FB_PAGE_ACCESS_TOKEN,
    }

    response = requests.post(url, data=payload, timeout=30)
    data = response.json()

    if response.status_code != 200 or "error" in data:
        error = data.get("error", {})
        raise FacebookPostError(
            f"Facebook API error ({response.status_code}): "
            f"{error.get('message', response.text)}"
        )

    logger.info("Posted to Facebook, post id: %s", data.get("id"))
    return data


def post_photo_to_page(image_path: str, caption: str) -> dict:
    if not config.FB_PAGE_ID or not config.FB_PAGE_ACCESS_TOKEN:
        raise FacebookPostError(
            "FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not configured. See .env.example."
        )

    url = f"https://graph.facebook.com/{config.FB_GRAPH_API_VERSION}/{config.FB_PAGE_ID}/photos"
    with open(image_path, "rb") as image_file:
        files = {"source": image_file}
        payload = {"caption": caption, "access_token": config.FB_PAGE_ACCESS_TOKEN}
        response = requests.post(url, data=payload, files=files, timeout=60)

    data = response.json()
    if response.status_code != 200 or "error" in data:
        error = data.get("error", {})
        raise FacebookPostError(
            f"Facebook API error ({response.status_code}): "
            f"{error.get('message', response.text)}"
        )

    logger.info("Posted photo to Facebook, post id: %s", data.get("post_id") or data.get("id"))
    return data
