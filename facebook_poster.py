import logging
import json
import re
from datetime import datetime

import requests

import config

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 110
MAX_DIGEST_TITLE = 88


class FacebookPostError(Exception):
    pass


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cutoff = text.rfind(" ", 0, max_len)
    if cutoff == -1:
        cutoff = max_len
    return text[:cutoff].rstrip(",.;- ") + "…"


def _clean_money(raw: str) -> str:
    """Turn '20,000,000.00' into 'PKR 20,000,000'."""
    text = (raw or "").strip()
    if not text or text in ("0", "0.0", "0.00", "N/A"):
        return ""
    text = re.sub(r"^PKR\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\.00$", "", text)
    return f"PKR {text}" if text else ""


def _short_deadline(raw: str) -> str:
    """'October 05, 2026 at 11:00 AM' → '5 Oct, 11am'."""
    text = (raw or "").strip()
    if not text:
        return ""

    date_part = text
    time_part = ""
    if re.search(r"\s+at\s+", text, flags=re.IGNORECASE):
        date_part, time_part = re.split(r"\s+at\s+", text, maxsplit=1, flags=re.IGNORECASE)

    parsed = None
    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %B %Y",
    ):
        try:
            parsed = datetime.strptime(date_part.strip(), fmt)
            break
        except ValueError:
            continue

    if not parsed:
        return text

    day = parsed.day  # no leading zero
    mon = parsed.strftime("%b")
    short = f"{day} {mon}"

    time_part = time_part.strip()
    if time_part:
        tm = None
        for fmt in ("%I:%M %p", "%H:%M", "%I %p"):
            try:
                tm = datetime.strptime(time_part, fmt)
                break
            except ValueError:
                continue
        if tm:
            hour = tm.strftime("%I").lstrip("0") or "0"
            minute = tm.minute
            ampm = tm.strftime("%p").lower()
            short += f", {hour}:{minute:02d}{ampm}" if minute else f", {hour}{ampm}"
        else:
            short += f", {time_part}"

    return short


def shorten_url(url: str, attempts: int = 2) -> str:
    """Kept for compatibility; captions use the original PPRA URL (more trusted)."""
    if not url:
        return url
    for _attempt in range(attempts):
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
    return url


def _status_label(status_raw: str) -> str:
    if "Corrigendum" in (status_raw or ""):
        return "Corrigendum"
    if "Cancelled" in (status_raw or ""):
        return "Cancelled"
    return "Active"


def extract_fields(tender: dict) -> dict:
    """Display fields from listing + detail page."""
    detail = tender.get("detail_fields") or {}

    city = (
        detail.get("City")
        or tender.get("city")
        or tender.get("location", "").split(" - ")[0].strip()
    )

    department = detail.get("Organization Name") or tender.get("organization", "")

    category = (
        detail.get("Procurement Category")
        or tender.get("procurement_category")
        or tender.get("category", "")
        or ""
    )

    sector = detail.get("Sector") or tender.get("sector") or ""

    deadline = detail.get("Closing Date & Time") or ""
    if not deadline:
        deadline = tender.get("closing_date", "")
        if tender.get("closing_time"):
            deadline = f"{deadline} at {tender['closing_time']}".strip()

    bid_security = _clean_money(detail.get("Bid Security", ""))
    bid_validity = (detail.get("Bid Validity") or "").strip()
    bidding_method = (
        detail.get("Procurement Procedure") or detail.get("Method") or ""
    ).strip()

    return {
        "city": city,
        "department": department,
        "category": category,
        "sector": sector,
        "status_label": _status_label(tender.get("status", "")),
        "deadline": deadline,
        "bid_security": bid_security or "Not listed",
        "bid_validity": bid_validity or "Not listed",
        "bidding_method": bidding_method or "Not listed",
    }


