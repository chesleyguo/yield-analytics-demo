# Product X Yield Analytics (demo)

> **Simulated data – for demonstration only.** "Product X" is a generic laptop. Nothing here describes a real company, product, factory or process.

An interactive yield-analytics dashboard that follows one story: a new contract manufacturer ramps Product X on a final-assembly + test line. Week 1 final yield is **39%**. Over 12 weeks (EVT → DVT → PVT → Ramp), three data-driven fixes bring it to **91%**.

The flow is: **find the problem → root cause → validate the fix → hold the gain.**

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python generate_data.py        # writes CSVs to ./data (fixed seed, about 1 s)
streamlit run app.py           # opens http://localhost:8501
```

If `./data` is missing, the app generates the data itself on first load.

**Language / 语言:** the dashboard is bilingual. Use the **🌐 Language / 语言** switch in the sidebar, or open `http://localhost:8501/?lang=zh` for Chinese. You can also set `DEMO_LANG=zh` when you start the app. Every label, chart, takeaway, root-cause hint and Q&A answer is translated, and Q&A understands questions in either language. Defect codes and lot IDs stay as identifiers.
To open the app on a particular page, set `DEMO_START_PAGE` to one of `overview`, `drilldown`, `pareto`, `spc`, `ai-insights` or `program`:

```bash
DEMO_START_PAGE=ai-insights streamlit run app.py
```

Smoke test. It opens every page and the main controls headlessly in both English and Chinese, and checks that all three root causes are found:

```bash
python tests/smoke_test.py
```

## Pages

| Page | What it shows |
|---|---|
| **Overview** | KPI cards: final yield, FPY, RTY, DPPM, retest rate and units, each with week-over-week change. Also a yield trend marked with the three fixes and the build phases, plus yield loss by station. |
| **Drill-down** | Filters for weeks, line, shift and phase. Yield can be broken down by station, line, shift, supplier lot or phase. |
| **Defect Pareto** | Top defect codes with a cumulative-% line and an 80% reference. Also a before (W1–4) vs after (W10–12) comparison. |
| **SPC** | X̄ chart with UCL/CL/LCL computed from a baseline period you choose. Western Electric rules 1–4 are flagged. Cpk is shown before and after the fix, with a capability histogram against the spec limits. |
| **AI Insights** | Anomaly detection, root-cause hints written as plain sentences, a 2×2 DOE (cure temp × cure time) and rule-based "Ask the data" Q&A. |
| **Program view** | The TPM angle: users, data sources, rollout phases, success metrics and risks. |

Every chart has a one-line takeaway. Most takeaways are computed from the data, so they change when you change the filters.

## Synthetic data (`generate_data.py`, seed = 42)

* 12 weeks × 6 days, 3 lines, 2 shifts, 6 stations in order: SMT/Board Test → Display Attach → Enclosure Assembly → Keyboard/Trackpad → Functional Test → Cosmetic Inspection
* About 17k units and 90k station records. Each unit has a serial, timestamp, line, shift, station, PASS/FAIL, retest count, defect code, keyboard and display supplier lots, cure temp, cure time and screw torque.
* The general learning curve (an immature process early on) and no-fault-found retests are both modelled.

| # | Embedded root cause | Active | Fix (in `data/fix_events.csv`) |
|---|---|---|---|
| 1 | Line 2 adhesive-cure oven drifts hot, which causes `DSP-ADHESIVE-DELAM` at Display Attach | weeks 2–4 | W5: oven recalibrated, DOE recipe 80 °C / 25 min |
| 2 | Keyboard lot `KB-B-3104` (Supplier B) has a high `KB-KEY-STICK` rate | weeks 3–6 | W7: lot quarantined, supplier 8D |
| 3 | Night shift has more `COS-SCRATCH` (a handling/training gap) | weeks 1–8 | W9: retraining + boundary samples |

Display-panel lots carry no embedded effect. They act as a **negative control**, so you can show that the method doesn't flag everything.

Output files: `data/station_results.csv`, `data/units.csv`, `data/fix_events.csv`, `data/doe_results.csv`.

## Methods (in `analytics.py`)

* **KPIs** (each card shows its definition under the number):
  * Final yield = units that pass all 6 stations (retests allowed) ÷ units started.
  * FPY = units that pass every station on the first attempt, with no retest ÷ units started.
  * RTY = Π station first-pass yields, using the same station FPYs as the Drill-down page. RTY ≤ FPY because defects cluster on the same "marginal" units. The generator models this with a per-unit marginality factor.
  * DPPM = failed first-pass station tests ÷ all station tests × 1,000,000.
  * Retest rate = station tests that failed first, then passed on retest ÷ all station tests.
  * `kpi_consistency()` checks every week that RTY = Π station FPY ≤ FPY ≤ final yield, and that DPPM/10⁶ = 1 − pooled station FPY = retest rate + confirmed-fail rate. The smoke test fails if any of these breaks.
* **Anomaly detection**: a two-proportion z-test. Each line-day, line-week, shift-week and keyboard lot is compared with its *peers built in the same week*, so the normal ramp improvement isn't flagged.
  * Severity is set by the σ distance. Values beyond 10σ are displayed as ">10σ".
  * The UI shows the top 3 cards; the full table is in a collapsed expander.
  * Each anomaly gets a rule-based suggested action, owner role and timeframe, picked from the station whose failures are most elevated in that group.
* **Root-cause hints**: for each top defect code, a depth-1 (or depth-2) decision tree searches line, shift, supplier lots and process parameters for the best split. Build week is also a candidate feature, so a pure learning-curve effect "wins" and is discarded. Each hint is kept only if:
  * the week-adjusted (Mantel-Haenszel) risk ratio is at least 2×,
  * the crude risk ratio is at least 1.5×,
  * and the week-stratified Cochran-Mantel-Haenszel p < 1e-6.
* **Factor association**: week-stratified χ² of final failure against each factor.
* **SPC**: subgroups of n = 5 sampled per line, shift and day. Limits use A2·R̄. The chart applies Western Electric rules 1–4, and Cpk uses the spec limits.
* **DOE**: a 2² full factorial with 3 replicates and 3 center points. It reports main effects, the interaction, a noise band and the best setting.
* **Q&A**: keyword/intent matching over the data. It needs **no API key and no network**.

## Files

```
app.py              Streamlit UI (6 pages)
analytics.py        metrics, SPC, anomaly detection, root-cause hints, DOE, Q&A
i18n.py             English / Chinese display translations
generate_data.py    synthetic data generator (numpy/pandas, fixed seed)
tests/smoke_test.py headless test of every page and root-cause detection
DEMO_SCRIPT.md      2-minute and 30-second talk tracks
DEMO_SCRIPT_zh.md   中文讲稿 (Chinese talk tracks + glossary)
```
