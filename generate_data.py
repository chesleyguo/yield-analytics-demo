"""
Synthetic yield data generator for the "Product X" yield-analytics demo.

SIMULATED DATA - FOR DEMONSTRATION ONLY.
Nothing here describes any real company, product, factory or process.

Story: a new contract manufacturer ramps a generic laptop ("Product X") on a
final-assembly + test line. Week 1 final yield is ~40%; three embedded root
causes are found and fixed, and yield climbs to ~92% by week 12.

Embedded root causes (for the dashboard to "discover"):
  1. Line 2 adhesive-cure oven drifts hot (weeks 2-4) -> display-attach
     delamination. Fixed week 5 (oven recalibrated + DOE-optimised recipe).
  2. Keyboard lot KB-B-3104 (Supplier B) has a high key-stick rate.
     In use weeks 3-6; quarantined week 7.
  3. Night shift has more cosmetic scratches (handling / training gap).
     Retraining + boundary samples in week 9.

Outputs (CSV, in ./data):
  station_results.csv  one row per unit x station visited
  units.csv            one row per unit (final outcome)
  fix_events.csv       dated corrective actions
  doe_results.csv      2x2 factorial DOE on cure temp x cure time

Run:  python generate_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_WEEKS = 12
DAYS_PER_WEEK = 6  # Mon-Sat production
START_DATE = pd.Timestamp("2026-01-05")  # a Monday
LINES = ["Line 1", "Line 2", "Line 3"]
SHIFTS = ["Day", "Night"]

STATIONS = [
    "SMT / Board Test",
    "Display Attach",
    "Enclosure Assembly",
    "Keyboard / Trackpad",
    "Functional Test",
    "Cosmetic Inspection",
]

# Generic defect codes per station (first = most common "background" code)
DEFECT_CODES = {
    "SMT / Board Test": ["SMT-SOLDER-BRIDGE", "SMT-OPEN-JOINT", "BT-PMIC-FAIL"],
    "Display Attach": ["DSP-ADHESIVE-DELAM", "DSP-PANEL-GAP"],
    "Enclosure Assembly": ["ENC-SCREW-STRIP", "ENC-HOUSING-GAP"],
    "Keyboard / Trackpad": ["KB-KEY-STICK", "TP-CLICK-FAIL"],
    "Functional Test": ["FT-WIFI-RANGE", "FT-NO-BOOT", "FT-AUDIO"],
    "Cosmetic Inspection": ["COS-SCRATCH", "COS-DENT", "COS-PARTICLE"],
}

# Spec limits for the process parameters
SPECS = {
    "cure_temp_c": dict(target=80.0, lsl=75.0, usl=85.0, label="Adhesive cure temp (°C)"),
    "cure_time_min": dict(target=25.0, lsl=22.0, usl=28.0, label="Adhesive cure time (min)"),
    "screw_torque_kgfcm": dict(target=1.80, lsl=1.60, usl=2.00, label="Screw torque (kgf·cm)"),
}

FIX_EVENTS = [
    dict(week=5, date="2026-02-02", title="Line 2 cure oven recalibrated; DOE recipe 80°C / 25 min",
         short="Oven fix (L2)", owner="Process Eng.", root_cause="Cure-temp drift on Line 2",
         affected_station="Display Attach"),
    dict(week=7, date="2026-02-16", title="Keyboard lot KB-B-3104 quarantined; supplier 8D opened",
         short="Lot quarantine", owner="SQE / Supplier Mgmt", root_cause="Bad keyboard lot KB-B-3104",
         affected_station="Keyboard / Trackpad"),
    dict(week=9, date="2026-03-02", title="Night-shift handling retraining + cosmetic boundary samples",
         short="Night-shift training", owner="Mfg. Ops / Quality", root_cause="Night-shift cosmetic handling",
         affected_station="Cosmetic Inspection"),
]

PHASES = {1: "EVT", 2: "EVT", 3: "EVT", 4: "DVT", 5: "DVT", 6: "DVT",
          7: "PVT", 8: "PVT", 9: "PVT", 10: "Ramp", 11: "Ramp", 12: "Ramp"}


def daily_volume(week: int) -> int:
    """Units started per line per shift per day - ramps with phase."""
    return int(np.interp(week, [1, 3, 6, 9, 12], [14, 22, 36, 54, 72]))


def learning(week_float: np.ndarray, start: float, end: float) -> np.ndarray:
    """Exponential learning curve from `start` (week 1) to `end` (week 12)."""
    t = (week_float - 1) / (N_WEEKS - 1)
    return end + (start - end) * np.exp(-3.2 * t)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def build_units(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    serial = 0
    for week in range(1, N_WEEKS + 1):
        for d in range(DAYS_PER_WEEK):
            day_idx = (week - 1) * DAYS_PER_WEEK + d
            date = START_DATE + pd.Timedelta(days=(week - 1) * 7 + d)
            for line in LINES:
                for shift in SHIFTS:
                    n = rng.poisson(daily_volume(week) * (0.92 if shift == "Night" else 1.0))
                    base_hour = 7 if shift == "Day" else 19
                    offs = np.sort(rng.uniform(0, 11.5, n))
                    for o in offs:
                        serial += 1
                        rows.append((f"PX{serial:07d}", date + pd.Timedelta(hours=base_hour + o),
                                     date, week, day_idx, line, shift))
    u = pd.DataFrame(rows, columns=["serial", "start_ts", "date", "week", "day_idx", "line", "shift"])
    u["phase"] = u["week"].map(PHASES)
    u["week_float"] = u["week"] + (u["day_idx"] % DAYS_PER_WEEK) / DAYS_PER_WEEK
    return u


def assign_lots(u: pd.DataFrame, rng: np.random.Generator) -> None:
    n = len(u)
    wk = u["week"].to_numpy()
    # Keyboard lots: Supplier A ships lot per week, Supplier B ships lot per ~2 weeks.
    a_lot = np.array([f"KB-A-21{w:02d}" for w in wk])
    b_week = ((wk - 1) // 2) * 2 + 1
    b_lot = np.array([f"KB-B-31{w:02d}" for w in b_week])
    # Bad lot KB-B-3104 is consumed weeks 3-6 (longer than normal: big lot), then quarantined.
    bad_window = (wk >= 3) & (wk <= 6)
    b_lot = np.where(bad_window, "KB-B-3104", b_lot)
    use_b = rng.random(n) < np.where(bad_window, 0.40, 0.35)
    u["kb_lot"] = np.where(use_b, b_lot, a_lot)
    u["kb_supplier"] = np.where(use_b, "Supplier B", "Supplier A")
    # Display panel lots (negative control - no embedded issue)
    d_week = ((wk - 1) // 3) * 3 + 1
    u["display_lot"] = np.array([f"DP-C-31{w:02d}" if r < 0.5 else f"DP-D-52{w:02d}"
                                 for w, r in zip(d_week, rng.random(n))])


def process_params(u: pd.DataFrame, rng: np.random.Generator) -> None:
    n = len(u)
    wf = u["week_float"].to_numpy()
    line = u["line"].to_numpy()
    # Cure temperature: all lines ~80 °C, Line 2 drifts hot from week 2 until the fix in week 5.
    temp_mean = np.full(n, 80.0)
    drift = np.clip((wf - 2.0) / 3.0, 0, 1) * 9.5  # up to +9.5 °C by end of week 4
    l2_pre = (line == "Line 2") & (wf < 5.0)
    temp_mean = np.where(l2_pre, 80.3 + drift, temp_mean)
    temp_mean = np.where(line == "Line 3", 79.6, temp_mean)
    temp_sd = np.where(wf < 5.0, 1.6, 1.1)  # tighter after oven PM + SPC alarm
    u["cure_temp_c"] = np.round(rng.normal(temp_mean, temp_sd), 2)
    # Cure time: recipe was 22 min pre-fix (short), DOE recipe 25 min after week 5.
    time_mean = np.where(wf < 5.0, 22.5, 25.0)
    u["cure_time_min"] = np.round(rng.normal(time_mean, 0.9), 2)
    # Screw torque: stable, slightly noisy early (driver calibration)
    torque_sd = np.where(wf < 4.0, 0.075, 0.05)
    u["screw_torque_kgfcm"] = np.round(rng.normal(1.80, torque_sd), 3)


def failure_probs(u: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return (hard-defect prob, no-fault-found prob) arrays of shape (n, 6)."""
    n = len(u)
    wf = u["week_float"].to_numpy()
    line = u["line"].to_numpy()
    shift = u["shift"].to_numpy()
    temp = u["cure_temp_c"].to_numpy()
    ctime = u["cure_time_min"].to_numpy()
    torque = u["screw_torque_kgfcm"].to_numpy()
    lot = u["kb_lot"].to_numpy()

    p = np.zeros((n, 6))
    # 0 SMT / Board test - immature stencil + reflow profile early
    p[:, 0] = learning(wf, 0.200, 0.008)
    # 1 Display attach - background + cure-temp/cure-time physics
    over = sigmoid((temp - 85.5) / 1.1)  # sharp rise above ~85-86 °C
    short = sigmoid((22.0 - ctime) / 0.8)
    p[:, 1] = learning(wf, 0.100, 0.008) + 0.42 * over + 0.06 * short
    # 2 Enclosure - torque out of spec strips screws
    oos = (torque < SPECS["screw_torque_kgfcm"]["lsl"]) | (torque > SPECS["screw_torque_kgfcm"]["usl"])
    p[:, 2] = learning(wf, 0.120, 0.008) + 0.25 * oos
    # 3 Keyboard / trackpad - bad lot
    p[:, 3] = learning(wf, 0.090, 0.008) + np.where(lot == "KB-B-3104", 0.20, 0.0)
    # 4 Functional test
    p[:, 4] = learning(wf, 0.230, 0.012)
    # 5 Cosmetic - night shift handling gap until training in week 9
    night_gap = np.where((shift == "Night") & (wf < 9.0), 0.13, 0.0)
    night_gap = np.where((shift == "Night") & (wf >= 9.0), 0.008, night_gap)
    p[:, 5] = learning(wf, 0.110, 0.009) + night_gap
    p = np.clip(p, 0, 0.95)

    # No-fault-found (test flakiness -> retest passes). Higher at test stations.
    nff = np.zeros((n, 6))
    base_nff = learning(wf, 0.05, 0.012)
    nff[:, :] = base_nff[:, None] * np.array([1.6, 0.6, 0.4, 0.8, 1.8, 1.0])[None, :]
    return p, nff


