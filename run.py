"""Entry point: python run.py [file_or_dir ...]

Scans each file (or every file in a directory) for PII and prints findings.
Defaults to SCAN_TARGET_DIR env var or ./sample-data when no paths are given.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.process import run


def collect_files(paths: list[Path]) -> list[Path]:
    files = []
    for p in paths:
        if p.is_dir():
            files.extend(f for f in p.rglob("*") if f.is_file())
        elif p.is_file():
            files.append(p)
        else:
            print(f"[warn] path not found: {p}", file=sys.stderr)
    return files


if __name__ == "__main__":
    if len(sys.argv) > 1:
        roots = [Path(a) for a in sys.argv[1:]]
    else:
        default = os.getenv("SCAN_TARGET_DIR", "./sample-data")
        roots = [Path(default)]

    files = collect_files(roots)
    if not files:
        print("No files found to scan.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {len(files)} file(s)...\n")
    results = run(files)

    for result in results:
        status = f"{len(result.findings)} finding(s)" if result.has_pii else "clean"
        print(f"{result.file_path}  →  {status}")
        for f in result.findings:
            print(f"  [{f['category']}] [{f.get('source', '?')}] {f['snippet']}")
