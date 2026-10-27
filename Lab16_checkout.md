# Lab 16 — Provenance Gate & Point-in-Time Admission Filter
## As-Of Historical Data Filtering, Revisions Handling, and Fixed Income Sanity Gating

**Student:** Luca Richey  
**Course:** FIN 43900 (AI Finance Applications, Purdue University)  
**Date:** October 27, 2026  
**Category:** Tuesday Completion Checkout (25/25)  
**Workspace Directory:** `/Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey`  

---

## Executive Evidence Summary & Deliverables

All deliverables, Python filtering engines, test scripts, and verified console outputs are preserved directly in this repository:

| Deliverable / Artifact | Workspace Link | Description & Key Result | Status |
|---|---|---|:---:|
| **As-Of Provenance Engine** | [`asof.py`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/asof.py)<br>[`Lab16_Provenance/asof.py`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/Lab16_Provenance/asof.py) | Standalone, standard-library Python engine applying the 4 sequential gating rules, calculating As-Of signals, Naive signals, and yield sanity checks. | **Verified (Matches Known Answer)** |
| **Console Execution Output** | [`Lab16_Provenance/asof_output.txt`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/Lab16_Provenance/asof_output.txt) | Captured console stdout confirming exact matches across row funnel, as-of panel, signals, and fixed income sanity checks. | **Exact Match** |
| **Lab 16 Checkout Document** | [`Lab16_checkout.md`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/Lab16_checkout.md)<br>[`Lab16_Provenance/Lab16_checkout.md`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/Lab16_Provenance/Lab16_checkout.md) | Complete documentation of D, R, I, V, code explanation, swap-and-break test, and learning reflections. | **Complete** |

---

## D — The Core Question

> **"On the day you would have traded, what did this data actually say — and how much of what you see now came later?"**

### Direct Executive Finding:
1. **What was knowable on the decision date (31 March 2026):**
   - The market only knew economic and fund performance through **February 2026**.
   - For **AAA**, the latest knowable February price was **103.0** (Row 4, revised on March 25), producing an As-Of return of **+1.98%**. The earlier preliminary release of **104.0** (Row 2, March 10) was already superseded.
   - For **BBB**, February price was **97.0** (Row 6), producing an As-Of return of **-1.02%**.
   - For **CCC**, February price was **111.0** (Row 12), producing an As-Of return of **+0.91%**.
2. **How much came later (the look-ahead gap):**
   - **Row 3 (AAA March at 109.0)**: Published on April 10 $\rightarrow$ created an illusory naive signal of **+5.83%** (+385 bps look-ahead bias).
   - **Row 8 (BBB March at 92.0)**: Published on April 10 $\rightarrow$ created an illusory naive signal of **-5.15%** (-413 bps look-ahead bias).
   - **Row 10 (CCC February revised at 112.0)**: Published on April 5 $\rightarrow$ revised February return upward to **+1.82%** (+91 bps revision gap) that could not have been known on March 31.
   - Any backtest relying on modern flattened data without point-in-time filtering would trade on data published **5 to 10 days in the future**, generating completely fictional performance.

---

## R — The Training Table & Four Gating Rules

### 1. Raw Training Table (Decision Date: 2026-03-31)
Data represents fictional funds holding one-year zero-coupon bonds per 100 face value across three rating categories (AAA, BBB, CCC):

| Row | Ticker | Month Measured | Published On | Price | Observation Notes |
|:---:|:---:|:---:|:---:|:---:|---|
| **1** | AAA | 2026-01 | 2026-02-10 | 101.0 | Initial release for Jan |
| **2** | AAA | 2026-02 | 2026-03-10 | 104.0 | Initial release for Feb (superseded by Row 4) |
| **3** | AAA | 2026-03 | 2026-04-10 | 109.0 | March data published *after* decision date |
| **4** | AAA | 2026-02 | 2026-03-25 | 103.0 | Revision of Feb published *before* decision date |
| **5** | BBB | 2026-01 | 2026-02-10 | 98.0 | Initial release for Jan |
| **6** | BBB | 2026-02 | 2026-03-10 | 97.0 | Initial release for Feb |
| **7** | BBB | 2026-02 | 2026-03-10 | 97.0 | **Exact duplicate** of Row 6 |
| **8** | BBB | 2026-03 | 2026-04-10 | 92.0 | March data published *after* decision date |
| **9** | CCC | 2026-01 | 2026-02-10 | 110.0 | Initial release for Jan |
| **10** | CCC | 2026-02 | 2026-04-05 | 112.0 | Revision of Feb published *after* decision date |
| **11** | *(None)* | 2026-02 | 2026-03-10 | 99.0 | **Missing ticker** |
| **12** | CCC | 2026-02 | 2026-03-10 | 111.0 | Initial release for Feb |