def defect_code_for(station_idx: int, unit_ctx: dict, rng: np.random.Generator) -> str:
    st = STATIONS[station_idx]
    codes = DEFECT_CODES[st]
    if station_idx == 1 and (unit_ctx["temp"] > 84.5 or unit_ctx["ctime"] < 21.5):
        return "DSP-ADHESIVE-DELAM" if rng.random() < 0.92 else "DSP-PANEL-GAP"
    if station_idx == 2 and unit_ctx["torque_oos"]:
        return "ENC-SCREW-STRIP"
    if station_idx == 3 and unit_ctx["lot"] == "KB-B-3104":
        return "KB-KEY-STICK" if rng.random() < 0.9 else "TP-CLICK-FAIL"
    if station_idx == 5 and unit_ctx["night_pre"]:
        return "COS-SCRATCH" if rng.random() < 0.8 else rng.choice(["COS-DENT", "COS-PARTICLE"])
    weights = {
        "SMT / Board Test": [0.75, 0.15, 0.10],
        "Display Attach": [0.15, 0.85],
        "Enclosure Assembly": [0.2, 0.8],
        "Keyboard / Trackpad": [0.3, 0.7],
        "Functional Test": [0.75, 0.15, 0.10],
        "Cosmetic Inspection": [0.45, 0.35, 0.20],
    }[st]
    return str(rng.choice(codes, p=weights))


