"""
Extraction consumer service.
Pulls file metadata messages from Pub/Sub in batches, downloads and extracts
text using a thread pool, then publishes results to the scanner Pub/Sub topic.

Required env vars:
  PUBSUB_SUBSCRIPTION   — Pub/Sub subscription to pull from
  SCANNER_PUBSUB_TOPIC  — Pub/Sub topic to publish extracted text to

Optional env vars:
  BATCH_SIZE   — messages to pull per batch (default: 10)
  WORKERS      — parallel download threads per batch (default: 10)
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

from google.cloud import pubsub_v1

from app.drive.downloader import GDriveDownloader

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _start_health_server() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("", port), Handler).serve_forever()


_thread_local = threading.local()


def _get_downloader() -> GDriveDownloader:
    if not hasattr(_thread_local, "downloader"):
        _thread_local.downloader = GDriveDownloader()
    return _thread_local.downloader


def process_message(
    msg: pubsub_v1.types.ReceivedMessage,
    publisher: pubsub_v1.PublisherClient,
    scanner_topic: str,
) -> tuple[str, bool]:
    """Download, extract, and publish one message. Returns (ack_id, success)."""
    try:
        file = json.loads(msg.message.data.decode("utf-8"))
        text = _get_downloader().download_and_extract(
            file["file_id"], file["mime_type"], file["name"]
        )
        publisher.publish(
            scanner_topic,
            json.dumps({"file_id": file["file_id"], "name": file["name"], "text": text}).encode(),
        ).result()
        logger.info("processed file_id=%s", file["file_id"])
        return msg.ack_id, True
    except Exception as exc:
        file_id = "unknown"
        try:
            file_id = json.loads(msg.message.data).get("file_id", "unknown")
        except Exception:
            pass
        logger.error("failed file_id=%s error=%s", file_id, exc)
        return msg.ack_id, False


def main() -> None:
    threading.Thread(target=_start_health_server, daemon=True).start()

    subscription = os.environ["PUBSUB_SUBSCRIPTION"]
    scanner_topic = os.environ["SCANNER_PUBSUB_TOPIC"]
    batch_size = int(os.environ.get("BATCH_SIZE", "100"))
    workers = int(os.environ.get("WORKERS", "100"))

    logger.info("consumer start subscription=%s batch_size=%d workers=%d", subscription, batch_size, workers)

    subscriber = pubsub_v1.SubscriberClient()
    publisher = pubsub_v1.PublisherClient()

    with subscriber:
        while True:
            response = subscriber.pull(
                request={"subscription": subscription, "max_messages": batch_size},
                timeout=30,
            )
            messages = response.received_messages
            if not messages:
                time.sleep(1)
                continue

            logger.info("pulled %d messages", len(messages))

            ack_ids, nack_ids = [], []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(process_message, msg, publisher, scanner_topic): msg
                    for msg in messages
                }
                for future in as_completed(futures):
                    ack_id, success = future.result()
                    (ack_ids if success else nack_ids).append(ack_id)

            if ack_ids:
                subscriber.acknowledge(request={"subscription": subscription, "ack_ids": ack_ids})
            if nack_ids:
                subscriber.modify_ack_deadline(
                    request={"subscription": subscription, "ack_ids": nack_ids, "ack_deadline_seconds": 0}
                )
            logger.info("batch done acked=%d nacked=%d", len(ack_ids), len(nack_ids))


if __name__ == "__main__":
    main()
