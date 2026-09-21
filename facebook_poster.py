import json
import logging
import re
from datetime import datetime

import requests

import config

logger = logging.getLogger(__name__)


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

    day = parsed.day
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


def extract_fields(tender: dict) -> dict:
    """Display fields from listing + detail page."""
    detail = tender.get("detail_fields") or {}

    city = (
        detail.get("City")
        or tender.get("city")
        or tender.get("location", "").split(" - ")[0].strip()
    )
    department = detail.get("Organization Name") or tender.get("organization", "")

    deadline = detail.get("Closing Date & Time") or ""
    if not deadline:
        deadline = tender.get("closing_date", "")
        if tender.get("closing_time"):
            deadline = f"{deadline} at {tender['closing_time']}".strip()

    bid_security = _clean_money(detail.get("Bid Security", ""))

    return {
        "city": city,
        "department": department,
        "deadline": deadline,
        "bid_security": bid_security or "Not listed",
    }


def format_digest_message(niche_label: str, tenders: list) -> str:
    """Sector digest caption for the Facebook feed."""
    today = datetime.now().strftime("%d %b %Y")
    cities = []
    for tender in tenders:
        city = extract_fields(tender)["city"]
        if city and city not in cities:
            cities.append(city)
    city_bit = ", ".join(cities) if cities else "Islamabad, Lahore, Karachi"

    lines = [
        f"{niche_label} · {today}",
        f"{len(tenders)} new tender{'s' if len(tenders) != 1 else ''} · {city_bit}",
        "",
    ]

    for i, tender in enumerate(tenders, start=1):
        f = extract_fields(tender)
        title = _truncate((tender.get("title") or "").strip(), 120)
        city = f["city"] or ""
        closes = _short_deadline(f["deadline"])

        lines.append(f"{i}. {title}")
        if f["department"]:
            lines.append(f["department"])
        lines.append("")
        meta = " · ".join(p for p in (city, f"closes {closes}" if closes else "") if p)
        if meta:
            lines.append(meta)
        if tender.get("detail_url"):
            lines.append(tender["detail_url"])
        lines.append("")

    lines.extend(
        [
            "Follow for daily Civil Works, Health and IT alerts.",
            "Comment your city if you want more from there.",
        ]
    )
    return "\n".join(lines)


def post_photo_to_page(image_path: str, caption: str) -> dict:
    """Upload photo then publish as a Page feed post (not Photos-only)."""
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
