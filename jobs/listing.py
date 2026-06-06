"""
Cloud Run Job entrypoint for Google Drive file listing.
"""

import logging
import time

from app.drive.extractor import GDriveLister

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("listing start")
    lister = GDriveLister()
    t0 = time.perf_counter()
    count = lister.run()
    elapsed_s = round(time.perf_counter() - t0, 1)
    logger.info("listing complete total=%d elapsed_s=%.1f", count, elapsed_s)


if __name__ == "__main__":
    main()
