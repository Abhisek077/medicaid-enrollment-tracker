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
  CMS publishes both Preliminary and Updated figures for each reporting month.
  States frequently revise their submissions retroactively. This script captures
  the value as it appeared on each fetch date so the before/after is permanently
  recorded — something CMS itself does not do.

Schema (key fields tracked):
  - state_name        : State or territory name
  - report_date       : Reporting month (YYYY-MM format)
  - data_type         : "Preliminary" or "Updated"
  - total_medicaid_chip_enrollment : Total Medicaid + CHIP enrollees
  - medicaid_enrollment            : Medicaid-only enrollees
  - chip_enrollment                : Separate CHIP enrollees

Usage:
  python tracker_medicaid.py

Output:
  data/vintages/medicaid_enrollment/{YYYY-MM-DD}.json  — full snapshot
  data/revision_log_medicaid.csv                       — append-only diff log
"""

import os
import json
import csv
import hashlib
import requests
from datetime import date, datetime

# ── Configuration ─────────────────────────────────────────────────────────────

DATASET_ID  = "6165f45b-ca93-5bb5-9d06-db29c692a360"
API_BASE    = f"https://data.medicaid.gov/api/1/datastore/query/{DATASET_ID}/0"
SERIES_DIR  = "data/vintages/medicaid_enrollment"
REVISION_LOG = "data/revision_log_medicaid.csv"
PAGE_SIZE   = 1000   # records per API page

# Fields we track for revision detection (must be stable column names)
# Adjust if CMS renames columns — check the API response on first run.
KEY_FIELDS = [
    "state_name",
    "report_date",
    "data_type",
]
VALUE_FIELDS = [
    "total_medicaid_chip_enrollment",
    "medicaid_enrollment",
    "chip_enrollment",
    "total_medicaid_and_chip_applications",
    "total_eligibility_determinations",
    "total_individuals_determined_eligible",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_all_records() -> list[dict]:
    """Page through the Socrata API and return all records."""
    records = []
    offset  = 0

    while True:
        params = {
            "limit":  PAGE_SIZE,
            "offset": offset,
        }
        try:
            resp = requests.get(API_BASE, params=params, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [ERROR] API fetch failed at offset {offset}: {e}")
            raise

        data = resp.json()

        # data.medicaid.gov wraps results under "results" key
        batch = data.get("results", [])
        if not batch:
            break

        records.extend(batch)
        print(f"  Fetched {len(records)} records so far...")

        # If we got fewer records than PAGE_SIZE, we've reached the end
        if len(batch) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return records


def make_row_key(record: dict) -> str:
    """Build a unique composite key from the key fields."""
    parts = [str(record.get(f, "")).strip() for f in KEY_FIELDS]
    return "||".join(parts)


def make_row_hash(record: dict) -> str:
    """Hash the value fields to detect changes."""
    parts = [str(record.get(f, "")).strip() for f in VALUE_FIELDS]
    content = "||".join(parts)
    return hashlib.md5(content.encode()).hexdigest()


def load_previous_vintage(series_dir: str) -> tuple[dict, str | None]:
    """
    Return (keyed_records, previous_date_str) for the most recent vintage file,
    or ({}, None) if no previous vintage exists.
    """
    if not os.path.isdir(series_dir):
        return {}, None

    vintages = sorted(
        [f for f in os.listdir(series_dir) if f.endswith(".json")],
        reverse=True,
    )
    if not vintages:
        return {}, None

    latest = vintages[0]
    prev_date = latest.replace(".json", "")
    path = os.path.join(series_dir, latest)

    with open(path) as f:
        records = json.load(f)

    keyed = {make_row_key(r): r for r in records}
    return keyed, prev_date


def save_vintage(records: list[dict], series_dir: str, today: str) -> None:
    """Save today's full snapshot as a dated JSON file."""
    os.makedirs(series_dir, exist_ok=True)
    path = os.path.join(series_dir, f"{today}.json")
    with open(path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"  Saved vintage: {path} ({len(records)} records)")


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
    today = date.today().isoformat()  # e.g. "2025-05-08"
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
        # Check for changed or new rows
        for key, curr_record in curr_keyed.items():
            state       = curr_record.get("state_name", "")
            report_date = curr_record.get("report_date", "")
            data_type   = curr_record.get("data_type", "")

            if key not in prev_keyed:
                new_rows += 1
                # Log new rows as a revision event so we capture new months appearing
                log_revision(
                    REVISION_LOG, today, prev_date,
                    key, "ROW_ADDED", "", "new_record",
                    state, report_date, data_type,
                )
                continue

            prev_record = prev_keyed[key]

            # Field-level diff on value fields
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
                    print(f"  REVISION: {state} | {report_date} | {data_type} | {field}: {old_val!r} → {new_val!r}")

        # Check for deleted rows
        for key in prev_keyed:
            if key not in curr_keyed:
                deleted_rows += 1
                prev_record = prev_keyed[key]
                log_revision(
                    REVISION_LOG, today, prev_date,
                    key, "ROW_DELETED", "existed", "",
                    prev_record.get("state_name", ""),
                    prev_record.get("report_date", ""),
                    prev_record.get("data_type", ""),
                )
                print(f"  DELETED ROW: {key}")

        print(f"\n  Summary: {revisions_found} field revisions | {new_rows} new rows | {deleted_rows} deleted rows")
    else:
        print("  First run — skipping diff, saving baseline vintage.")

    # 4. Save today's vintage
    print(f"\n[4] Saving today's vintage...")
    save_vintage(records, SERIES_DIR, today)

    # 5. Done
    print(f"\n{'='*60}")
    print(f"Done. Revision log: {REVISION_LOG}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
