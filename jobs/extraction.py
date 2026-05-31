"""
Cloud Run Job entrypoint for document text extraction.
Reads discovered file metadata from Postgres, downloads and extracts text from each file.

Required env vars:
  (none until Postgres is wired up)
"""

import logging
import sys

from app.gdrive_downloader import GDriveDownloader

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("extraction start")

    # add postgres implementation here: read unprocessed file metadata
    files = []

    downloader = GDriveDownloader()
    failed = 0

    for file in files:
        try:
            text = downloader.download_and_extract(
                file["file_id"], file["mime_type"], file["name"]
            )
            # add scanner implementation here: pass text to scanner
        except Exception as exc:
            logger.error("failed file_id=%s error=%s", file["file_id"], exc)
            failed += 1

    logger.info("extraction complete total=%d failed=%d", len(files), failed)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
