# Medicaid Enrollment Vintage Tracker

**Catching silent revisions to US Medicaid enrollment data — the numbers that determine healthcare coverage for 79 million Americans.**

🔗 **Live dashboard:** [abhisek077.github.io/medicaid-enrollment-tracker/medicaid.html](https://abhisek077.github.io/medicaid-enrollment-tracker/medicaid.html)

---

## The problem

Every month, the Centers for Medicare & Medicaid Services (CMS) publishes how many people are enrolled in Medicaid and CHIP — the government health insurance programs that cover roughly 79 million low-income Americans.

These numbers get quietly revised after the fact. States resubmit corrections. Methodology changes. Old months get overwritten. CMS doesn't keep a record of what it published before.

If you downloaded the data in January and someone else downloaded it in March, you might have different numbers for the exact same month — and neither of you would know.

**This tracker downloads the full CMS dataset every day and records exactly what changed.** Nothing gets deleted. The archive only grows.

---

## Why it matters

Medicaid enrollment numbers directly determine:

- **Federal matching payments** — how much money Washington sends each state
- **Managed care capitation rates** — payments to insurers covering ~75% of Medicaid spending
- **Policy research** — studies on coverage gaps, the effects of eligibility changes, and who loses insurance
- **Journalism** — every story about healthcare access, state budgets, and federal cuts depends on these figures
- **Accountability** — when a state claims enrollment dropped for one reason, the revision history shows the actual sequence

When CMS silently changes a number, researchers using the old version reach different conclusions than those using the new one. This tracker makes that revision history permanent and public.

---

## The timing

This tracker launched during an unusually important moment:

- **25 million people lost Medicaid coverage** during the 2023–2024 "unwinding" when pandemic-era protections ended — the largest coverage disruption in the program's history
- **Active federal legislation** is changing Medicaid eligibility rules right now
- **CMS confirmed** that states routinely revise prior months' enrollment retroactively — KFF documented this pattern explicitly

This is the worst possible time to not have a revision archive.

---

## What gets tracked

| Field | What it means |
|---|---|
| `total_medicaid_and_chip_enrollment` | Everyone enrolled in Medicaid or CHIP combined |
| `total_medicaid_enrollment` | Medicaid-only enrollees |
| `total_chip_enrollment` | Children's Health Insurance Program enrollees |
| `total_medicaid_and_chip_determinations` | Eligibility decisions made |
| `medicaid_and_chip_child_enrollment` | Children enrolled |
| `total_adult_medicaid_enrollment` | Adults enrolled |

**Coverage:** All 50 states + DC + territories, every reporting month from 2013 onward.

**Source:** [CMS data.medicaid.gov](https://data.medicaid.gov/dataset/6165f45b-ca93-5bb5-9d06-db29c692a360) — public, no API key required.

CMS publishes two versions of each month: **Preliminary** (~1 week after close) and **Updated** (~1 month later). Both are tracked. Revisions to either version are logged.

---

## What's in this repo

```
data/
  vintages/
    medicaid_enrollment/
      2026-05-08.json.gz    ← full CMS snapshot, compressed (~15 KB)
      2026-05-09.json.gz
      ...                   ← one file per day, indefinitely
  revision_log_medicaid.csv ← every detected change, append-only

docs/
  medicaid.html             ← live dashboard (auto-generated)

scripts/
  tracker_medicaid.py           ← fetches data, diffs, saves snapshots
  generate_medicaid_dashboard.py ← builds dashboard from the data

.github/
  workflows/
    medicaid_tracker.yml    ← runs everything daily at 8 AM UTC
```

### Storage

The raw CMS dataset is ~27 MB. Each daily snapshot is stripped of empty fields and gzip-compressed to **~15 KB**. That's about **5 MB per year** — meaning this tracker can run for decades on GitHub's free tier without hitting any limits.

Every daily file is a complete snapshot of the entire dataset as it appeared on that date. No information is lost. Any two files can be compared to independently verify any claimed revision.

### The revision log

`data/revision_log_medicaid.csv` — every row is one detected change:

| Column | What it means |
|---|---|
| `detected_date` | When we noticed the change |
| `previous_vintage_date` | What we're comparing against |
| `state_name` | Which state |
| `report_date` | Which reporting month (YYYYMM format) |
| `data_type` | `P` = Preliminary, `U` = Updated |
| `field` | Which number changed |
| `old_value` | What it said before |
| `new_value` | What it says now |

Special event types: `ROW_ADDED` (new state-month appeared), `ROW_DELETED` (a row was removed from the dataset).

---

## How to use this data

**Researchers:** Download any `.json.gz` file from `data/vintages/medicaid_enrollment/` — it's standard gzip-compressed JSON, readable in Python (`gzip.open`), R, or any tool. Use `revision_log_medicaid.csv` to identify which state-month pairs were revised and by how much.

```python
import gzip, json

with gzip.open("data/vintages/medicaid_enrollment/2026-05-08.json.gz", "rt") as f:
    records = json.load(f)

# Each record has: state_name, reporting_period, preliminary_or_updated,
# total_medicaid_and_chip_enrollment, etc.
```

**Journalists:** Filter the revision log by state. Look for large changes to recently published months — those are the silent corrections worth investigating.

**Everyone else:** The [live dashboard](https://abhisek077.github.io/medicaid-enrollment-tracker/medicaid.html) shows current enrollment by state and every revision caught, updated daily.

**Citation:**
> Gupta, A. (2026). Medicaid Enrollment Vintage Tracker [Dataset]. GitHub. https://github.com/Abhisek077/medicaid-enrollment-tracker

---

## Revision semantics

> When this archive records a value for State X, Report Month Y on Date Z, it means: **that was the value returned by the CMS API on Date Z, before any subsequent revision.**

This is the standard vintage-archive definition, consistent with how the [Philadelphia Fed's ALFRED](https://alfred.stlouisfed.org/) handles national economic data.

---

## How it runs

- A Python script runs automatically every day at 8 AM UTC via GitHub Actions (free)
- Downloads all ~10,600 records from the CMS public API (no authentication needed)
- Compares each record against the previous day's snapshot
- Logs any field-level differences to the revision CSV
- Saves the full snapshot as compressed JSON (~15 KB)
- Rebuilds the dashboard HTML
- Commits and pushes everything automatically

No server. No API keys. No cost. Runs indefinitely.

---

## Related

This tracker is part of a broader effort to document silent revisions in US federal statistics:

🔗 [Government Statistics Vintage Tracker](https://abhisek077.github.io/govt-stats-tracker) — covers BLS unemployment, BEA GDP, CDC mortality, EPA air quality, HUD housing data, and more.

---

## Contributing

Found a revision this tracker missed? Have a question about the data? Open an issue.

*Not affiliated with CMS, HHS, or any federal agency. All data is from public government APIs.*

## Citation

If you use this data in research, journalism, or policy work, please cite:

> Gupta, A. (2026). Medicaid Enrollment Vintage Tracker (v1.0.0) [Dataset]. 
> Zenodo. https://doi.org/10.5281/zenodo.20091323

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20091323.svg)](https://doi.org/10.5281/zenodo.20091323)
