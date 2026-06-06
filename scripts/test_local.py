"""
Local test script for the full pipeline: listing → extraction → scanning.
Bypasses Pub/Sub and Postgres entirely.

Usage:
  1. Fill in SOURCE_FOLDER_ID in .env
  2. python test_local.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from app.drive.extractor import GDriveLister
from app.drive.downloader import GDriveDownloader
from app.process import scan_text


def test_listing():
    print("\n=== Listing ===")
    lister = GDriveLister()
    files = list(lister.list_files())
    print(f"Found {len(files)} files")
    for f in files[:5]:
        print(f"  {f['name']} | {f['mime_type']} | owner={f['owner']} | deleted={f['deleted']}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")
    return files


def test_extraction(files):
    print("\n=== Extraction (first file) ===")
    if not files:
        print("No files found — skipping")
        return None, None
    file = files[0]
    print(f"Extracting: {file['name']}")
    downloader = GDriveDownloader()
    text = downloader.download_and_extract(file["file_id"], file["mime_type"], file["name"])
    print(f"Extracted {len(text)} characters")
    print(f"Preview:\n{text[:300].strip()}")
    return file, text


def test_scanner(file, text):
    print("\n=== Scanner ===")
    if not text:
        print("No text to scan — skipping")
        return
    result = scan_text(text, file["file_id"])
    print(f"has_pii={result.has_pii}  findings={len(result.findings)}")
    for f in result.findings[:10]:
        print(f"  [{f['category']}] {f['snippet']!r}  confidence={f.get('confidence')}")
    if len(result.findings) > 10:
        print(f"  ... and {len(result.findings) - 10} more")


if __name__ == "__main__":
    files = test_listing()
    file, text = test_extraction(files)
    test_scanner(file, text)
