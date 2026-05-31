"""
Scanner consumer service.
Pulls extracted text messages from Pub/Sub and runs PII detection on each.
Runs as a long-lived Cloud Run Service — autoscales based on CPU/message volume.

Required env vars:
  PUBSUB_SUBSCRIPTION  — Pub/Sub subscription to pull from

Optional env vars:
  MAX_MESSAGES         — max concurrent messages being processed (default: 10)
"""

import json
import logging
import os

from google.cloud import pubsub_v1

from app.process import scan_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    subscription = os.environ["PUBSUB_SUBSCRIPTION"]
    max_messages = int(os.environ.get("MAX_MESSAGES", "10"))

    subscriber = pubsub_v1.SubscriberClient()
    flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)

    def callback(message: pubsub_v1.subscriber.message.Message) -> None:
        try:
            payload = json.loads(message.data.decode("utf-8"))
            file_id = payload["file_id"]
            text = payload["text"]

            result = scan_text(text, file_id)

            # add postgres implementation here: store scan result (file_id, findings, has_pii)
            # add postgres implementation here: set flag=True on file if result.has_pii

            message.ack()
            logger.info("scanned file_id=%s has_pii=%s findings=%d", file_id, result.has_pii, len(result.findings))
        except Exception as exc:
            logger.error("failed file_id=%s error=%s", payload.get("file_id", "unknown"), exc)
            message.nack()

    with subscriber:
        future = subscriber.subscribe(subscription, callback=callback, flow_control=flow_control)
        logger.info("scanner start subscription=%s max_messages=%d", subscription, max_messages)
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()
            future.result()


if __name__ == "__main__":
    main()
