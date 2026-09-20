import argparse
import logging
import tempfile
import time
from pathlib import Path

import config
import facebook_poster
import image_generator
import scraper
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False, pages: int = None):
    storage.init_db()

    tenders = scraper.scrape_active_tenders(num_pages=pages)
    logger.info("Scraped %d tenders", len(tenders))

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

    # Oldest-new first, so the Facebook feed reads in the same chronological
    # order the tenders were advertised.
    new_tenders.reverse()

    if len(new_tenders) > config.MAX_POSTS_PER_RUN:
        logger.warning(
            "Capping this run to %d posts (found %d new); the rest will be "
            "picked up next run.",
            config.MAX_POSTS_PER_RUN,
            len(new_tenders),
        )
        new_tenders = new_tenders[: config.MAX_POSTS_PER_RUN]

    for i, tender in enumerate(new_tenders):
        try:
            tender["detail_fields"] = scraper.fetch_tender_detail(tender["tender_no"])
        except scraper.ScrapeError:
            logger.exception(
                "Failed to fetch detail page for %s, posting with listing-only fields",
                tender["tender_no"],
            )
            tender["detail_fields"] = {}

        message = facebook_poster.format_tender_message(tender)

        if dry_run:
            preview_path = config.DATA_DIR / f"preview_{tender['tender_no']}.png"
            image_generator.generate_tender_image(tender, str(preview_path))
            logger.info(
                "[DRY RUN] Would post (image saved to %s):\n%s\n", preview_path, message
            )
            continue

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = str(Path(tmp_dir) / f"{tender['tender_no']}.png")
            image_generator.generate_tender_image(tender, image_path)

            try:
                facebook_poster.post_photo_to_page(image_path, message)
                storage.mark_posted(tender["tender_no"], tender["title"])
            except facebook_poster.FacebookPostError:
                logger.exception("Failed to post tender %s", tender["tender_no"])
                continue

        if i < len(new_tenders) - 1:
            time.sleep(config.POST_DELAY_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape PPRA active tenders and post new ones to Facebook."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and show what would be posted without posting or writing to the DB.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Override number of listing pages to scrape (default: config.PAGES_TO_SCRAPE).",
    )
    args = parser.parse_args()

    run(dry_run=args.dry_run, pages=args.pages)
