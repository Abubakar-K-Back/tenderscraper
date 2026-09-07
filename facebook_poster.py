import logging
import re
from datetime import date, datetime

import requests

import config

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 140

_BOLD_MAP = {}
for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _BOLD_MAP[c] = chr(0x1D5D4 + i)
for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _BOLD_MAP[c] = chr(0x1D5EE + i)
for i, c in enumerate("0123456789"):
    _BOLD_MAP[c] = chr(0x1D7EC + i)


class FacebookPostError(Exception):
    pass


def to_bold_unicode(text: str) -> str:
    """Render ASCII letters/digits as Unicode bold so it stands out on Facebook,
    which doesn't support markdown."""
    return "".join(_BOLD_MAP.get(ch, ch) for ch in text)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cutoff = text.rfind(" ", 0, max_len)
    if cutoff == -1:
        cutoff = max_len
    return text[:cutoff].rstrip(",.;- ") + "…"


def _days_left(closing_date: str):
    try:
        closing = datetime.strptime(closing_date, "%b %d, %Y").date()
    except ValueError:
        return None
    return (closing - date.today()).days


def _category_hashtag(category: str) -> str:
    return "#" + re.sub(r"[^A-Za-z0-9]", "", category)


def format_tender_message(tender: dict) -> str:
    title = _truncate(tender["title"].strip(), MAX_TITLE_LENGTH)

    lines = [
        "🆕 NEW TENDER ALERT",
        "",
        to_bold_unicode(title),
        "",
    ]

    info_lines = []
    if tender.get("organization"):
        info_lines.append(f"🏛️ {tender['organization']}")
    if tender.get("location"):
        info_lines.append(f"📍 {tender['location']}")
    if tender.get("category"):
        info_lines.append(f"🏷️ {tender['category']}")
    if info_lines:
        lines.extend(info_lines)
        lines.append("")

    if tender.get("closing_date"):
        closing = f"⏳ Closing: {tender['closing_date']}"
        if tender.get("closing_time"):
            closing += f" at {tender['closing_time']}"
        days_left = _days_left(tender["closing_date"])
        if days_left is not None and days_left >= 0:
            day_word = "day" if days_left == 1 else "days"
            closing += f"  ({days_left} {day_word} left)"
        lines.append(closing)
        lines.append("")

    lines.append(f"🆔 Tender No: {tender['tender_no']}")
    if tender.get("detail_url"):
        lines.append(f"🔗 Full details & documents: {tender['detail_url']}")

    hashtags = ["#PPRA", "#GovtTenders", "#Pakistan"]
    if tender.get("category"):
        hashtags.append(_category_hashtag(tender["category"]))
    lines.append("")
    lines.append(" ".join(hashtags))

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
