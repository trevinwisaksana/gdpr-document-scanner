"""
Cloud Run Job entrypoint for Google Drive file listing.

Required env vars:
  SOURCE_FOLDER_ID  — Google Drive folder ID to scan
"""

import logging
import os

from app.gdrive_extractor import GDriveLister

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    source_folder_id = os.environ["SOURCE_FOLDER_ID"]

    logger.info("listing start source_folder=%s", source_folder_id)

    lister = GDriveLister(source_folder_id)
    count = lister.run()

    logger.info("listing complete total=%d", count)


if __name__ == "__main__":
    main()
