"""
tracker_medicaid.py — Medicaid & CHIP Monthly Enrollment Vintage Tracker
=========================================================================
Fetches the CMS Medicaid & CHIP monthly enrollment dataset from data.medicaid.gov,
diffs against the previous vintage, and logs any revisions to data/revision_log_medicaid.csv.

Data source:
  Dataset: "State Medicaid and CHIP Applications, Eligibility Determinations, and Enrollment"
  URL:     https://data.medicaid.gov/dataset/6165f45b-ca93-5bb5-9d06-db29c692a360
  API:     https://data.medicaid.gov/api/1/datastore/query/6165f45b-ca93-5bb5-9d06-db29c692a360/0

Why revisions matter:
  CMS publishes both Preliminary ("P") and Updated ("U") figures for each
  reporting month. States frequently revise their submissions retroactively.
  This script captures the value as it appeared on each fetch date so the
  before/after is permanently recorded — something CMS itself does not do.

Storage:
  Snapshots are saved as gzip-compressed JSON with null/empty fields stripped.
  Raw API response: ~27 MB -> compressed vintage: ~15 KB per day (~5 MB/year).
  This allows daily full snapshots indefinitely on GitHub free tier (1 GB limit).

Usage:
  python tracker_medicaid.py

Output:
  data/vintages/medicaid_enrollment/{YYYY-MM-DD}.json.gz  — compressed snapshot
  data/revision_log_medicaid.csv                          — append-only diff log
"""

import os
import json
import csv
import gzip
import hashlib
import requests
from datetime import date

# ── Configuration ─────────────────────────────────────────────────────────────

DATASET_ID   = "6165f45b-ca93-5bb5-9d06-db29c692a360"
API_BASE     = f"https://data.medicaid.gov/api/1/datastore/query/{DATASET_ID}/0"
SERIES_DIR   = "data/vintages/medicaid_enrollment"
REVISION_LOG = "data/revision_log_medicaid.csv"
PAGE_SIZE    = 1000   # records per API page

# Key fields — together they uniquely identify one row
KEY_FIELDS = [
    "state_name",
    "reporting_period",       # format: "202309" (YYYYMM)
    "preliminary_or_updated", # "U" = Updated, "P" = Preliminary
]

