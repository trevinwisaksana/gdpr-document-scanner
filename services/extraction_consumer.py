"""
Extraction consumer service.
Pulls file metadata messages from Pub/Sub, downloads and extracts text,
then publishes the result to the scanner Pub/Sub topic.
Runs as a long-lived Cloud Run Service — autoscales based on CPU/message volume.

Required env vars:
  PUBSUB_SUBSCRIPTION   — Pub/Sub subscription to pull from
  SCANNER_PUBSUB_TOPIC  — Pub/Sub topic to publish extracted text to

Optional env vars:
  MAX_MESSAGES          — max concurrent messages being processed (default: 10)
"""

import json
import logging
import os

from google.cloud import pubsub_v1

from app.gdrive_downloader import GDriveDownloader

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    subscription = os.environ["PUBSUB_SUBSCRIPTION"]
    scanner_topic = os.environ["SCANNER_PUBSUB_TOPIC"]
    max_messages = int(os.environ.get("MAX_MESSAGES", "10"))

    downloader = GDriveDownloader()
    subscriber = pubsub_v1.SubscriberClient()
    publisher = pubsub_v1.PublisherClient()
    flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)

    def callback(message: pubsub_v1.subscriber.message.Message) -> None:
        try:
            file = json.loads(message.data.decode("utf-8"))
            text = downloader.download_and_extract(
                file["file_id"], file["mime_type"], file["name"]
            )
            publisher.publish(
                scanner_topic,
                json.dumps({"file_id": file["file_id"], "name": file["name"], "text": text}).encode("utf-8"),
            ).result()
            message.ack()
            logger.info("processed file_id=%s", file["file_id"])
        except Exception as exc:
            logger.error("failed file_id=%s error=%s", file.get("file_id", "unknown"), exc)
            message.nack()

    with subscriber:
        future = subscriber.subscribe(subscription, callback=callback, flow_control=flow_control)
        logger.info("consumer start subscription=%s max_messages=%d", subscription, max_messages)
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()
            future.result()


if __name__ == "__main__":
    main()
