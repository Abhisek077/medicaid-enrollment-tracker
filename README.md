# Medicaid Enrollment Vintage Tracker

**What this is:** A public archive that catches when the US government quietly changes its own Medicaid enrollment numbers — and records exactly what changed, when, and by how much.

🔗 **Live dashboard:** [abhisek077.github.io/medicaid-enrollment-tracker](https://abhisek077.github.io/medicaid-enrollment-tracker)

---

## The problem this solves

Every month, the Centers for Medicare & Medicaid Services (CMS) publishes how many Americans are enrolled in Medicaid and CHIP — the government health insurance programs covering roughly 79 million low-income people.

But here's what most people don't know: **those numbers get revised after the fact, silently, with no announcement.**

States submit corrections. Methodology changes. Old months get updated. CMS overwrites the live database without keeping a record of what it said before. If you downloaded the data in January and someone else downloaded it in March, you might have different numbers for the same month — and there's no official record of that difference.

**This tracker is that record.**

Every day, this system automatically downloads the full CMS dataset and compares it to yesterday's copy. If anything changed — any state, any month, any number — it logs the before and after value with a timestamp. Nothing gets deleted. The archive only grows.

---

## Why it matters

Medicaid enrollment numbers are not just statistics. They determine:

- **Federal matching payments** — how much money the federal government sends each state for Medicaid
- **Policy research** — studies on coverage gaps, the effect of policy changes, who loses insurance and when
- **Journalism** — stories about healthcare access, state budget decisions, and the effects of federal cuts
- **Accountability** — when a state claims its enrollment dropped for one reason, the vintage record shows the actual sequence of events

When the numbers change silently, researchers working with the "old" version reach different conclusions than researchers working with the "new" version. Nobody can tell which version a given paper used. This archive makes the revision history permanent and public.

---

## The context right now (May 2026)

This tracker launched during an unusually important moment for Medicaid data:

- **25 million people lost Medicaid coverage** during the 2023–2024 "unwinding" — when pandemic-era continuous enrollment ended and states resumed eligibility checks. That's the largest coverage disruption in Medicaid's history.
- **New cuts are in progress** under current federal legislation. Enrollment is actively changing.
- **CMS retracted and corrected a Medicare Advantage enrollment report in January 2025** — proving that silent revisions to federal health enrollment data are a real, documented phenomenon, not a hypothetical.

This is the worst possible time to not have a revision archive. So we built one.

---

## What gets tracked

**Source:** [CMS Medicaid & CHIP Enrollment Data](https://data.medicaid.gov/dataset/6165f45b-ca93-5bb5-9d06-db29c692a360)

**Coverage:** All 50 states + DC, every reporting month available

**Cadence:** Daily snapshot. CMS updates the dataset monthly, but we check daily so we catch the exact day any revision appears.

**Fields tracked per state per month:**
| Field | What it means |
|---|---|
| `total_medicaid_chip_enrollment` | Everyone enrolled in Medicaid or CHIP |
| `medicaid_enrollment` | Medicaid-only enrollees |
| `chip_enrollment` | Children's Health Insurance Program enrollees |
| `total_medicaid_and_chip_applications` | Applications submitted |
| `total_eligibility_determinations` | Eligibility decisions made |
| `total_individuals_determined_eligible` | People approved |

CMS publishes two versions of each month:
- **Preliminary** — published ~1 week after the reporting period closes
- **Updated** — published ~1 month later, incorporating state corrections

Both are tracked. The transition from Preliminary to Updated, and any further retroactive changes, are all logged.

---

## What's in this repo

```
data/
  vintages/
    medicaid_enrollment/
      2025-05-08.json     ← full CMS dataset snapshot on that date
      2025-05-09.json
      ...                 ← one file per day, forever
  revision_log_medicaid.csv  ← every detected change, append-only
docs/
  index.html              ← the live dashboard
scripts/
  tracker_medicaid.py         ← fetches data, detects revisions, saves snapshots
  generate_medicaid_dashboard.py  ← builds the dashboard from the data
.github/
  workflows/
    medicaid_tracker.yml  ← runs everything automatically every day at 8 AM UTC
```

### The revision log

`data/revision_log_medicaid.csv` is the core output. Every row is one detected change:

| Column | Meaning |
|---|---|
| `detected_date` | The date we noticed the change |
| `previous_vintage_date` | What we're comparing against |
| `state_name` | Which state's number changed |
| `report_date` | Which reporting month was revised |
| `data_type` | Preliminary or Updated |
| `field` | Which specific number changed |
| `old_value` | What it said before |
| `new_value` | What it says now |

---

## How to use this data

**For researchers:** Download any dated JSON from `data/vintages/medicaid_enrollment/` to get the exact dataset as it appeared on that date. Use `revision_log_medicaid.csv` to identify which state-month combinations have been revised and by how much. Cite as:

> Gupta, A. (2025). Medicaid Enrollment Vintage Tracker [Dataset]. GitHub. https://github.com/Abhisek077/medicaid-enrollment-tracker

**For journalists:** The revision log is your starting point. Filter by state and look for large changes to recently-published months — those are the silent corrections worth investigating.

**For everyone else:** The [live dashboard](https://abhisek077.github.io/medicaid-enrollment-tracker) shows current enrollment by state and any revisions caught so far, updated daily.

---

## Important note on what these numbers mean

> When this archive records a value for State X, Report Month Y on Date Z, it means: **that was the value returned by the CMS API on Date Z, before any subsequent revision.** It is not a CMS-certified "final" figure.

This is the standard vintage-archive definition, consistent with how the [Philadelphia Fed's ALFRED](https://alfred.stlouisfed.org/) system handles national economic data. We are preserving the data as published, not certifying its accuracy.

---

## How it works technically

- A Python script runs automatically every day via GitHub Actions (free, no server needed)
- It downloads the full CMS dataset from data.medicaid.gov's public API
- It compares each record against the previous day's snapshot using unique state + month + data_type keys
- Any field-level differences are appended to the revision log
- The full snapshot is saved as a dated JSON file
- The dashboard is rebuilt and published automatically

No API keys required. No cost. Runs indefinitely.

---

## Relationship to the broader project

This tracker is part of a larger effort to document silent revisions across US federal government statistics:

🔗 [Government Statistics Vintage Tracker](https://abhisek077.github.io/govt-stats-tracker) — tracks BLS unemployment, BEA GDP, CDC mortality, EPA air quality, HUD housing data, and more.

---

## Questions, issues, or found a revision we missed?

Open an issue on this repo or contact via GitHub.

*Not affiliated with CMS, HHS, or any federal agency. All data is sourced from public government APIs.*
