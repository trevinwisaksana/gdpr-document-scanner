CREATE TABLE IF NOT EXISTS drive_files (
    file_id        text PRIMARY KEY,
    name           text,
    owner          text,
    mime_type      text,
    google_created_at text,
    is_deleted     boolean DEFAULT false,
    last_seen_at   timestamptz,
    status_flag    text DEFAULT NULL,
    pii_category   text
);

CREATE INDEX IF NOT EXISTS idx_drive_files_owner      ON drive_files(owner);
CREATE INDEX IF NOT EXISTS idx_drive_files_last_seen  ON drive_files(last_seen_at);

CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id                        bigserial PRIMARY KEY,
    captured_at               timestamptz DEFAULT NOW(),
    run_label                 text,
    total_files_registered    integer,
    total_files_flagged       integer,
    total_files_processed     integer,
    percentage_files_flagged  numeric(7,2),
    owners                    jsonb,
    flagged_files_per_owner   jsonb
);

CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_captured_at ON kpi_snapshots(captured_at DESC);
