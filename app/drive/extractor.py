from __future__ import annotations

import json
import logging
import os
from typing import Generator

import psycopg2
import psycopg2.extras
from google.cloud import pubsub_v1
from app.drive.mimes import GOOGLE_EXPORT, SUPPORTED_MIME, build_drive_service

logger = logging.getLogger(__name__)

_UPSERT = """
INSERT INTO drive_files (file_id, name, mime_type, owner, google_created_at, is_deleted, last_seen_at)
VALUES %s
ON CONFLICT (file_id) DO UPDATE SET
    name = EXCLUDED.name,
    mime_type = EXCLUDED.mime_type,
    owner = EXCLUDED.owner,
    is_deleted = EXCLUDED.is_deleted,
    last_seen_at = NOW()
"""

_UPSERT_TEMPLATE = "(%s, %s, %s, %s, %s, %s, NOW())"


class GDriveLister:
    def __init__(self):
        self._service = build_drive_service()

    def list_files(self) -> Generator[dict, None, None]:
        """List all accessible files, paginating through the full result set."""
        page_token = None
        while True:
            resp = (
                self._service.files()
                .list(
                    fields="nextPageToken, files(id, name, mimeType, createdTime, trashed, owners)",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                mime_type = f["mimeType"]
                if mime_type in GOOGLE_EXPORT or mime_type in SUPPORTED_MIME or mime_type.startswith("video/"):
                    owners = f.get("owners", [])
                    yield {
                        "file_id": f["id"],
                        "name": f["name"],
                        "mime_type": mime_type,
                        "modified_time": f.get("createdTime"),
                        "owner": owners[0].get("emailAddress") if owners else "admin@admin.com",
                        "deleted": f.get("trashed", False),
                    }
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    def run(self) -> int:
        database_url = os.environ["DATABASE_URL"]
        topic = os.environ.get("EXTRACTOR_PUBSUB_TOPIC")
        publisher = pubsub_v1.PublisherClient() if topic else None

        conn = psycopg2.connect(database_url)
        count = 0
        try:
            batch = list(self.list_files())
            rows = [
                (
                    file["file_id"],
                    file["name"],
                    file["mime_type"],
                    file["owner"],
                    file["modified_time"],
                    file["deleted"],
                )
                for file in batch
            ]
            with conn.cursor() as cur:
                if rows:
                    psycopg2.extras.execute_values(cur, _UPSERT, rows, template=_UPSERT_TEMPLATE)
                count = len(rows)
            conn.commit()
            logger.info("upserted %d files into drive_files", count)

            if publisher and topic:
                with conn.cursor() as cur:
                    file_ids = [file["file_id"] for file in batch]
                    cur.execute(
                        "SELECT file_id FROM drive_files "
                        "WHERE file_id = ANY(%s) "
                        "AND (status_flag IS NULL OR status_flag = 'not_checked')",
                        (file_ids,),
                    )
                    unchecked = {row[0] for row in cur.fetchall()}

                to_publish = [f for f in batch if f["file_id"] in unchecked]
                logger.info("publishing %d unchecked files (skipping %d already processed)", len(to_publish), count - len(to_publish))

                futures = [
                    publisher.publish(
                        topic,
                        json.dumps({
                            "file_id": file["file_id"],
                            "name": file["name"],
                            "mime_type": file["mime_type"],
                        }).encode(),
                    )
                    for file in to_publish
                ]
                for f in futures:
                    f.result()
                logger.info("published %d messages to %s", len(futures), topic)
        finally:
            conn.close()
        return count