def simulate(u: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    p, nff = failure_probs(u)
    n = len(u)
    alive = np.ones(n, dtype=bool)
    records = []
    t = u["start_ts"].to_numpy()
    cycle_min = np.array([18, 22, 15, 12, 35, 8])
    temp = u["cure_temp_c"].to_numpy()
    ctime = u["cure_time_min"].to_numpy()
    torque = u["screw_torque_kgfcm"].to_numpy()
    tlsl, tusl = SPECS["screw_torque_kgfcm"]["lsl"], SPECS["screw_torque_kgfcm"]["usl"]
    lot = u["kb_lot"].to_numpy()
    night_pre = ((u["shift"] == "Night") & (u["week_float"] < 9.0)).to_numpy()

    for s in range(6):
        idx = np.flatnonzero(alive)
        r_def = rng.random(len(idx))
        r_nff = rng.random(len(idx))
        hard = r_def < p[idx, s]
        flaky = (~hard) & (r_nff < nff[idx, s])
        retests = np.zeros(len(idx), dtype=int)
        retests[flaky] = 1 + (rng.random(flaky.sum()) < 0.15)
        retests[hard] = 1 + (rng.random(hard.sum()) < 0.4)  # confirm the failure
        t = t + (cycle_min[s] + rng.exponential(10, n)).astype("timedelta64[m]")
        for j, i in enumerate(idx):
            code = ""
            if hard[j]:
                code = defect_code_for(s, dict(temp=temp[i], ctime=ctime[i],
                                                torque_oos=(torque[i] < tlsl) or (torque[i] > tusl),
                                                lot=lot[i], night_pre=night_pre[i]), rng)
            records.append((i, s, t[i], not hard[j], (not hard[j]) and retests[j] == 0,
                            int(retests[j]), code))
        alive[idx[hard]] = False

    sr = pd.DataFrame(records, columns=["uidx", "station_seq", "timestamp", "passed",
                                        "first_pass", "retest_count", "defect_code"])
    meta = u.reset_index(drop=True)
    cols = ["serial", "date", "week", "phase", "line", "shift", "kb_lot", "kb_supplier",
            "display_lot", "cure_temp_c", "cure_time_min", "screw_torque_kgfcm"]
    sr = sr.join(meta[cols], on="uidx")
    sr["station"] = sr["station_seq"].map(dict(enumerate(STATIONS)))
    sr["station_seq"] = sr["station_seq"] + 1
    sr["result"] = np.where(sr["passed"], "PASS", "FAIL")
    sr = sr.sort_values(["uidx", "station_seq"]).drop(columns=["uidx", "passed"])
    order = ["serial", "timestamp", "date", "week", "phase", "line", "shift", "station_seq",
             "station", "result", "first_pass", "retest_count", "defect_code", "kb_lot",
             "kb_supplier", "display_lot", "cure_temp_c", "cure_time_min", "screw_torque_kgfcm"]
    return sr[order]


def unit_summary(u: pd.DataFrame, sr: pd.DataFrame) -> pd.DataFrame:
    g = sr.groupby("serial")
    last = sr.loc[g["station_seq"].idxmax()].set_index("serial")
    out = u.drop(columns=["day_idx", "week_float"]).set_index("serial")
    out["stations_completed"] = last["station_seq"] - (last["result"] == "FAIL").astype(int)
    out["final_result"] = np.where((last["station_seq"] == 6) & (last["result"] == "PASS"), "PASS", "FAIL")
    out["fail_station"] = np.where(out["final_result"] == "FAIL", last["station"], "")
    out["defect_code"] = np.where(out["final_result"] == "FAIL", last["defect_code"], "")
    out["total_retests"] = g["retest_count"].sum()
    out["first_pass_all"] = g["first_pass"].all() & (out["final_result"] == "PASS")
    return out.reset_index()


def doe_results(rng: np.random.Generator) -> pd.DataFrame:
    """2^2 full factorial (3 replicates) + 3 center points, response = display-attach yield (%)."""
    rows = []
    levels = {"cure_temp_c": (80.0, 88.0), "cure_time_min": (20.0, 25.0)}
    run = 0
    for rep in range(3):
        for a in (-1, 1):
            for b in (-1, 1):
                run += 1
                y = 91.0 - 3.6 * a + 2.2 * b - 1.2 * a * b + rng.normal(0, 0.6)
                rows.append((run, rep + 1, a, b, levels["cure_temp_c"][(a + 1) // 2],
                             levels["cure_time_min"][(b + 1) // 2], round(min(y, 99.9), 2), 200))
    for c in range(3):
        run += 1
        y = 91.2 + rng.normal(0, 0.6)
        rows.append((run, c + 1, 0, 0, 84.0, 22.5, round(y, 2), 200))
    df = pd.DataFrame(rows, columns=["run", "replicate", "temp_coded", "time_coded",
                                     "cure_temp_c", "cure_time_min", "display_attach_yield_pct",
                                     "units_per_run"])
    df["note"] = "Simulated data - for demonstration only"
    return df


def main(out_dir: str = "data") -> None:
    rng = np.random.default_rng(SEED)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    u = build_units(rng)
    assign_lots(u, rng)
    process_params(u, rng)
    sr = simulate(u, rng)
    units = unit_summary(u, sr)

    sr.to_csv(out / "station_results.csv", index=False)
    units.to_csv(out / "units.csv", index=False)
    pd.DataFrame(FIX_EVENTS).to_csv(out / "fix_events.csv", index=False)
    doe_results(rng).to_csv(out / "doe_results.csv", index=False)

    wk = units.groupby("week")["final_result"].apply(lambda s: (s == "PASS").mean())
    print(f"Units: {len(units):,}   station records: {len(sr):,}")
    print("Final yield by week:", " ".join(f"W{w}:{y:.0%}" for w, y in wk.items()))
    print(f"Wrote CSVs to {out.resolve()}")


if __name__ == "__main__":
    main()