# Value fields — these are what we watch for revisions
VALUE_FIELDS = [
    "total_medicaid_and_chip_enrollment",
    "total_medicaid_enrollment",
    "total_chip_enrollment",
    "total_medicaid_and_chip_determinations",
    "medicaid_and_chip_child_enrollment",
    "total_adult_medicaid_enrollment",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_all_records() -> list[dict]:
    """Page through the API and return all records."""
    records = []
    offset  = 0

    while True:
        params = {"limit": PAGE_SIZE, "offset": offset}
        try:
            resp = requests.get(API_BASE, params=params, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [ERROR] API fetch failed at offset {offset}: {e}")
            raise

        data  = resp.json()
        batch = data.get("results", [])
        if not batch:
            break

        records.extend(batch)
        print(f"  Fetched {len(records)} records so far...")

        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return records


def slim_record(record: dict) -> dict:
    """Strip null values and empty strings to reduce storage size."""
    return {k: v for k, v in record.items() if v is not None and v != ""}


def make_row_key(record: dict) -> str:
    """Build a unique composite key from the key fields."""
    parts = [str(record.get(f, "")).strip() for f in KEY_FIELDS]
    return "||".join(parts)


def load_previous_vintage(series_dir: str) -> tuple[dict, str | None]:
    """
    Return (keyed_records, previous_date_str) for the most recent vintage file,
    or ({}, None) if no previous vintage exists.
    Supports both .json.gz (new) and .json (legacy) files.
    """
    if not os.path.isdir(series_dir):
        return {}, None

    files = sorted(os.listdir(series_dir), reverse=True)
    vintages = [f for f in files if f.endswith(".json.gz") or f.endswith(".json")]
    if not vintages:
        return {}, None

    latest = vintages[0]
    prev_date = latest.replace(".json.gz", "").replace(".json", "")
    path = os.path.join(series_dir, latest)

    if latest.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            records = json.load(f)
    else:
        with open(path) as f:
            records = json.load(f)

    keyed = {make_row_key(r): r for r in records}
    return keyed, prev_date


def save_vintage(records: list[dict], series_dir: str, today: str) -> None:
    """
    Save today's full snapshot as gzip-compressed JSON with null/empty fields
    stripped. ~27 MB raw -> ~15 KB compressed.
    """
    os.makedirs(series_dir, exist_ok=True)

    slim_records = [slim_record(r) for r in records]
    json_bytes   = json.dumps(slim_records, separators=(",", ":")).encode("utf-8")

    path = os.path.join(series_dir, f"{today}.json.gz")
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(json_bytes)

    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved vintage: {path} ({len(records)} records, {size_kb:.0f} KB compressed)")


def log_revision(
    revision_log: str,
    today: str,
    prev_date: str,
    row_key: str,
    field: str,
    old_val: str,
    new_val: str,
    state: str,
    report_date: str,
    data_type: str,
) -> None:
    """Append one revision event to the CSV log."""
    os.makedirs(os.path.dirname(revision_log), exist_ok=True)
    write_header = not os.path.exists(revision_log)

    with open(revision_log, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "detected_date",
                "previous_vintage_date",
                "state_name",
                "report_date",
                "data_type",
                "field",
                "old_value",
                "new_value",
                "source",
            ])
        writer.writerow([
            today,
            prev_date,
            state,
            report_date,
            data_type,
            field,
            old_val,
            new_val,
            "data.medicaid.gov",
        ])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = date.today().isoformat()
    print(f"\n{'='*60}")
    print(f"Medicaid Enrollment Tracker — {today}")
    print(f"{'='*60}")

    # 1. Fetch current data
    print("\n[1] Fetching from data.medicaid.gov...")
    try:
        records = fetch_all_records()
    except Exception as e:
        print(f"  FATAL: Could not fetch data — {e}")
        return

    if not records:
        print("  WARNING: API returned 0 records. Skipping save.")
        return

    print(f"  Total records fetched: {len(records)}")

    # 2. Load previous vintage
    print(f"\n[2] Loading previous vintage from {SERIES_DIR}...")
    prev_keyed, prev_date = load_previous_vintage(SERIES_DIR)

    if prev_date:
        print(f"  Previous vintage: {prev_date} ({len(prev_keyed)} records)")
    else:
        print("  No previous vintage found — this is the first snapshot.")

    # 3. Diff
    print("\n[3] Diffing against previous vintage...")
    curr_keyed = {make_row_key(r): r for r in records}

    revisions_found = 0
    new_rows        = 0
    deleted_rows    = 0

    if prev_date:
        for key, curr_record in curr_keyed.items():
            state       = curr_record.get("state_name", "")
            report_date = curr_record.get("reporting_period", "")
            data_type   = curr_record.get("preliminary_or_updated", "")

            if key not in prev_keyed:
                new_rows += 1
                log_revision(
                    REVISION_LOG, today, prev_date,
                    key, "ROW_ADDED", "", "new_record",
                    state, report_date, data_type,
                )
                continue

            prev_record = prev_keyed[key]

            for field in VALUE_FIELDS:
                old_val = str(prev_record.get(field, "")).strip()
                new_val = str(curr_record.get(field, "")).strip()
                if old_val != new_val:
                    revisions_found += 1
                    log_revision(
                        REVISION_LOG, today, prev_date,
                        key, field, old_val, new_val,
                        state, report_date, data_type,
                    )
                    print(f"  REVISION: {state} | {report_date} | {data_type} | {field}: {old_val!r} -> {new_val!r}")

        for key in prev_keyed:
            if key not in curr_keyed:
                deleted_rows += 1
                prev_record = prev_keyed[key]
                log_revision(
                    REVISION_LOG, today, prev_date,
                    key, "ROW_DELETED", "existed", "",
                    prev_record.get("state_name", ""),
                    prev_record.get("reporting_period", ""),
                    prev_record.get("preliminary_or_updated", ""),
                )
                print(f"  DELETED ROW: {key}")

        print(f"\n  Summary: {revisions_found} field revisions | {new_rows} new rows | {deleted_rows} deleted rows")
    else:
        print("  First run — skipping diff, saving baseline vintage.")

    # 4. Save today's vintage (compressed)
    print(f"\n[4] Saving today's vintage (compressed)...")
    save_vintage(records, SERIES_DIR, today)

    print(f"\n{'='*60}")
    print(f"Done. Revision log: {REVISION_LOG}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
