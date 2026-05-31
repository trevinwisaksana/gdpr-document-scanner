# Benchmark

Run the GDPR scanner benchmark against staging Google Drive end-to-end.

## Steps

1. **Wipe DB** — truncate `drive_files` so the run starts clean:
```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres -c "TRUNCATE TABLE drive_files;"
```

2. **List files** — run the listing job to populate `drive_files` from Google Drive:
```bash
gcloud run jobs execute gdpr-listing-job --region=us-central1 --project=summer-bond-461608-i5 --wait
```

3. **Batch scan** — run the batch scan job (downloads + scans all files in parallel, 12 workers):
```bash
gcloud run jobs execute gdpr-batch-scan --region=us-central1 --project=summer-bond-461608-i5 --wait
```

4. **Show results** — pull `scan_metrics` logs and print a summary table of stage breakdown and timing.

For step 4, fetch logs from the `gdpr-batch-scan` job and parse them with Python to produce a table showing:
- Files processed per stage (regex / ner / ner+llm_verify / llm_detect)
- Percentage breakdown
- Average, min, max timing per stage (regex_ms, ner_ms, llm_verify_ms, llm_detect_ms, total_ms)

Use this log query:
```bash
gcloud logging read 'resource.labels.job_name="gdpr-batch-scan" AND textPayload=~"scan_metrics"' \
  --project=summer-bond-461608-i5 --limit=2000 --format="value(textPayload)"
```

Parse and display the results as a clean table in the terminal.
