from __future__ import annotations

from typing import Generator

from app.drive_mimes import GOOGLE_EXPORT, SUPPORTED_MIME, build_drive_service


class GDriveLister:
    def __init__(self, source_folder_id: str):
        self.source_folder_id = source_folder_id
        self._service = build_drive_service()

    def list_files(self) -> Generator[dict, None, None]:
        """BFS over Drive folder tree, yielding all extractable files."""
        folder_queue = [self.source_folder_id]
        while folder_queue:
            folder_id = folder_queue.pop()
            page_token = None
            while True:
                resp = (
                    self._service.files()
                    .list(
                        q=f"'{folder_id}' in parents",
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, trashed, owners)",
                        pageToken=page_token,
                        pageSize=1000,
                    )
                    .execute()
                )
                for f in resp.get("files", []):
                    if f["mimeType"] == "application/vnd.google-apps.folder":
                        if not f.get("trashed"):
                            folder_queue.append(f["id"])
                    elif f["mimeType"] in GOOGLE_EXPORT or f["mimeType"] in SUPPORTED_MIME:
                        owners = f.get("owners", [])
                        yield {
                            "file_id": f["id"],
                            "name": f["name"],
                            "mime_type": f["mimeType"],
                            "modified_time": f.get("modifiedTime"),
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
            # add postgres implementation here: upsert file record (file_id, name, owner, flag, deleted)
            count += 1
        return count