### 2. The Four Rules in Sequential Order
Between the raw data provider (such as the ALFRED API) and our quantitative strategy sits the **Provenance Gate**:
1. **Rule 1 (Quarantine No Ticker):** Quarantine any record missing a valid ticker symbol.
2. **Rule 2 (Remove Exact Duplicates):** Remove exact duplicate rows with identical `(ticker, month, published_on, price)`.
3. **Rule 3 (Remove Late Publications):** Remove any row published after the decision date (`published_on > DECISION_DATE`).
4. **Rule 4 (Keep Latest Revision):** For any `(ticker, month)` with multiple publications admitted by the decision date, retain the latest published vintage and remove older superseded vintages.

---

## I — Implementation (`asof.py`)

The engine [`asof.py`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/asof.py) is implemented using Python standard library only (`datetime`, `collections.defaultdict`).

### Command to Run:
```bash
python3 asof.py
```

### Explaining the Code: Rule 4 Line-by-Line
Below is the core Rule 4 block from [`asof.py`](file:///Users/lucarichey/Documents/Courses/AIFinance2026/LucaRichey/asof.py):

```python
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
```

#### Line-by-Line Partner Explanation:
1. `grouped = defaultdict(list)`: Initializes a dictionary mapping each composite key `(ticker, month)` to an empty list of rows.
2. `for r in r3_kept: grouped[(r["ticker"], r["month"])].append(r)`: Iterates through all rows that survived Rules 1–3 and buckets them by asset and measurement period.
3. `r4_kept = []` and `r4_removed = []`: Allocates lists to hold the admitted final records and the discarded older vintages.
4. `for (ticker, month), vintage_list in grouped.items():`: Iterates through every unique asset-month pair.
5. `if len(vintage_list) == 1: r4_kept.append(vintage_list[0])`: If only one publication exists for that month, it has no competing vintages and is immediately admitted.
6. `else:`: If two or more publications exist for the same month (e.g., preliminary vs. revised).
7. `sorted_vintages = sorted(vintage_list, key=lambda x: (x["published_on"], x["row"]))`: Sorts the vintages in chronological order of their publication date (`published_on`).
8. `latest_vintage = sorted_vintages[-1]`: Extracts the very last record in the sorted sequence, which represents the most up-to-date information knowable by the decision date.
9. `older_vintages = sorted_vintages[:-1]`: Slices out all preceding records that have now been superseded.
10. `for old in older_vintages: r4_removed.append(old["row"])`: Logs each superseded row's number to the funnel removal audit trail.
11. `r4_kept.append(latest_vintage)`: Admits only the latest vintage into the final as-of panel.

---

## V — Validation Against Known Answer

### 1. The Row Funnel Audit Trail
| Funnel Step | Target / Description | Rows Removed | Count | Verification |
|---|---|:---:|:---:|:---:|
| **Rule 1** | Quarantined: no ticker | **11** | 1 | **Exact Match** |
| **Rule 2** | Exact duplicate | **7** | 1 | **Exact Match** |
| **Rule 3** | Published after 31 March 2026 | **3, 8, 10** | 3 | **Exact Match** |
| **Rule 4** | Older vintage replaced by a revision | **2** | 1 | **Exact Match** |
| **Admitted** | **As-of panel remaining** | **1, 4, 5, 6, 9, 12** | **6** | **Exact Match** |

> [!IMPORTANT]
> **The Classic Error:** Keeping Row 2 (AAA Feb initial release at 104.0) instead of Row 4 (AAA Feb revision at 103.0) would cause AAA's return to calculate as $\frac{104.0 - 101.0}{101.0} = +2.97\%$.  
> By correctly retaining Row 4, the true As-Of signal is $\frac{103.0 - 101.0}{101.0} = \mathbf{+1.98\%}$.

### 2. Admitted As-Of Panel
| Row | Ticker | Month Measured | Published On | Admitted Price | Role in Signal |
|:---:|:---:|:---:|:---:|:---:|---|
| **1** | AAA | 2026-01 | 2026-02-10 | 101.0 | Base price (Jan) |
| **4** | AAA | 2026-02 | 2026-03-25 | 103.0 | Latest price (Feb, revised vintage) |
| **5** | BBB | 2026-01 | 2026-02-10 | 98.0 | Base price (Jan) |
| **6** | BBB | 2026-02 | 2026-03-10 | 97.0 | Latest price (Feb) |
| **9** | CCC | 2026-01 | 2026-02-10 | 110.0 | Base price (Jan) |
| **12** | CCC | 2026-02 | 2026-03-10 | 111.0 | Latest price (Feb) |

### 3. The Signals Comparison
Returns calculated as percent change from previous month to latest knowable month:

$$\text{Signal} = \frac{\text{Price}_{t} - \text{Price}_{t-1}}{\text{Price}_{t-1}}$$

| Ticker | As-Of Signal (Decision: 2026-03-31) | Naive Signal (All Vintages / No Cutoff) | Look-Ahead Discrepancy & Reason |
|:---:|:---:|:---:|---|
| **AAA** | **+1.98% (February)** | **+5.83% (March)** | Naive uses Row 3 (109.0), published April 10. |
| **BBB** | **-1.02% (February)** | **-5.15% (March)** | Naive uses Row 8 (92.0), published April 10. |
| **CCC** | **+0.91% (February)** | **+1.82% (February, revised)** | Naive uses Row 10 (112.0), published April 5. |

### 4. Sanity Check — Fixed Income Yields & Broken Finance Principles
For a one-year zero-coupon bond paying face value of 100 at maturity:

$$\text{Yield} = \frac{100}{\text{Price}} - 1$$

Two non-negotiable financial laws:
1. **Price $\le 100.0$:** Any price above 100 implies a negative nominal yield (paying more now than the 100 returned at maturity).
2. **Credit Spread Monotonicity:** Riskier credit must yield more than safer credit to compensate for default risk $\rightarrow \text{Price}(\text{AAA}) \ge \text{Price}(\text{BBB}) \ge \text{Price}(\text{CCC})$.

| Row | Fund | Month | Price | Yield Calculation | Realized Yield | Breaks What Rule? |
|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **1** | AAA | Jan | 101.0 | $100 / 101.0 - 1$ | **-0.99%** | Negative yield (price > 100) |
| **4** | AAA | Feb | 103.0 | $100 / 103.0 - 1$ | **-2.91%** | Negative yield (price > 100) |
| **5** | BBB | Jan | 98.0 | $100 / 98.0 - 1$ | **+2.04%** | **Nothing** (economically sound) |
| **6** | BBB | Feb | 97.0 | $100 / 97.0 - 1$ | **+3.09%** | **Nothing** (economically sound) |
| **9** | CCC | Jan | 110.0 | $100 / 110.0 - 1$ | **-9.09%** | Negative yield; CCC priced above BBB (98.0) & AAA (101.0) |
| **12** | CCC | Feb | 111.0 | $100 / 111.0 - 1$ | **-9.91%** | Negative yield; CCC priced above BBB (97.0) & AAA (103.0) |

> [!CAUTION]
> **Core Takeaway:** "On time is not the same as true: a provenance gate needs a sanity gate behind it."  
> All 6 rows arrived with valid dates and proper provenance, yet 4 of the 6 break fundamental fixed income pricing principles.

---

## Swap and Break Test: Setting Decision Date to 2026-04-15

To verify that the provenance gate strictly tracks knowability, we set `DECISION_DATE = "2026-04-15"`:

1. **Rows 3, 8, and 10** were published on April 10 and April 5 ($\le \text{2026-04-15}$). Under Rule 3, **zero rows are removed for lateness**.
2. For AAA, March becomes knowable (Row 3, 109.0) $\rightarrow$ signal becomes **+5.83% (March)**.
3. For BBB, March becomes knowable (Row 8, 92.0) $\rightarrow$ signal becomes **-5.15% (March)**.
4. For CCC, the February revision (Row 10, 112.0) arrives and supersedes Row 12 under Rule 4 $\rightarrow$ signal becomes **+1.82% (February)**.

**Result:** Ticker for ticker, the As-Of signals become identical to the Naive signals. The gap between the two columns is *exactly* what had not been published yet on March 31.

---

## Point-in-Time — Learn on Your Own & Reflection

### 1. What is look-ahead bias?
**Look-ahead bias** occurs when an investment strategy or backtest incorporates information that was not yet publicly knowable or available on the historical date the trading decision would have been executed.

### 2. How does it work — Event Time vs. Publication Time vs. Revision?
- **Event Time (Month Measured / Date):** The calendar period during which economic activity took place (e.g., February 2026 GDP, unemployment, or fund returns).
- **Publication Time (`realtime_start`):** The exact calendar day when government statistical agencies or data providers officially publish that figure to the public (typically weeks or months after the event month ends).
- **Revision (`realtime_start` update):** A subsequent update to an earlier event month, published at a later date when more complete survey data is gathered (e.g., CCC February being revised on April 5).
- **The Pitfall:** Standard financial databases often store historical time series indexed only by *Event Time*, retroactively overwriting preliminary numbers with their final revised values. A backtest running on this data unknowingly acts on future revisions.

### 3. The AAA Example: Why +5.83% is Illusory
On March 31, 2026, an investor looking at AAA only had February data (+1.98%). The +5.83% signal reflects March returns, which were not computed or published until **April 10, 2026**. Trading on +5.83% on March 31 implies time travel—buying an asset based on gains that have not yet occurred and data that has not yet been released.

### 4. Which rule removed the row that mattered most?
- For eliminating pure look-ahead bias: **Rule 3** removed Rows 3 and 8 (March performance published in April), preventing a massive distortion of 385 to 413 bps in portfolio signals.
- For revision accuracy: **Rule 4** removed Row 2, ensuring the strategy traded on the revised 103.0 price rather than the stale 104.0 price, shifting the return from +2.97% to +1.98%.

### 5. What a backtest built on the naive column would claim:
A naive backtest would falsely claim that the strategy captured a huge rally in AAA (+5.83%) and avoided a sharp drop in BBB (-5.15%) as of March 31. In live production trading, the fund would suffer severe underperformance because those signals were physically impossible to observe on March 31.

### 6. The Fifth Rule: The Sanity Gate
A fifth rule placed immediately after the provenance gate would test **economic and mathematical sanity**:
```python
# Rule 5: Sanity Gate (Economic Feasibility & Monotonicity)
# Quarantine any zero-coupon bond fund priced > 100 (negative yield)
# or where CCC price > BBB price > AAA price.
```
This rule would instantly quarantine **Rows 1, 4, 9, and 12**, alerting the portfolio manager that the vendor feed contains corrupt pricing records.

---

## Interactive Quiz Question for Luca

> **Code Quiz Question:**  
> In the Rule 4 implementation:
> ```python
> sorted_vintages = sorted(vintage_list, key=lambda x: (x["published_on"], x["row"]))
> latest_vintage = sorted_vintages[-1]
> older_vintages = sorted_vintages[:-1]
> ```
> **Question:** Why do we include `x["row"]` as the second element in the sorting tuple `(x["published_on"], x["row"])` instead of sorting solely by `x["published_on"]`?
>
> *(Think about what happens if two revisions share the exact same publication date but have different row indices, and answer before reviewing the explanation!)*