def format_tender_message(tender: dict, *, spotlight: bool = False) -> str:
    """Mobile-first caption: hook in the first 2 lines (before 'See more')."""
    f = extract_fields(tender)
    title = _truncate((tender.get("title") or "").strip(), MAX_TITLE_LENGTH)
    link = tender.get("detail_url") or ""
    city = f["city"] or "Pakistan"
    sector = f["sector"] or f["category"] or "Tender"

    hook = f"{'Spotlight · ' if spotlight else ''}{city} · {sector}"
    closes = _short_deadline(f["deadline"])
    lines = [
        hook,
        f"Closes {closes}" if closes else "",
        "",
        title,
        "",
        f["department"],
    ]

    facts = []
    if f["bid_security"] and f["bid_security"] != "Not listed":
        facts.append(f"Bid security {f['bid_security']}")
    # Bid validity stays on the image only — skip in caption.
    if f["status_label"] == "Corrigendum":
        facts.append("Updated notice (corrigendum)")
    if facts:
        lines.append(" · ".join(facts))

    lines.extend(["", "Apply here:", link] if link else [""])
    lines.extend(
        [
            "",
            "Follow for Islamabad, Lahore and Karachi tenders.",
            "Share with someone who bids this week.",
        ]
    )
    return "\n".join(line for line in lines if line is not None).replace("\n\n\n", "\n\n")


def format_digest_message(niche_label: str, tenders: list) -> str:
    """Scannable digest: one tender = a few short lines, then the apply link."""
    today = datetime.now().strftime("%d %b %Y")
    cities = []
    for tender in tenders:
        city = extract_fields(tender)["city"]
        if city and city not in cities:
            cities.append(city)
    city_bit = ", ".join(cities) if cities else "Islamabad, Lahore & Karachi"

    lines = [
        f"{niche_label} · {today}",
        f"{len(tenders)} new tender{'s' if len(tenders) != 1 else ''} · {city_bit}",
        "",
    ]

    for i, tender in enumerate(tenders, start=1):
        f = extract_fields(tender)
        title = _truncate((tender.get("title") or "").strip(), MAX_DIGEST_TITLE)
        city = f["city"] or ""
        closes = _short_deadline(f["deadline"])
        lines.append(f"{i}. {title}")
        if f["department"]:
            lines.append(f"   {f['department']}")
            lines.append("")
        meta_parts = [p for p in (city, f"closes {closes}" if closes else "") if p]
        if meta_parts:
            lines.append("   " + " · ".join(meta_parts))
        if tender.get("detail_url"):
            lines.append(f"   {tender['detail_url']}")
        lines.append("")

    lines.extend(
        [
            "Follow for daily Civil Works, Health and IT alerts.",
            "Comment your city if you want more from there.",
        ]
    )
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
    """Upload photo then publish it as a Page feed post (not Photos-only).

    Direct /photos posts often land in the album without showing under Posts.
    Unpublished upload + /feed attached_media creates a normal timeline post.
    """
    if not config.FB_PAGE_ID or not config.FB_PAGE_ACCESS_TOKEN:
        raise FacebookPostError(
            "FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not configured. See .env.example."
        )

    token = config.FB_PAGE_ACCESS_TOKEN
    page_id = config.FB_PAGE_ID
    version = config.FB_GRAPH_API_VERSION

    upload_url = f"https://graph.facebook.com/{version}/{page_id}/photos"
    with open(image_path, "rb") as image_file:
        upload = requests.post(
            upload_url,
            data={
                "published": "false",
                "temporary": "true",
                "access_token": token,
            },
            files={"source": image_file},
            timeout=60,
        )
    upload_data = upload.json()
    if upload.status_code != 200 or "error" in upload_data or "id" not in upload_data:
        error = upload_data.get("error", {})
        raise FacebookPostError(
            f"Facebook photo upload error ({upload.status_code}): "
            f"{error.get('message', upload.text)}"
        )

    photo_id = upload_data["id"]
    feed_url = f"https://graph.facebook.com/{version}/{page_id}/feed"
    feed = requests.post(
        feed_url,
        data={
            "message": caption,
            "attached_media[0]": json.dumps({"media_fbid": photo_id}),
            "access_token": token,
        },
        timeout=60,
    )
    feed_data = feed.json()
    if feed.status_code != 200 or "error" in feed_data:
        error = feed_data.get("error", {})
        raise FacebookPostError(
            f"Facebook feed post error ({feed.status_code}): "
            f"{error.get('message', feed.text)}"
        )

    logger.info("Posted to Facebook feed, post id: %s", feed_data.get("id"))
    return feed_data
