import argparse
import logging
import shutil
import tempfile
import time
from pathlib import Path

import config
import facebook_poster
import image_generator
import niches
import scraper
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _enrich_details(tenders: list[dict]) -> None:
    for tender in tenders:
        try:
            tender["detail_fields"] = scraper.fetch_tender_detail(tender["tender_no"])
        except scraper.ScrapeError:
            logger.exception(
                "Failed to fetch detail page for %s, using listing-only fields",
                tender["tender_no"],
            )
            tender["detail_fields"] = {}


def _sleep_between(remaining_after: int) -> None:
    if remaining_after > 0:
        logger.info("Waiting %d seconds before next post", config.POST_DELAY_SECONDS)
        time.sleep(config.POST_DELAY_SECONDS)


def _post_photo(image_path: str, message: str, dry_run: bool, preview_name: str) -> bool:
    if dry_run:
        preview_path = config.DATA_DIR / preview_name
        shutil.copy2(image_path, preview_path)
        logger.info("[DRY RUN] Would post (image saved to %s):\n%s\n", preview_path, message)
        return True

    try:
        facebook_poster.post_photo_to_page(image_path, message)
        return True
    except facebook_poster.FacebookPostError:
        logger.exception("Failed to post to Facebook")
        return False


def run(dry_run: bool = False, pages: int = None):
    storage.init_db()

    tenders = scraper.scrape_active_tenders(num_pages=pages)
    logger.info("Scraped %d tenders", len(tenders))
    logger.info(
        "Enabled niches: %s",
        ", ".join(niches.niche_label(n) for n in niches.enabled_niche_ids()) or "(none)",
    )

    if not storage.is_seeded():
        logger.info(
            "First run detected: seeding database with %d existing tenders "
            "without posting to Facebook.",
            len(tenders),
        )
        if not dry_run:
            storage.mark_many_posted(tenders)
        return

    new_tenders = [t for t in tenders if not storage.is_posted(t["tender_no"])]
    logger.info("Found %d new tenders since last run", len(new_tenders))

    if not new_tenders:
        return

    _enrich_details(new_tenders)

    # Outside the shortlist: mark posted silently so they do not clog every run.
    out_of_niche = []
    in_scope = []
    for tender in new_tenders:
        if niches.assign_niche(tender) is None:
            out_of_niche.append(tender)
        else:
            in_scope.append(tender)

    if out_of_niche:
        logger.info(
            "Marking %d non-niche tenders as seen (not posting)",
            len(out_of_niche),
        )
        if not dry_run:
            storage.mark_many_posted(out_of_niche)

    if not in_scope:
        logger.info("No new tenders matched enabled niches")
        return

    grouped = niches.filter_and_group(in_scope)
    digest_groups = niches.select_digest_groups(grouped)

    if not digest_groups:
        logger.info("No digest groups to post")
        return

    # Tenders in niches that did not win a digest slot today stay unposted
    # for the next run. Everything in selected digests gets posted (and marked).
    selected_tenders = [t for _, group in digest_groups for t in group]
    selected_ids = {nid for nid, _ in digest_groups}
    deferred = sum(len(grouped[nid]) for nid in grouped if nid not in selected_ids)
    if deferred:
        logger.info(
            "Deferring %d tenders in niches beyond MAX_DIGEST_POSTS_PER_DAY=%d",
            deferred,
            config.MAX_DIGEST_POSTS_PER_DAY,
        )

    spotlight = niches.pick_spotlight(selected_tenders)
    posts_remaining = len(digest_groups) + (1 if spotlight else 0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        for niche_id, group in digest_groups:
            label = niches.niche_label(niche_id)
            image_path = str(tmp / f"digest_{niche_id}.png")
            image_generator.generate_digest_image(label, group, image_path)
            message = facebook_poster.format_digest_message(label, group)

            ok = _post_photo(
                image_path,
                message,
                dry_run=dry_run,
                preview_name=f"preview_digest_{niche_id}.png",
            )
            if ok and not dry_run:
                storage.mark_many_posted(group)

            posts_remaining -= 1
            _sleep_between(posts_remaining)

        if spotlight:
            image_path = str(tmp / f"spotlight_{spotlight['tender_no']}.png")
            image_generator.generate_tender_image(spotlight, image_path)
            message = facebook_poster.format_tender_message(spotlight, spotlight=True)
            ok = _post_photo(
                image_path,
                message,
                dry_run=dry_run,
                preview_name=f"preview_spotlight_{spotlight['tender_no']}.png",
            )
            # Spotlight tender is already in a digest group and marked there.
            if not ok:
                logger.warning(
                    "Spotlight post failed for %s (already included in digest)",
                    spotlight["tender_no"],
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Scrape PPRA active tenders and post niche digests + one spotlight "
            "to Facebook."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and save preview images without posting or writing to the DB.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Override number of listing pages to scrape (default: config.PAGES_TO_SCRAPE).",
    )
    args = parser.parse_args()

    run(dry_run=args.dry_run, pages=args.pages)
