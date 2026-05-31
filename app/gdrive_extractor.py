from __future__ import annotations

from typing import Generator

from app.drive_mimes import GOOGLE_EXPORT, SUPPORTED_MIME, build_drive_service


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
                if f["mimeType"] in GOOGLE_EXPORT or f["mimeType"] in SUPPORTED_MIME:
                    owners = f.get("owners", [])
                    yield {
                        "file_id": f["id"],
                        "name": f["name"],
                        "mime_type": f["mimeType"],
                        "modified_time": f.get("createdTime"),
                        "owner": owners[0].get("emailAddress") if owners else None,
                        "deleted": f.get("trashed", False),
                        "flag": False,
                    }
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    def run(self) -> int:
        count = 0
        for file in self.list_files():
            # add postgres implementation here: upsert into drive_files
            # INSERT INTO drive_files (file_id, name, owner, google_created_at, is_deleted, last_seen_at)
            # VALUES (%s, %s, %s, %s, %s, NOW())
            # ON CONFLICT (file_id) DO UPDATE SET
            #     name = EXCLUDED.name, owner = EXCLUDED.owner,
            #     is_deleted = EXCLUDED.is_deleted, last_seen_at = NOW()
            count += 1
        return count
