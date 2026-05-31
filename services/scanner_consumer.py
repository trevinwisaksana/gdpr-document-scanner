"""
Scanner consumer service.
Pulls extracted text messages from Pub/Sub, runs PII detection, and updates
the status_flag on drive_files in Postgres.

Required env vars:
  PUBSUB_SUBSCRIPTION  — Pub/Sub subscription to pull from
  DATABASE_URL         — Postgres connection string (postgresql://user:pass@host/db)

Optional env vars:
  MAX_MESSAGES         — max concurrent messages being processed (default: 10)
"""

import json
import logging
import os

import psycopg2
import psycopg2.pool
from google.cloud import pubsub_v1

from app.process import scan_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_ENSURE_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_drive_files_owner ON drive_files (owner);
"""

_UPDATE_FLAG = """
UPDATE drive_files
SET status_flag = %s, last_seen_at = NOW()
WHERE file_id = %s
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


def main() -> None:
    subscription = os.environ["PUBSUB_SUBSCRIPTION"]
    database_url = os.environ["DATABASE_URL"]
    max_messages = int(os.environ.get("MAX_MESSAGES", "10"))

    logger.info("connecting to database")
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1, maxconn=max_messages + 2, dsn=database_url
    )
    logger.info("database connection pool ready")

    _ensure_schema(pool)

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

            logger.info(
                "scan complete file_id=%s name=%r has_pii=%s findings=%d",
                file_id, file_name, result.has_pii, len(result.findings),
            )
            for f in result.findings:
                logger.info(
                    "  finding file_id=%s category=%s snippet=%r confidence=%s",
                    file_id, f["category"], f.get("snippet"), f.get("confidence"),
                )

            logger.info("updating database file_id=%s status_flag=%s", file_id, status_flag)
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(_UPDATE_FLAG, (status_flag, file_id))
                conn.commit()
                logger.info("database updated file_id=%s", file_id)
            except Exception as exc:
                conn.rollback()
                logger.error("database update failed file_id=%s error=%s", file_id, exc)
                raise
            finally:
                pool.putconn(conn)

            message.ack()
            logger.info("done file_id=%s name=%r status_flag=%s", file_id, file_name, status_flag)

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
