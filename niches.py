"""Digest niches aligned to PPRA Sector filters."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

import config

logger = logging.getLogger(__name__)

# niche_id → (sector_id, label) — must match config.SECTORS
NICHE_DEFINITIONS = {
    "civil_works": {"sector_id": "6", "label": "Civil Works"},
    "health": {"sector_id": "13", "label": "Health/Medicines"},
    "ict": {"sector_id": "14", "label": "Info and Comm Tech"},
}

_SECTOR_ID_TO_NICHE = {
    meta["sector_id"]: niche_id for niche_id, meta in NICHE_DEFINITIONS.items()
}

# Titles that say nothing useful to a bidder scrolling Facebook.
_GENERIC_TITLES = {
    "invitation to bid",
    "invitation for bid",
    "invitation for bids",
    "invitation to tender",
    "invitation for tender",
    "invitation for tenders",
    "tender notice",
    "tender notice.",
    "notice inviting tender",
    "notice inviting tenders",
    "notice inviting bids",
    "nit",
    "ifb",
    "itt",
    "tender",
    "tenders",
    "bid notice",
    "bidding notice",
    "request for proposal",
    "request for quotations",
    "request for quotation",
    "rfq",
    "rfp",
    "eoi",
    "expression of interest",
}

_MIN_TITLE_LEN = 28


def is_meaningful_title(title: str) -> bool:
    """False for empty, tiny, or generic labels like 'Invitation to Bid'."""
    raw = (title or "").strip()
    if not raw:
        return False
    normalized = re.sub(r"\s+", " ", raw).strip(" .-_|").lower()
    if normalized in _GENERIC_TITLES:
        return False
    for prefix in (
        "invitation to bid",
        "invitation for bid",
        "invitation for bids",
        "invitation to tender",
        "tender notice",
        "notice inviting tender",
        "notice inviting tenders",
    ):
        if normalized == prefix or (
            normalized.startswith(prefix + " ") and len(normalized) < _MIN_TITLE_LEN
        ):
            return False
        if normalized.startswith(prefix + " -") or normalized.startswith(prefix + " –"):
            rest = normalized.split("-", 1)[-1].split("–", 1)[-1].strip()
            if len(rest) < 12:
                return False
    if len(normalized) < _MIN_TITLE_LEN:
        return False
    letters = sum(1 for c in normalized if c.isalpha())
    if letters < 16:
        return False
    return True


def enabled_niche_ids() -> list[str]:
    ids = []
    for raw in config.ENABLED_NICHES:
        key = raw.strip().lower()
        if key in NICHE_DEFINITIONS and key not in ids:
            ids.append(key)
    return ids


def niche_label(niche_id: str) -> str:
    return NICHE_DEFINITIONS.get(niche_id, {}).get("label", niche_id.title())


def assign_niche(tender: dict) -> str | None:
    """Map a scraped tender to a digest niche via its PPRA sector id/name."""
    sector_id = str(tender.get("sector_id") or "").strip()
    if sector_id in _SECTOR_ID_TO_NICHE:
        niche_id = _SECTOR_ID_TO_NICHE[sector_id]
        return niche_id if niche_id in enabled_niche_ids() else None

    sector_name = (tender.get("sector") or "").strip().lower()
    for niche_id in enabled_niche_ids():
        if NICHE_DEFINITIONS[niche_id]["label"].lower() == sector_name:
            return niche_id
    return None


def filter_and_group(tenders: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    skipped_niche = 0
    skipped_title = 0
    for tender in tenders:
        if not is_meaningful_title(tender.get("title", "")):
            skipped_title += 1
            continue
        niche_id = assign_niche(tender)
        if niche_id is None:
            skipped_niche += 1
            continue
        tender["niche_id"] = niche_id
        tender["niche_label"] = niche_label(niche_id)
        grouped[niche_id].append(tender)

    if skipped_title:
        logger.info("Skipped %d tenders with generic/short titles", skipped_title)
    if skipped_niche:
        logger.info("Skipped %d tenders outside enabled sector niches", skipped_niche)
    return dict(grouped)


def select_digest_groups(
    grouped: dict[str, list[dict]],
) -> list[tuple[str, list[dict]]]:
    """Largest niche first (ENABLED_NICHES order is tie-break only)."""
    ordered_ids = enabled_niche_ids()
    candidates = [
        (nid, grouped[nid])
        for nid in ordered_ids
        if nid in grouped and grouped[nid]
    ]
    candidates.sort(key=lambda item: (-len(item[1]), ordered_ids.index(item[0])))
    return candidates[: config.MAX_DIGEST_POSTS_PER_DAY]
