import logging
import time
from datetime import datetime, timedelta

import config
import main as tender_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def seconds_until(target_hhmm: str) -> float:
    now = datetime.now()
    target_time = datetime.strptime(target_hhmm, "%H:%M").time()
    target_dt = datetime.combine(now.date(), target_time)
    if target_dt <= now:
        target_dt += timedelta(days=1)
    return (target_dt - now).total_seconds()


def run_forever():
    logger.info(
        "Scheduler started. Will run the scraper daily at %s (container time, now: %s)",
        config.RUN_TIME,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    while True:
        wait = seconds_until(config.RUN_TIME)
        logger.info("Next run in %.0f minutes", wait / 60)
        time.sleep(wait)

        try:
            tender_main.run()
        except Exception:
            logger.exception("Scheduled run failed")

        # avoid double-triggering within the same target minute
        time.sleep(65)


if __name__ == "__main__":
    run_forever()
