"""
Cloud Run Job entrypoint for Google Drive file listing.
"""

import logging

from app.gdrive_extractor import GDriveLister

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("listing start")
    lister = GDriveLister()
    count = lister.run()
    logger.info("listing complete total=%d", count)


if __name__ == "__main__":
    main()
