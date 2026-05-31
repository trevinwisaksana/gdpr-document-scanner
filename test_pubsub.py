"""
End-to-end local pipeline test using the Pub/Sub emulator.
Runs: listing → extraction topic → extraction consumer → scanner topic → scanner consumer

Usage:
  1. Fill in SOURCE_FOLDER_ID in .env
  2. python test_pubsub.py
"""

import json
import os
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Point all Pub/Sub clients to the emulator
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"

PROJECT_ID = "local-test"
EXTRACTION_TOPIC        = f"projects/{PROJECT_ID}/topics/extraction"
EXTRACTION_SUBSCRIPTION = f"projects/{PROJECT_ID}/subscriptions/extraction-sub"
SCANNER_TOPIC           = f"projects/{PROJECT_ID}/topics/scanner"
SCANNER_SUBSCRIPTION    = f"projects/{PROJECT_ID}/subscriptions/scanner-sub"


# ── emulator lifecycle ────────────────────────────────────────────────────────

def start_emulator() -> subprocess.Popen:
    print("Starting Pub/Sub emulator (Docker)...")
    proc = subprocess.Popen(
        [
            "docker", "run", "--rm",
            "-p", "8085:8085",
            "gcr.io/google.com/cloudsdktool/cloud-sdk:emulators",
            "gcloud", "beta", "emulators", "pubsub", "start",
            f"--project={PROJECT_ID}",
            "--host-port=0.0.0.0:8085",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import socket
    for _ in range(40):
        try:
            with socket.create_connection(("localhost", 8085), timeout=1):
                print("Emulator ready")
                return proc
        except OSError:
            time.sleep(1)
    proc.kill()
    raise RuntimeError("Pub/Sub emulator failed to start")


def stop_emulator(proc: subprocess.Popen) -> None:
    print("Stopping emulator...")
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── setup ─────────────────────────────────────────────────────────────────────

def setup_topics_and_subscriptions() -> None:
    from google.api_core.exceptions import AlreadyExists
    from google.cloud import pubsub_v1

    publisher  = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    for topic in [EXTRACTION_TOPIC, SCANNER_TOPIC]:
        try:
            publisher.create_topic(request={"name": topic})
        except AlreadyExists:
            pass

    for sub, topic in [
        (EXTRACTION_SUBSCRIPTION, EXTRACTION_TOPIC),
        (SCANNER_SUBSCRIPTION,    SCANNER_TOPIC),
    ]:
        try:
            subscriber.create_subscription(request={"name": sub, "topic": topic})
        except AlreadyExists:
            pass

    print(f"Topics and subscriptions ready")


# ── pipeline stages ───────────────────────────────────────────────────────────

def stage_listing() -> list[dict]:
    print("\n=== Stage 1: Listing ===")
    from app.gdrive_extractor import GDriveLister
    from google.cloud import pubsub_v1

    lister    = GDriveLister()
    publisher = pubsub_v1.PublisherClient()
    files     = list(lister.list_files())

    print(f"Found {len(files)} files — publishing to extraction topic")
    for file in files:
        publisher.publish(EXTRACTION_TOPIC, json.dumps(file).encode("utf-8")).result()

    return files


def stage_extraction(num_messages: int) -> None:
    print("\n=== Stage 2: Extraction consumer ===")
    from app.gdrive_downloader import GDriveDownloader
    from google.cloud import pubsub_v1

    subscriber = pubsub_v1.SubscriberClient()
    publisher  = pubsub_v1.PublisherClient()
    downloader = GDriveDownloader()

    with subscriber:
        response = subscriber.pull(
            request={"subscription": EXTRACTION_SUBSCRIPTION, "max_messages": num_messages},
            timeout=10,
        )
        ack_ids = []
        for received in response.received_messages:
            file = json.loads(received.message.data.decode("utf-8"))
            try:
                text = downloader.download_and_extract(
                    file["file_id"], file["mime_type"], file["name"]
                )
                publisher.publish(
                    SCANNER_TOPIC,
                    json.dumps({"file_id": file["file_id"], "name": file["name"], "text": text}).encode("utf-8"),
                ).result()
                ack_ids.append(received.ack_id)
                print(f"  Extracted: {file['name']} ({len(text)} chars)")
            except Exception as exc:
                print(f"  FAILED: {file['name']} — {exc}")

        if ack_ids:
            subscriber.acknowledge(
                request={"subscription": EXTRACTION_SUBSCRIPTION, "ack_ids": ack_ids}
            )


def stage_scanner(num_messages: int) -> None:
    print("\n=== Stage 3: Scanner consumer ===")
    from app.process import scan_text
    from google.cloud import pubsub_v1

    subscriber = pubsub_v1.SubscriberClient()

    with subscriber:
        response = subscriber.pull(
            request={"subscription": SCANNER_SUBSCRIPTION, "max_messages": num_messages},
            timeout=10,
        )
        ack_ids = []
        for received in response.received_messages:
            payload = json.loads(received.message.data.decode("utf-8"))
            try:
                result = scan_text(payload["text"], payload["file_id"])
                ack_ids.append(received.ack_id)
                print(f"  Scanned: {payload['name']} | has_pii={result.has_pii} | findings={len(result.findings)}")
                for f in result.findings[:5]:
                    print(f"    [{f['category']}] {f['snippet']!r}  confidence={f.get('confidence')}")
                if len(result.findings) > 5:
                    print(f"    ... and {len(result.findings) - 5} more")
            except Exception as exc:
                print(f"  FAILED: {payload.get('name')} — {exc}")

        if ack_ids:
            subscriber.acknowledge(
                request={"subscription": SCANNER_SUBSCRIPTION, "ack_ids": ack_ids}
            )


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    emulator = start_emulator()
    try:
        setup_topics_and_subscriptions()
        files = stage_listing()
        if files:
            stage_extraction(len(files))
            stage_scanner(len(files))
        print("\nDone.")
    finally:
        stop_emulator(emulator)
