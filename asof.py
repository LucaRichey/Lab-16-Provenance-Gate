"""
asof.py — Lab 16: Provenance Gate and Point-in-Time Admission Filter
Standard library only.

Applies a 4-rule provenance gate to financial data records:
  Rule 1: Quarantine rows with no ticker.
  Rule 2: Remove exact duplicate rows.
  Rule 3: Remove rows published after the decision date.
  Rule 4: For any ticker and month with multiple publications, keep the latest one
          published on or before the decision date (a revision).

Computes:
  - Row funnel (removed rows and remaining as-of panel)
  - As-of signals (fund return from previous month to latest knowable month)
  - Naive signals (same calculation ignoring publication date cutoff)
  - Sanity check (yield = 100 / price - 1 and economic validity)
"""

from datetime import datetime
from collections import defaultdict

# =============================================================================
# EDITABLE INPUTS
# =============================================================================
DECISION_DATE = "2026-03-31"

RAW_TABLE = [
    {"row": 1,  "ticker": "AAA",  "month": "2026-01", "published_on": "2026-02-10", "price": 101.0},
    {"row": 2,  "ticker": "AAA",  "month": "2026-02", "published_on": "2026-03-10", "price": 104.0},
    {"row": 3,  "ticker": "AAA",  "month": "2026-03", "published_on": "2026-04-10", "price": 109.0},
    {"row": 4,  "ticker": "AAA",  "month": "2026-02", "published_on": "2026-03-25", "price": 103.0},
    {"row": 5,  "ticker": "BBB",  "month": "2026-01", "published_on": "2026-02-10", "price": 98.0},
    {"row": 6,  "ticker": "BBB",  "month": "2026-02", "published_on": "2026-03-10", "price": 97.0},
    {"row": 7,  "ticker": "BBB",  "month": "2026-02", "published_on": "2026-03-10", "price": 97.0},
    {"row": 8,  "ticker": "BBB",  "month": "2026-03", "published_on": "2026-04-10", "price": 92.0},
    {"row": 9,  "ticker": "CCC",  "month": "2026-01", "published_on": "2026-02-10", "price": 110.0},
    {"row": 10, "ticker": "CCC",  "month": "2026-02", "published_on": "2026-04-05", "price": 112.0},
    {"row": 11, "ticker": None,   "month": "2026-02", "published_on": "2026-03-10", "price": 99.0},
    {"row": 12, "ticker": "CCC",  "month": "2026-02", "published_on": "2026-03-10", "price": 111.0},
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def month_name(month_str: str) -> str:
    """Converts '2026-02' -> 'February'."""
    return datetime.strptime(month_str, "%Y-%m").strftime("%B")


def format_return(val: float) -> str:
    """Formats return with explicit sign and two decimal places (e.g., +1.98%, -1.02%)."""
    # Use ASCII plus/minus, with + for positive values
    if val > 0:
        return f"+{val:.2f}%"
    elif val < 0:
        return f"-{abs(val):.2f}%"
    else:
        return f"0.00%"


# =============================================================================
# PROVENANCE GATE FILTER
# =============================================================================
def apply_provenance_gate(rows, decision_date):
    """
    Applies the four provenance gate rules in sequential order.
    Returns:
      funnel_log: list of (step_name, list_of_removed_row_numbers)
      asof_panel: list of admitted row dicts
    """
    funnel_log = []

    # Rule 1: Quarantine a row with no ticker
    r1_kept = []
    r1_removed = []
    for r in rows:
        ticker = r.get("ticker")
        if ticker is None or str(ticker).strip() == "":
            r1_removed.append(r["row"])
        else:
            r1_kept.append(r)
    funnel_log.append(("Quarantined: no ticker", r1_removed))

    # Rule 2: Remove an exact duplicate
    r2_kept = []
    r2_removed = []
    seen_tuples = set()
    for r in r1_kept:
        key = (r["ticker"], r["month"], r["published_on"], r["price"])
        if key in seen_tuples:
            r2_removed.append(r["row"])
        else:
            seen_tuples.add(key)
            r2_kept.append(r)
    funnel_log.append(("Exact duplicate", r2_removed))

    # Rule 3: Remove a row published after the decision date
    r3_kept = []
    r3_removed = []
    for r in r2_kept:
        if r["published_on"] > decision_date:
            r3_removed.append(r["row"])
        else:
            r3_kept.append(r)
    funnel_log.append((f"Published after {decision_date}", r3_removed))

    # Rule 4: Where one ticker and month has two publications, keep the latest one published by the decision date
    # Group remaining rows by (ticker, month)
    grouped = defaultdict(list)
    for r in r3_kept:
        grouped[(r["ticker"], r["month"])].append(r)

    r4_kept = []
    r4_removed = []
    for (ticker, month), vintage_list in grouped.items():
        if len(vintage_list) == 1:
            r4_kept.append(vintage_list[0])
        else:
            # Sort by publication date ascending; if tied, row number ascending
            sorted_vintages = sorted(vintage_list, key=lambda x: (x["published_on"], x["row"]))
            latest_vintage = sorted_vintages[-1]
            older_vintages = sorted_vintages[:-1]
            for old in older_vintages:
                r4_removed.append(old["row"])
            r4_kept.append(latest_vintage)

    # Sort r4_kept by original row number for clean panel presentation
    r4_kept = sorted(r4_kept, key=lambda x: x["row"])
    r4_removed = sorted(r4_removed)
    funnel_log.append(("Older vintage replaced by a revision", r4_removed))

    return funnel_log, r4_kept


# =============================================================================
# SIGNAL COMPUTATION
# =============================================================================
def compute_signals(panel, label_revisions=False, baseline_panel=None):
    """
    Computes percent change from previous month to latest month for each ticker.
    Returns dict: ticker -> (return_str, month_label)
    """
    # Group by ticker
    by_ticker = defaultdict(list)
    for r in panel:
        by_ticker[r["ticker"]].append(r)

    signals = {}
    for ticker, obs_list in sorted(by_ticker.items()):
        # Sort observations chronologically by month
        obs_sorted = sorted(obs_list, key=lambda x: x["month"])
        if len(obs_sorted) < 2:
            signals[ticker] = ("N/A", "Insufficient data")
            continue

        prev_obs = obs_sorted[-2]
        latest_obs = obs_sorted[-1]

        pct_change = ((latest_obs["price"] - prev_obs["price"]) / prev_obs["price"]) * 100.0
        pct_str = format_return(pct_change)
        m_name = month_name(latest_obs["month"])

        # Check if revision label is warranted (for naive signals where the month is identical but revised)
        if label_revisions and baseline_panel is not None:
            # Find the corresponding baseline latest observation for this ticker
            baseline_obs = [r for r in baseline_panel if r["ticker"] == ticker]
            if baseline_obs:
                base_latest = sorted(baseline_obs, key=lambda x: x["month"])[-1]
                if base_latest["month"] == latest_obs["month"] and base_latest["row"] != latest_obs["row"]:
                    m_name = f"{m_name}, revised"

        signals[ticker] = (pct_str, m_name)

    return signals


def compute_naive_panel_and_signals(rows, baseline_panel=None):
    """
    Computes naive panel:
      - Ignores publication date cutoff (skips Rule 3)
      - Retains Rule 1 (quarantine no ticker) and Rule 2 (deduplication)
      - Retains Rule 4 (latest publication for each ticker and month)
    """
    # Rule 1: No ticker
    r1_kept = [r for r in rows if r.get("ticker") is not None and str(r.get("ticker")).strip() != ""]
    # Rule 2: Deduplication
    r2_kept = []
    seen = set()
    for r in r1_kept:
        key = (r["ticker"], r["month"], r["published_on"], r["price"])
        if key not in seen:
            seen.add(key)
            r2_kept.append(r)

    # Rule 4: Latest publication across all vintages for (ticker, month)
    grouped = defaultdict(list)
    for r in r2_kept:
        grouped[(r["ticker"], r["month"])].append(r)

    naive_panel = []
    for (ticker, month), vintage_list in grouped.items():
        sorted_vintages = sorted(vintage_list, key=lambda x: (x["published_on"], x["row"]))
        naive_panel.append(sorted_vintages[-1])

    naive_panel = sorted(naive_panel, key=lambda x: x["row"])
    naive_signals = compute_signals(naive_panel, label_revisions=True, baseline_panel=baseline_panel)
    return naive_panel, naive_signals


# =============================================================================
# SANITY CHECK (FIXED INCOME YIELD & CREDIT ORDER)
# =============================================================================
def compute_sanity_check(panel):
    """
    For a one-year zero-coupon bond per 100 face value:
      Yield = 100 / price - 1
    Checks for:
      - Negative yields (price > 100)
      - Credit ordering violations (riskier credit priced above safer credit)
    """
    results = []
    for r in panel:
        price = r["price"]
        yld = (100.0 / price - 1.0) * 100.0
        breaks = []
        if price > 100.0:
            breaks.append("negative yield")
        results.append({
            "row": r["row"],
            "fund": r["ticker"],
            "month": month_name(r["month"])[:3],
            "price": price,
            "yield": yld,
            "breaks": breaks
        })

    # Check credit ordering across funds in the same month: AAA should be priced > BBB > CCC
    # and BBB yield > AAA yield, CCC yield > BBB yield
    by_month = defaultdict(dict)
    for res in results:
        by_month[res["month"]][res["fund"]] = res["price"]

    for res in results:
        m = res["month"]
        fund = res["fund"]
        price = res["price"]
        if fund == "CCC":
            bbb_price = by_month[m].get("BBB")
            aaa_price = by_month[m].get("AAA")
            violations = []
            if bbb_price and price > bbb_price:
                violations.append("BBB")
            if aaa_price and price > aaa_price:
                violations.append("AAA")
            if violations:
                res["breaks"].append(f"priced above {' and '.join(violations)}")

    return results


# =============================================================================
# MAIN RUNNER
# =============================================================================
def main():
    print("=" * 72)
    print("LAB 16: PROVENANCE GATE & POINT-IN-TIME ADMISSION FILTER")
    print(f"Decision Date: {DECISION_DATE}")
    print("=" * 72)

    # 1. Apply Provenance Gate
    funnel_log, asof_panel = apply_provenance_gate(RAW_TABLE, DECISION_DATE)

    print("\n--- The Row Funnel ---")
    print(f"{'Funnel step':<38} {'Rows removed'}")
    print("-" * 55)
    for step_name, removed_rows in funnel_log:
        removed_str = ", ".join(map(str, removed_rows)) if removed_rows else "None"
        print(f"{step_name:<38} {removed_str}")

    asof_row_numbers = [r["row"] for r in asof_panel]
    print(f"{'As-of panel':<38} {', '.join(map(str, asof_row_numbers))}")

    # 2. Display As-Of Panel
    print("\n--- As-Of Panel (Admitted Rows) ---")
    print(f"{'Row':<6} {'Ticker':<8} {'Month':<10} {'Published On':<14} {'Price':<8}")
    print("-" * 48)
    for r in asof_panel:
        print(f"{r['row']:<6} {r['ticker']:<8} {r['month']:<10} {r['published_on']:<14} {r['price']:<8.1f}")

    # 3. Compute Signals
    asof_signals = compute_signals(asof_panel)
    naive_panel, naive_signals = compute_naive_panel_and_signals(RAW_TABLE, baseline_panel=asof_panel)

    print("\n--- The Signals ---")
    print(f"{'Ticker':<8} {'As-of signal':<26} {'Naive signal'}")
    print("-" * 60)
    for ticker in sorted(asof_signals.keys()):
        asof_ret, asof_m = asof_signals[ticker]
        asof_disp = f"{asof_ret} ({asof_m})"

        naive_ret, naive_m = naive_signals[ticker]
        naive_disp = f"{naive_ret} ({naive_m})"

        print(f"{ticker:<8} {asof_disp:<26} {naive_disp}")

    # 4. Sanity Check (Economics / Fixed Income)
    print("\n--- The Sanity Check (Fixed Income Yield & Credit Order) ---")
    print(f"{'Row':<6} {'Fund':<6} {'Month':<8} {'Price':<8} {'Yield':<10} {'Breaks'}")
    print("-" * 72)
    sanity_results = compute_sanity_check(asof_panel)
    for s in sanity_results:
        breaks_str = "; ".join(s["breaks"]) if s["breaks"] else "nothing"
        print(f"{s['row']:<6} {s['fund']:<6} {s['month']:<8} {s['price']:<8.1f} {format_return(s['yield']):<10} {breaks_str}")

    print("\n" + "=" * 72)
    print("Conclusion: On time is not the same as true:")
    print("A provenance gate needs a sanity gate behind it.")
    print("=" * 72)


if __name__ == "__main__":
    main()
