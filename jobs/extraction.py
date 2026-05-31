"""
Cloud Run Job entrypoint for extraction scheduling.
Reads unprocessed file metadata from Postgres and publishes each file to Pub/Sub
to be consumed by the extraction consumer service.

Required env vars:
  PUBSUB_TOPIC  — Pub/Sub topic to publish file metadata to
"""

import json
import logging
import os
import sys

from google.cloud import pubsub_v1

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    pubsub_topic = os.environ["PUBSUB_TOPIC"]

    logger.info("extraction job start topic=%s", pubsub_topic)

    # add postgres implementation here: read unprocessed file metadata
    files = []

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
