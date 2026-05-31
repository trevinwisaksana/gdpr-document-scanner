"""
Scanner consumer service.
Pulls extracted text messages from Pub/Sub, runs PII detection, and updates
the status_flag, detection stage, and primary PII category on drive_files in Postgres.

Required env vars:
  PUBSUB_SUBSCRIPTION  — Pub/Sub subscription to pull from
  DATABASE_URL         — Postgres connection string (postgresql://user:pass@host/db)

Optional env vars:
  MAX_MESSAGES         — max concurrent messages being processed (default: 10)
"""

import json
import logging
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg2
import psycopg2.extras
import psycopg2.pool
from google.cloud import pubsub_v1

from app.process import scan_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FLUSH_BATCH_SIZE = 50
FLUSH_INTERVAL = 0.5


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

_ENSURE_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_drive_files_owner ON drive_files (owner);
ALTER TABLE drive_files ADD COLUMN IF NOT EXISTS detection_stage TEXT;
ALTER TABLE drive_files ADD COLUMN IF NOT EXISTS pii_category TEXT;
"""

_BATCH_UPDATE_FLAG = """
UPDATE drive_files SET status_flag = v.flag, detection_stage = v.stage, pii_category = v.category, last_seen_at = NOW()
FROM (VALUES %s) AS v(flag, stage, category, file_id)
WHERE drive_files.file_id = v.file_id
"""


def _ensure_schema(pool: psycopg2.pool.ThreadedConnectionPool) -> None:
    logger.info("ensuring index on drive_files.owner")
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(_ENSURE_SCHEMA)
        conn.commit()
        logger.info("schema ready")
    except Exception as exc:
        logger.error("schema setup failed error=%s", exc)
        raise
    finally:
        pool.putconn(conn)


def _flusher(pool: psycopg2.pool.ThreadedConnectionPool, write_queue: queue.Queue) -> None:
    while True:
        batch = []
        deadline = time.monotonic() + FLUSH_INTERVAL
        while len(batch) < FLUSH_BATCH_SIZE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                item = write_queue.get(timeout=remaining)
                batch.append(item)
            except queue.Empty:
                break

        if not batch:
            continue

        messages = [item[0] for item in batch]
        values = [(item[1], item[2], item[3], item[4]) for item in batch]

        logger.info("flushing batch size=%d", len(batch))
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, _BATCH_UPDATE_FLAG, values)
            conn.commit()
            logger.info("batch database update complete size=%d", len(batch))
            for msg in messages:
                msg.ack()
        except Exception as exc:
            conn.rollback()
            logger.error("batch database update failed error=%s", exc)
            for msg in messages:
                msg.nack()
        finally:
            pool.putconn(conn)


def main() -> None:
    threading.Thread(target=_start_health_server, daemon=True).start()
    subscription = os.environ["PUBSUB_SUBSCRIPTION"]
    database_url = os.environ["DATABASE_URL"]
    max_messages = int(os.environ.get("MAX_MESSAGES", "100"))

    logger.info("connecting to database")
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1, maxconn=5, dsn=database_url
    )
    logger.info("database connection pool ready")

    _ensure_schema(pool)

    write_queue: queue.Queue = queue.Queue()
    threading.Thread(target=_flusher, args=(pool, write_queue), daemon=True).start()

    subscriber = pubsub_v1.SubscriberClient()
    flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)

    def callback(message: pubsub_v1.subscriber.message.Message) -> None:
        payload = {}
        try:
            payload = json.loads(message.data.decode("utf-8"))
            file_id = payload["file_id"]
            file_name = payload.get("name", file_id)
            text = payload["text"]

            logger.info("scanning file_id=%s name=%r chars=%d", file_id, file_name, len(text))

            result = scan_text(text, file_id)
            status_flag = "flagged" if result.has_pii else "not_flagged"
            pii_category = result.category

            logger.info(
                "scan complete file_id=%s name=%r has_pii=%s category=%s findings=%d stage=%s",
                file_id, file_name, result.has_pii, pii_category, len(result.findings), result.stage,
            )
            for f in result.findings:
                logger.info(
                    "  finding file_id=%s category=%s snippet=%r confidence=%s",
                    file_id, f["category"], f.get("snippet"), f.get("confidence"),
                )

            write_queue.put((message, status_flag, result.stage, pii_category, file_id))

        except Exception as exc:
            logger.error(
                "failed file_id=%s name=%r error=%s",
                payload.get("file_id", "unknown"),
                payload.get("name", "unknown"),
                exc,
                exc_info=True,
            )
            message.nack()

    with subscriber:
        future = subscriber.subscribe(subscription, callback=callback, flow_control=flow_control)
        logger.info("scanner start subscription=%s max_messages=%d", subscription, max_messages)
        try:
            future.result()
        except KeyboardInterrupt:
            logger.info("shutting down")
            future.cancel()
            future.result()

    pool.closeall()
    logger.info("scanner stopped")


if __name__ == "__main__":
    main()
