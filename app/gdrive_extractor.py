import psycopg2
from typing import Generator

from app.drive_mimes import build_drive_service


class GDriveLister:
    def __init__(self, source_folder_id: str, db_config: dict):
        self.source_folder_id = source_folder_id
        self._service = build_drive_service()
        self.db_config = db_config  # Store your DB connection details

    def list_files(self) -> Generator[dict, None, None]:
        """BFS over Drive folder tree, yielding all extractable files."""
        # ... (keep your existing list_files logic here)
        yield from []  # Placeholder for your existing generator logic

    def run(self) -> int:
        count = 0

        # 1. Connect to the database
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()

        # 2. Prepare the Upsert Query
        # We use ON CONFLICT to prevent duplicate file_id errors.
        # Note: We do NOT update the 'flag' here so that your manual flags stay saved.
        upsert_query = """
                       INSERT INTO drive_files (file_id, name, owner, google_created_at, is_deleted, last_seen_at)
                       VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP) ON CONFLICT (file_id) DO \
                       UPDATE SET
                           name = EXCLUDED.name, \
                           owner = EXCLUDED.owner, \
                           is_deleted = EXCLUDED.is_deleted, \
                           last_seen_at = CURRENT_TIMESTAMP; \
                       """

        try:
            for file_data in self.list_files():
                # Execute the upsert for each file found in the scan
                cur.execute(upsert_query, (
                    file_data["file_id"],
                    file_data["name"],
                    file_data["owner"],
                    file_data["modified_time"],  # Using modified_time as created_at
                    file_data["deleted"]
                ))
                count += 1

            # 3. Commit the changes
            conn.commit()
            print(f"Successfully synced {count} files to PostgreSQL.")

        except Exception as e:
            print(f"Error during DB sync: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

        return count
