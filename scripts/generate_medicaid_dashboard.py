"""
generate_medicaid_dashboard.py
Reads Medicaid vintage snapshots and revision log, builds docs/medicaid.html
Run after tracker_medicaid.py in the same GitHub Actions workflow.
"""

import os
import json
import csv
import gzip
from datetime import date
from pathlib import Path

SERIES_DIR   = "data/vintages/medicaid_enrollment"
REVISION_LOG = "data/revision_log_medicaid.csv"
OUTPUT_HTML  = "docs/medicaid.html"

# ── Data loading ──────────────────────────────────────────────────────────────

def load_latest_vintage():
    if not os.path.isdir(SERIES_DIR):
        return [], None
    files = sorted(os.listdir(SERIES_DIR), reverse=True)
    vintages = [f for f in files if f.endswith(".json.gz") or f.endswith(".json")]
    if not vintages:
        return [], None
    latest = vintages[0]
    date_str = latest.replace(".json.gz", "").replace(".json", "")
    path = os.path.join(SERIES_DIR, latest)
    if latest.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            records = json.load(f)
    else:
        with open(path) as f:
            records = json.load(f)
    return records, date_str

def load_revision_log():
    if not os.path.exists(REVISION_LOG):
        return []
    with open(REVISION_LOG, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows

def count_vintage_days():
    if not os.path.isdir(SERIES_DIR):
        return 0
    return len([f for f in os.listdir(SERIES_DIR) if f.endswith(".json.gz") or f.endswith(".json")])

# ── Stats helpers ─────────────────────────────────────────────────────────────

def get_summary_stats(records, revisions):
    total_enroll = 0
    states_seen  = set()

    # Get most recent "Updated" data per state
    state_latest = {}
    for r in records:
        state = r.get("state_name", "")
        dtype = r.get("preliminary_or_updated", "")
        rdate = r.get("reporting_period", "")
        enroll = r.get("total_medicaid_and_chip_enrollment", "")
        if state and dtype == "U" and enroll:
            if state not in state_latest or rdate > state_latest[state]["report_date"]:
                state_latest[state] = {"report_date": rdate, "enrollment": enroll}

    for state, data in state_latest.items():
        try:
            total_enroll += int(str(data["enrollment"]).replace(",", ""))
            states_seen.add(state)
        except (ValueError, TypeError):
            pass

    real_revisions = [r for r in revisions if r.get("field") not in ("ROW_ADDED", "ROW_DELETED")]
    new_months     = [r for r in revisions if r.get("field") == "ROW_ADDED"]

    return {
        "total_enrollment":  f"{total_enroll:,}" if total_enroll else "—",
        "states_tracked":    len(states_seen),
        "real_revisions":    len(real_revisions),
        "new_months_added":  len(new_months),
        "days_running":      count_vintage_days(),
        "total_polls":       count_vintage_days(),
    }

def format_period(p):
    """Convert '202309' to 'Sep 2023' for display."""
    if not p or len(p) != 6:
        return p or "—"
    try:
        year = p[:4]
        month_num = int(p[4:6])
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return f"{months[month_num - 1]} {year}"
    except (ValueError, IndexError):
        return p

def format_number(val):
    """Format a number string with commas, or return '—'."""
    if not val or val == "None":
        return "—"
    try:
        return f"{int(str(val).replace(',', '')):,}"
    except (ValueError, TypeError):
        return "—"

def build_state_table(records):
    """Build per-state latest enrollment summary."""
    state_data = {}
    for r in records:
        state = r.get("state_name", "")
        dtype = r.get("preliminary_or_updated", "")
        rdate = r.get("reporting_period", "")
        if not state or dtype != "U":
            continue
        enroll_raw = r.get("total_medicaid_and_chip_enrollment", "")
        try:
            enroll = int(str(enroll_raw).replace(",", ""))
        except (ValueError, TypeError):
            enroll = 0
        if state not in state_data or rdate > state_data[state]["report_date"]:
            state_data[state] = {
                "report_date": rdate,
                "enrollment":  enroll,
                "medicaid":    r.get("total_medicaid_enrollment", ""),
                "chip":        r.get("total_chip_enrollment", ""),
            }

    rows_html = ""
    for state in sorted(state_data.keys()):
        d = state_data[state]
        rows_html += f"""
        <tr>
          <td>{state}</td>
          <td>{format_period(d['report_date'])}</td>
          <td class="num">{format_number(d['enrollment'])}</td>
          <td class="num">{format_number(d['medicaid'])}</td>
          <td class="num">{format_number(d['chip'])}</td>
        </tr>"""
    return rows_html

def build_revision_table(revisions):
    """Build revision log table, most recent first, real revisions only."""
    real = [r for r in revisions if r.get("field") not in ("ROW_ADDED", "ROW_DELETED")]
    real = sorted(real, key=lambda x: x.get("detected_date",""), reverse=True)

    if not real:
        return '<tr><td colspan="6" class="empty">No field-level revisions detected yet — accumulating baseline vintages</td></tr>'

    rows_html = ""
    for r in real[:100]:
        old = format_number(r.get("old_value", ""))
        new = format_number(r.get("new_value", ""))
        rows_html += f"""
        <tr>
          <td>{r.get('detected_date','')}</td>
          <td>{r.get('state_name','')}</td>
          <td>{format_period(r.get('report_date',''))}</td>
          <td>{'Updated' if r.get('data_type','') == 'U' else 'Preliminary' if r.get('data_type','') == 'P' else r.get('data_type','')}</td>
          <td>{r.get('field','').replace('_', ' ').title()}</td>
          <td class="diff"><span class="old">{old}</span> &rarr; <span class="new">{new}</span></td>
        </tr>"""
    return rows_html

# ── HTML builder ──────────────────────────────────────────────────────────────

def build_html(records, revisions, last_poll):
    stats      = get_summary_stats(records, revisions)
    state_rows = build_state_table(records)
    rev_rows   = build_revision_table(revisions)
    today      = date.today().isoformat()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Medicaid Enrollment Vintage Tracker</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0d1117;
      color: #c9d1d9;
      min-height: 100vh;
      padding: 0 0 60px;
    }}

    .header {{
      background: #161b22;
      border-bottom: 1px solid #30363d;
      padding: 24px 32px 20px;
    }}
    .header-top {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }}
    .badge {{
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 12px;
      font-weight: 500;
    }}
    .badge-blue  {{ background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb66; }}
    .badge-green {{ background: #23863633; color: #3fb950; border: 1px solid #23863666; }}
    .back-link {{
      font-size: 12px;
      color: #58a6ff;
      text-decoration: none;
      margin-left: auto;
    }}
    .back-link:hover {{ text-decoration: underline; }}
    h1 {{
      font-size: 22px;
      font-weight: 600;
      color: #e6edf3;
      margin-bottom: 6px;
    }}
    .subtitle {{
      font-size: 13px;
      color: #8b949e;
      line-height: 1.5;
      max-width: 700px;
    }}

    .main {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px 0; }}

    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 32px;
    }}
    .stat-card {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 18px 20px;
      text-align: center;
    }}
    .stat-value {{
      font-size: 28px;
      font-weight: 700;
      color: #e6edf3;
      line-height: 1;
      margin-bottom: 6px;
    }}
    .stat-label {{
      font-size: 11px;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .stat-card.highlight .stat-value {{ color: #3fb950; }}
    .stat-card.warn      .stat-value {{ color: #f78166; }}

    .section {{ margin-bottom: 36px; }}
    .section-title {{
      font-size: 14px;
      font-weight: 600;
      color: #e6edf3;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid #30363d;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .section-note {{
      font-size: 11px;
      color: #8b949e;
      font-weight: 400;
    }}

    .table-wrap {{ overflow-x: auto; border-radius: 8px; border: 1px solid #30363d; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    thead th {{
      background: #161b22;
      color: #8b949e;
      font-weight: 600;
      text-align: left;
      padding: 10px 14px;
      border-bottom: 1px solid #30363d;
      white-space: nowrap;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.04em;
    }}
    tbody tr {{ border-bottom: 1px solid #21262d; transition: background 0.1s; }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody tr:hover {{ background: #161b22; }}
    tbody td {{
      padding: 9px 14px;
      color: #c9d1d9;
      vertical-align: middle;
    }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .empty {{ color: #8b949e; text-align: center; padding: 28px; }}
    .old {{ color: #f78166; }}
    .new {{ color: #3fb950; }}
    .diff {{ font-family: monospace; font-size: 11px; white-space: nowrap; }}

    .footer {{
      max-width: 1100px;
      margin: 40px auto 0;
      padding: 20px 24px;
      border-top: 1px solid #30363d;
      font-size: 11px;
      color: #8b949e;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: space-between;
    }}
    .footer a {{ color: #58a6ff; text-decoration: none; }}
    .footer a:hover {{ text-decoration: underline; }}

    .info-box {{
      background: #161b22;
      border: 1px solid #30363d;
      border-left: 3px solid #58a6ff;
      border-radius: 8px;
      padding: 16px 20px;
      font-size: 12px;
      color: #8b949e;
      line-height: 1.7;
      margin-bottom: 32px;
    }}
    .info-box strong {{ color: #c9d1d9; }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <span class="badge badge-blue">Public Dataset</span>
    <span class="badge badge-green">Updated Daily</span>
    <span class="badge badge-blue">Automated</span>
    <a class="back-link" href="https://abhisek077.github.io/govt-stats-tracker" target="_blank">&larr; Main tracker</a>
  </div>
  <h1>Medicaid &amp; CHIP Enrollment Vintage Tracker</h1>
  <p class="subtitle">
    Daily snapshots of CMS Medicaid &amp; CHIP monthly enrollment data &mdash; capturing silent retroactive
    revisions that states submit without public announcement. When a state&rsquo;s enrollment figure
    changes after publication, the before/after is recorded here permanently.
  </p>
</div>

<div class="main">

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value">{stats['days_running']}</div>
      <div class="stat-label">Days running</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['total_polls']}</div>
      <div class="stat-label">Total snapshots</div>
    </div>
    <div class="stat-card {'warn' if stats['real_revisions'] > 0 else ''}">
      <div class="stat-value">{stats['real_revisions']}</div>
      <div class="stat-label">Revisions caught</div>
    </div>
    <div class="stat-card highlight">
      <div class="stat-value">{stats['states_tracked']}</div>
      <div class="stat-label">States tracked</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['total_enrollment']}</div>
      <div class="stat-label">Latest total enrollees</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['new_months_added']}</div>
      <div class="stat-label">New months observed</div>
    </div>
  </div>

  <div class="info-box">
    <strong>Why this matters:</strong> CMS publishes Preliminary enrollment figures ~1 week after
    each reporting period, then Updated figures ~1 month later. States also revise earlier months
    retroactively when they detect errors. These revisions are silent &mdash; CMS overwrites the live
    dataset without a changelog. This tracker is that changelog.<br><br>
    <strong>How to read this data:</strong> The state table below shows the most recent Updated
    enrollment for each state. The revision log shows every time a previously published number
    was changed &mdash; with the old and new values. Each daily snapshot is preserved as a compressed
    file (~15 KB) so anyone can independently verify any revision by comparing two dated files.
    <br><br>
    <strong>Revision semantics:</strong> A value recorded for state X on date Y means the figure
    returned by the CMS API on that date, before any subsequent revision &mdash; consistent with the
    Philadelphia Fed&rsquo;s ALFRED vintage methodology.
  </div>

  <div class="section">
    <div class="section-title">
      Latest enrollment by state
      <span class="section-note">Most recent Updated figures &middot; source: data.medicaid.gov</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>State / Territory</th>
            <th>Report month</th>
            <th class="num">Total Medicaid + CHIP</th>
            <th class="num">Medicaid only</th>
            <th class="num">CHIP only</th>
          </tr>
        </thead>
        <tbody>
          {state_rows if state_rows else '<tr><td colspan="5" class="empty">No data yet &mdash; waiting for first snapshot with Updated figures</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-title">
      Revision log
      <span class="section-note">Field-level changes only &middot; most recent first &middot; capped at 100 rows</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Detected</th>
            <th>State</th>
            <th>Report month</th>
            <th>Type</th>
            <th>Field revised</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          {rev_rows}
        </tbody>
      </table>
    </div>
  </div>

</div>

<div class="footer">
  <span>
    Data source: <a href="https://data.medicaid.gov/dataset/6165f45b-ca93-5bb5-9d06-db29c692a360" target="_blank">data.medicaid.gov</a>
    &middot; Last poll: {last_poll or today}
    &middot; Built: {today}
    &middot; Storage: ~15 KB/day (gzip compressed)
  </span>
  <span>
    <a href="https://github.com/Abhisek077/medicaid-enrollment-tracker" target="_blank">github.com/Abhisek077/medicaid-enrollment-tracker</a>
  </span>
</div>

</body>
</html>"""
    return html

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print("Medicaid Dashboard Generator")
    print(f"{'='*60}")

    print("\n[1] Loading latest vintage...")
    records, last_poll = load_latest_vintage()
    print(f"  Records: {len(records)} | Last poll: {last_poll}")

    print("\n[2] Loading revision log...")
    revisions = load_revision_log()
    print(f"  Revision events: {len(revisions)}")

    print("\n[3] Building HTML...")
    html = build_html(records, revisions, last_poll)

    print("\n[4] Writing docs/medicaid.html...")
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_HTML, "w") as f:
        f.write(html)
    print(f"  Written: {OUTPUT_HTML} ({len(html):,} bytes)")

    print(f"\n{'='*60}")
    print("Dashboard ready.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
