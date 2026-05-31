"""
Cloud Run Job entrypoint for extraction scheduling.
Reads unprocessed file metadata from Postgres and publishes each file to Pub/Sub
to be consumed by the extraction consumer service.

Required env vars:
  PUBSUB_TOPIC  — Pub/Sub topic to publish file metadata to

Optional env vars:
  BATCH_SIZE    — max files to publish per run (default: 1000)
"""

import json
import logging
import os
import sys

import psycopg2
from google.cloud import pubsub_v1

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_SELECT = """
SELECT file_id, name, mime_type
FROM drive_files
WHERE is_deleted = false
  AND status_flag = 'not_checked'
  AND mime_type IS NOT NULL
LIMIT %s
"""


def main() -> None:
    pubsub_topic = os.environ["PUBSUB_TOPIC"]
    database_url = os.environ["DATABASE_URL"]
    batch_size = int(os.environ.get("BATCH_SIZE", "1000"))

    logger.info("extraction job start topic=%s batch_size=%d", pubsub_topic, batch_size)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT, (batch_size,))
            files = [
                {"file_id": row[0], "name": row[1], "mime_type": row[2]}
                for row in cur.fetchall()
            ]
    finally:
        conn.close()

    logger.info("found %d unprocessed files", len(files))

    publisher = pubsub_v1.PublisherClient()
    failed = 0

    for file in files:
        try:
            publisher.publish(
                pubsub_topic,
                json.dumps(file).encode("utf-8"),
            ).result()
        except Exception as exc:
            logger.error("failed to publish file_id=%s error=%s", file["file_id"], exc)
            failed += 1

    logger.info("extraction job complete total=%d failed=%d", len(files), failed)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
