"""Hand-labeled precision/recall over a subset of sample-data.

Ground truth is instance-level: each entry is a (category, snippet-substring) pair a
human reviewer marked as genuine personal data. A detection counts as a true positive
when its category matches and its snippet contains the labeled substring. Everything the
detector emits beyond the labels is a false positive; every label left undetected is a
false negative.

Run: python -m scanner.accuracy
The number printed is produced live from the detectors — nothing here is hardcoded.
"""
from __future__ import annotations

from pathlib import Path

from app.file_reader import extract_text
from scanner import detectors, gdpr

# (category, expected snippet substring) per file. Labeled by hand from the rendered PDFs.
GROUND_TRUTH: dict[str, list[tuple[str, str]]] = {
    "Expense_Report_Example_A.pdf": [
        (gdpr.NAME, "Sara Hoffmann"), (gdpr.NAME, "Philipp Neumann"),
        (gdpr.USERNAME, "E-20491"),
    ],
    "Expense_Report_Example_B.pdf": [
        (gdpr.NAME, "David Schmid"), (gdpr.NAME, "Laura König"),
        (gdpr.USERNAME, "E-31705"),
    ],
    "IT_Access_Request_Example_A.pdf": [
        (gdpr.NAME, "Elena Fischer"), (gdpr.NAME, "Jonas Keller"),
        (gdpr.NAME, "J. Keller"), (gdpr.SIGNATURE, "J. Keller"),
    ],
    "IT_Access_Request_Example_B.pdf": [
        (gdpr.NAME, "Tobias Wagner"), (gdpr.NAME, "Miriam Braun"),
        (gdpr.NAME, "M. Braun"), (gdpr.SIGNATURE, "M. Braun"),
    ],
    "Supplier_Onboarding_Example_A.pdf": [
        (gdpr.EMAIL, "procurement@nordic-components.example"),
        (gdpr.HOME_ADDRESS, "Hauptstr. 12, 70173 Stuttgart"),
        (gdpr.ID_CARD, "DE123456789"),
    ],
    "Supplier_Onboarding_Example_B.pdf": [
        (gdpr.EMAIL, "vendor@alpine-services.example"),
        (gdpr.HOME_ADDRESS, "Industriestr. 8, 80331 München"),
        (gdpr.ID_CARD, "DE987654321"),
    ],
    # Reports with only roles / locations — no direct identifiers. Negative controls.
    "Incident_Report_Example_A.pdf": [],
    "Incident_Report_Example_B.pdf": [],
    "Training_Evaluation_Example_A.pdf": [(gdpr.NAME, "Nina Beck")],
    "Training_Evaluation_Example_B.pdf": [(gdpr.NAME, "Markus Steiner")],
}

SAMPLE_DIR = Path("sample-data")


def _detections(filename: str) -> list[dict]:
    p = SAMPLE_DIR / filename
    text = extract_text(p.read_bytes(), filename).get("full_text", "") or ""
    return detectors.detect_categories(text)


def score() -> dict:
    tp = fp = fn = 0
    fp_items: list[tuple[str, str, str]] = []
    fn_items: list[tuple[str, str, str]] = []

    for filename, labels in GROUND_TRUTH.items():
        dets = _detections(filename)
        unmatched = list(labels)
        for d in dets:
            hit = next(
                (l for l in unmatched
                 if l[0] == d["category"] and l[1] in d["snippet"]),
                None,
            )
            if hit:
                tp += 1
                unmatched.remove(hit)
            else:
                fp += 1
                fp_items.append((filename, d["category"], d["snippet"]))
        for cat, snip in unmatched:
            fn += 1
            fn_items.append((filename, cat, snip))

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "fp_items": fp_items, "fn_items": fn_items,
        "files": len(GROUND_TRUTH),
        "labels": sum(len(v) for v in GROUND_TRUTH.values()),
    }


def main() -> None:
    r = score()
    print(f"Hand-labeled accuracy over {r['files']} files / {r['labels']} labeled items")
    print(f"  TP={r['tp']}  FP={r['fp']}  FN={r['fn']}")
    print(f"  precision={r['precision']:.3f}  recall={r['recall']:.3f}  F1={r['f1']:.3f}")
    if r["fp_items"]:
        print("  false positives:")
        for f, c, s in r["fp_items"]:
            print(f"    [{c}] {s!r}  ({f})")
    if r["fn_items"]:
        print("  misses:")
        for f, c, s in r["fn_items"]:
            print(f"    [{c}] {s!r}  ({f})")


if __name__ == "__main__":
    main()
