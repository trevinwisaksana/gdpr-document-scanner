"""
GDPR Scanner Benchmark
======================
Benchmarks the actual production pipeline used by the scanner consumer:
  1. Regex          (detectors/regex.py)
  2. Regex + NER    (+ Azure NER fallback)
  3. Full pipeline  (+ LLM verify / LLM fallback via OpenRouter/Qwen)

Usage:
    # Run against staging Google Drive (1036 files)
    python benchmark.py --staging [--sample N] [--no-llm] [--no-ner]

    # Run against local test dataset
    python benchmark.py --dataset ~/Desktop/test_dataset [--sample N]

Output:
    benchmark_results.json  — raw per-file data
    benchmark_report.txt    — human-readable summary
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from app.extraction.reader import extract_text
from detectors.regex import detect_pii, RegexDetectorConfig


# ── clean file generation ─────────────────────────────────────────────────────

CLEAN_TEXTS = [
    "The quarterly board meeting will be held in the main conference room. Agenda items include budget review, project status updates, and strategic planning for Q3.",
    "Please ensure all server configurations are updated before the maintenance window on Sunday. The deployment pipeline has been tested in the staging environment.",
    "The new product launch is scheduled for next month. Marketing materials are being finalised. Distribution channels have been confirmed with the logistics team.",
    "Annual fire safety inspection has been completed. All fire exits are clear and extinguishers are within service date. Report filed with building management.",
    "System uptime for this month was 99.97%. Two minor incidents were logged, both resolved within SLA. Full report available in the operations dashboard.",
    "The training session on workplace safety has been rescheduled to next Tuesday at 10am. All department heads should ensure attendance of their teams.",
    "Inventory levels for Q2 have been updated in the ERP system. Reorder points have been adjusted based on demand forecasting models.",
    "The software update introduces improved caching mechanisms and resolves three known bugs. Rollback procedure is documented in the runbook.",
    "Supplier performance reviews for the current quarter have been completed. Overall scores improved by 8% compared to the previous period.",
    "The research paper on renewable energy storage systems has been submitted for peer review. Three reviewers have been assigned by the editorial board.",
]


def generate_clean_files(out_dir: Path, n: int = 50) -> list[Path]:
    clean_dir = out_dir / "clean_control"
    clean_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for i in range(n):
        p = clean_dir / f"clean_{i+1:03d}.txt"
        p.write_text(random.choice(CLEAN_TEXTS))
        created.append(p)
    return created


def collect_files(dataset_dir: Path) -> tuple[list[Path], list[Path]]:
    pii, clean = [], []
    for p in sorted(dataset_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".txt", ".pdf", ".docx", ".xlsx", ".csv", ".pptx"}:
            continue
        (clean if p.stem.startswith("internal_memo_") else pii).append(p)
    return pii, clean


# ── detector runners ──────────────────────────────────────────────────────────

def run_regex(text: str) -> list[dict]:
    return detect_pii(text)


def run_regex_ner(text: str) -> list[dict]:
    from app.detection.ner import ner_inference
    from app.process import _ner_to_findings

    findings = detect_pii(text)
    if not findings:
        try:
            ner_entities = ner_inference(text)
            findings = _ner_to_findings(ner_entities)
        except Exception as e:
            print(f"[NER] failed: {e}")
    return findings


def run_full(text: str) -> list[dict]:
    from app.process import scan_text
    result = scan_text(text, "benchmark")
    return result.findings


# ── scoring ───────────────────────────────────────────────────────────────────

def score_file(findings: list[dict], is_pii: bool) -> dict:
    has = len(findings) > 0
    if is_pii:
        return {"tp": 1 if has else 0, "fp": 0, "fn": 0 if has else 1, "n_findings": len(findings)}
    else:
        return {"tp": 0, "fp": 1 if has else 0, "fn": 0, "n_findings": len(findings)}


# ── benchmark engine ──────────────────────────────────────────────────────────

def benchmark_detector(name: str, run_fn, pii_files: list[Path], clean_files: list[Path]) -> dict:
    total_tp = total_fp = total_fn = errors = 0
    times, per_file = [], []

    for path, is_pii in [(p, True) for p in pii_files] + [(p, False) for p in clean_files]:
        try:
            text = extract_text(str(path))
        except Exception as e:
            errors += 1
            continue

        t0 = time.perf_counter()
        try:
            findings = run_fn(text)
        except Exception as e:
            errors += 1
            continue
        elapsed = time.perf_counter() - t0

        times.append(elapsed)
        s = score_file(findings, is_pii)
        total_tp += s["tp"]; total_fp += s["fp"]; total_fn += s["fn"]
        per_file.append({
            "file": str(path),
            "is_pii": is_pii,
            "n_findings": s["n_findings"],
            "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
            "time_s": round(elapsed, 4),
        })

    n = len(times)
    times_s = sorted(times)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    recall    = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    fpr       = total_fp / len(clean_files) if clean_files else 0

    return {
        "detector": name,
        "files_processed": n,
        "errors": errors,
        "tp": total_tp, "fp": total_fp, "fn": total_fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "timing": {
            "total_s": round(sum(times), 2),
            "mean_ms": round(1000 * sum(times) / n, 1) if n else 0,
            "p50_ms":  round(1000 * times_s[n // 2], 1) if n else 0,
            "p95_ms":  round(1000 * times_s[int(n * 0.95)], 1) if n else 0,
            "p99_ms":  round(1000 * times_s[int(n * 0.99)], 1) if n else 0,
        },
        "per_file": per_file,
    }


# ── report ────────────────────────────────────────────────────────────────────

def print_report(results: list[dict], dataset_dir: Path, out_path: Path) -> None:
    lines = ["=" * 65, "GDPR SCANNER BENCHMARK REPORT", f"Dataset : {dataset_dir}", "=" * 65]
    for r in results:
        n_clean = sum(1 for f in r["per_file"] if not f["is_pii"])
        lines += [
            f"\n── {r['detector'].upper()} ──",
            f"  Files processed   : {r['files_processed']}  (errors: {r['errors']})",
            f"  TP / FP / FN      : {r['tp']} / {r['fp']} / {r['fn']}",
            f"  Precision         : {r['precision']:.1%}",
            f"  Recall            : {r['recall']:.1%}",
            f"  F1 score          : {r['f1']:.1%}",
            f"  False pos. rate   : {r['false_positive_rate']:.1%}  ({n_clean} clean files)",
            f"  Total time        : {r['timing']['total_s']}s",
            f"  Mean / p50 / p95 / p99 (ms) : "
            f"{r['timing']['mean_ms']} / {r['timing']['p50_ms']} / "
            f"{r['timing']['p95_ms']} / {r['timing']['p99_ms']}",
        ]
    lines.append("\n" + "=" * 65)
    report = "\n".join(lines)
    print(report)
    out_path.write_text(report)
    print(f"\nReport saved to: {out_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def collect_staging_files(sample: int = 0) -> tuple[list[dict], list[dict]]:
    """List files from staging Google Drive. Returns (pii_files, clean_files)."""
    from app.drive.extractor import GDriveLister

    print("Listing files from staging Google Drive ...")
    lister = GDriveLister()
    all_files = list(lister.list_files())
    print(f"Found {len(all_files)} files in Drive.")

    pii = [f for f in all_files if not Path(f["name"]).stem.startswith("internal_memo_")]
    clean = [f for f in all_files if Path(f["name"]).stem.startswith("internal_memo_")]

    if sample and sample < len(pii):
        random.seed(99)
        pii = random.sample(pii, sample)

    return pii, clean


def benchmark_detector_staging(name: str, run_fn, pii_files: list[dict], clean_files: list[dict]) -> dict:
    """Benchmark against staging Drive files (downloaded on the fly)."""
    from app.drive.downloader import GDriveDownloader
    downloader = GDriveDownloader()

    total_tp = total_fp = total_fn = errors = 0
    times, per_file = [], []

    for f, is_pii in [(f, True) for f in pii_files] + [(f, False) for f in clean_files]:
        try:
            text = downloader.download_and_extract(f["file_id"], f["mime_type"], f["name"])
        except Exception as e:
            print(f"  [skip] {f['name']}: {e}")
            errors += 1
            continue

        t0 = time.perf_counter()
        try:
            findings = run_fn(text)
        except Exception as e:
            errors += 1
            continue
        elapsed = time.perf_counter() - t0

        times.append(elapsed)
        s = score_file(findings, is_pii=is_pii)
        total_tp += s["tp"]; total_fn += s["fn"]; total_fp += s["fp"]
        per_file.append({
            "file": f["name"], "is_pii": is_pii,
            "n_findings": s["n_findings"], "tp": s["tp"], "fn": s["fn"], "fp": s["fp"],
            "time_s": round(elapsed, 4),
        })

    n = len(times)
    times_s = sorted(times)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    recall    = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    fpr       = total_fp / len(clean_files) if clean_files else 0

    return {
        "detector": name,
        "files_processed": n,
        "errors": errors,
        "tp": total_tp, "fp": total_fp, "fn": total_fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "timing": {
            "total_s":  round(sum(times), 2),
            "mean_ms":  round(1000 * sum(times) / n, 1) if n else 0,
            "p50_ms":   round(1000 * times_s[n // 2], 1) if n else 0,
            "p95_ms":   round(1000 * times_s[int(n * 0.95)], 1) if n else 0,
            "p99_ms":   round(1000 * times_s[int(n * 0.99)], 1) if n else 0,
        },
        "per_file": per_file,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", action="store_true", help="Pull files from staging Google Drive")
    parser.add_argument("--dataset", default=os.path.expanduser("~/Desktop/test_dataset"))
    parser.add_argument("--sample", type=int, default=0, help="Sample N PII files (0 = all)")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--no-ner", action="store_true")
    args = parser.parse_args()

    # ── file collection ───────────────────────────────────────────────────────
    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        sys.exit(f"Dataset not found: {dataset_dir}")

    _, clean_files = collect_files(dataset_dir)
    if not clean_files:
        print("Generating 50 clean control files ...")
        clean_files = generate_clean_files(dataset_dir)

    if args.staging:
        drive_files = collect_staging_files(sample=args.sample)
        print(f"PII files  : {len(drive_files)}  (from staging Drive)")
        print(f"Clean files: {len(clean_files)}  (from {dataset_dir})\n")
    else:
        _, pii_files_all = [], []
        pii_files, _ = collect_files(dataset_dir)
        if args.sample and args.sample < len(pii_files):
            random.seed(99)
            pii_files = random.sample(pii_files, args.sample)
        print(f"PII files  : {len(pii_files)}")
        print(f"Clean files: {len(clean_files)}\n")

    detectors = [("Regex", run_regex)]

    if not args.no_ner:
        if os.getenv("NER_SUBSCRIPTION_KEY"):
            detectors.append(("Regex + Azure NER", run_regex_ner))
        else:
            print("NER_SUBSCRIPTION_KEY not set — skipping NER stage.\n")

    if not args.no_llm:
        if os.getenv("OPENROUTER_API_KEY"):
            detectors.append(("Full pipeline (Regex + NER + LLM)", run_full))
        else:
            print("OPENROUTER_API_KEY not set — skipping LLM stage.\n")

    all_results = []
    for name, fn in detectors:
        print(f"Running: {name} ...")
        t0 = time.perf_counter()
        if args.staging:
            result = benchmark_detector_staging(name, fn, drive_files, clean_files)
        else:
            result = benchmark_detector(name, fn, pii_files, clean_files)
        print(f"  Done in {time.perf_counter()-t0:.1f}s — F1={result['f1']:.1%}  precision={result['precision']:.1%}  recall={result['recall']:.1%}\n")
        all_results.append(result)

    json_path = ROOT / "benchmark_results.json"
    report_path = ROOT / "benchmark_report.txt"

    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Raw results: {json_path}\n")
    print_report(all_results, dataset_dir, report_path)


if __name__ == "__main__":
    main()
