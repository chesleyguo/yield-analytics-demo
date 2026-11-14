"""Analytics layer: yield metrics, SPC, anomaly detection, root-cause hints, DOE, Q&A.

All functions are pure pandas/numpy/scipy/sklearn so they can be unit-tested
without Streamlit. Data is SIMULATED - for demonstration only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.tree import DecisionTreeClassifier

DATA_DIR = Path(__file__).parent / "data"

STATIONS = [
    "SMT / Board Test", "Display Attach", "Enclosure Assembly",
    "Keyboard / Trackpad", "Functional Test", "Cosmetic Inspection",
]
SPECS = {
    "cure_temp_c": dict(target=80.0, lsl=75.0, usl=85.0, label="Adhesive cure temp (°C)", unit="°C"),
    "cure_time_min": dict(target=25.0, lsl=22.0, usl=28.0, label="Adhesive cure time (min)", unit="min"),
    "screw_torque_kgfcm": dict(target=1.80, lsl=1.60, usl=2.00, label="Screw torque (kgf·cm)", unit="kgf·cm"),
}


# --------------------------------------------------------------------------- loading
def load_data(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    sr = pd.read_csv(data_dir / "station_results.csv", parse_dates=["timestamp", "date"],
                     keep_default_na=False, na_values=[])
    for c in ["cure_temp_c", "cure_time_min", "screw_torque_kgfcm"]:
        sr[c] = pd.to_numeric(sr[c])
    sr["first_pass"] = sr["first_pass"].astype(str).eq("True")
    units = pd.read_csv(data_dir / "units.csv", parse_dates=["start_ts", "date"],
                        keep_default_na=False, na_values=[])
    units["first_pass_all"] = units["first_pass_all"].astype(str).eq("True")
    for c in ["cure_temp_c", "cure_time_min", "screw_torque_kgfcm"]:
        units[c] = pd.to_numeric(units[c])
    fixes = pd.read_csv(data_dir / "fix_events.csv")
    doe = pd.read_csv(data_dir / "doe_results.csv")
    return dict(sr=sr, units=units, fixes=fixes, doe=doe)


# --------------------------------------------------------------------------- KPIs
def kpis(units: pd.DataFrame, sr: pd.DataFrame) -> dict[str, float]:
    """Yield KPIs for whatever slice of data is passed in."""
    n = len(units)
    if n == 0:
        return dict(final_yield=np.nan, fpy=np.nan, rty=np.nan, dppm=np.nan, retest_rate=np.nan, units=0)
    station_fpy = sr.groupby("station")["first_pass"].mean()
    rty = float(station_fpy.prod()) if len(station_fpy) else np.nan
    return dict(
        final_yield=(units["final_result"] == "PASS").mean(),
        fpy=units["first_pass_all"].mean(),
        rty=rty,
        dppm=(sr["result"] == "FAIL").mean() * 1e6,
        retest_rate=(sr["retest_count"] > 0).mean(),
        units=n,
    )


def weekly_trend(units: pd.DataFrame, sr: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for w, u in units.groupby("week"):
        k = kpis(u, sr[sr["week"] == w])
        k["week"] = w
        k["phase"] = u["phase"].iloc[0]
        rows.append(k)
    return pd.DataFrame(rows)


def yield_by(units: pd.DataFrame, col: str) -> pd.DataFrame:
    g = units.groupby(col)
    out = pd.DataFrame({"units": g.size(), "passed": g["final_result"].apply(lambda s: (s == "PASS").sum())})
    out["yield"] = out["passed"] / out["units"]
    return out.reset_index()


def station_fpy(sr: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    keys = ["station"] + ([by] if by else [])
    g = sr.groupby(keys)
    out = pd.DataFrame({"tested": g.size(), "fpy": g["first_pass"].mean(),
                        "fail_rate": g["result"].apply(lambda s: (s == "FAIL").mean())}).reset_index()
    out["station"] = pd.Categorical(out["station"], STATIONS, ordered=True)
    return out.sort_values(keys)


def pareto(sr: pd.DataFrame) -> pd.DataFrame:
    f = sr[sr["result"] == "FAIL"]
    p = f.groupby(["defect_code", "station"]).size().reset_index(name="count")
    p = p.sort_values("count", ascending=False).reset_index(drop=True)
    p["pct"] = p["count"] / p["count"].sum()
    p["cum_pct"] = p["pct"].cumsum()
    return p


# --------------------------------------------------------------------------- SPC
# Shewhart constants for subgroup size n
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483}
D3 = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004}


def spc_subgroups(units: pd.DataFrame, param: str, n: int = 5, seed: int = 7) -> pd.DataFrame:
    """Simulate a sampling plan: n units sampled per line x shift x day."""
    rng = np.random.default_rng(seed)
    rows = []
    for (date, shift, line), g in units.groupby(["date", "shift", "line"], sort=True):
        if len(g) < n:
            continue
        s = g[param].to_numpy()[rng.choice(len(g), n, replace=False)]
        rows.append(dict(date=date, shift=shift, line=line, week=int(g["week"].iloc[0]),
                         xbar=s.mean(), r=s.max() - s.min(), samples=s))
    sg = pd.DataFrame(rows)
    sg["shift_order"] = sg["shift"].map({"Day": 0, "Night": 1})
    sg = sg.sort_values(["line", "date", "shift_order"]).reset_index(drop=True)
    sg["label"] = sg["date"].dt.strftime("%b %d") + " " + sg["shift"].str[0]
    return sg


def control_limits(sg: pd.DataFrame, n: int = 5) -> dict[str, float]:
    xbb, rbar = sg["xbar"].mean(), sg["r"].mean()
    sigma_x = A2[n] * rbar / 3
    return dict(cl=xbb, ucl=xbb + 3 * sigma_x, lcl=xbb - 3 * sigma_x, sigma=sigma_x,
                r_cl=rbar, r_ucl=D4[n] * rbar, r_lcl=D3[n] * rbar)


def western_electric(x: np.ndarray, cl: float, sigma: float) -> list[set[int]]:
    """Return, per point, the set of Western Electric rules (1-4) it violates."""
    z = (np.asarray(x) - cl) / sigma
    flags: list[set[int]] = [set() for _ in z]
    for i in range(len(z)):
        if abs(z[i]) > 3:
            flags[i].add(1)
        for side in (1, -1):
            if i >= 2:
                w = z[i - 2:i + 1] * side
                if (w > 2).sum() >= 2 and w[-1] > 2:
                    flags[i].add(2)
            if i >= 4:
                w = z[i - 4:i + 1] * side
                if (w > 1).sum() >= 4 and w[-1] > 1:
                    flags[i].add(3)
            if i >= 7:
                w = z[i - 7:i + 1] * side
                if (w > 0).all():
                    flags[i].add(4)
    return flags


WE_RULES = {
    1: "1 point beyond 3σ",
    2: "2 of 3 points beyond 2σ (same side)",
    3: "4 of 5 points beyond 1σ (same side)",
    4: "8 points in a row on one side of center",
}


def cpk(values: np.ndarray, lsl: float, usl: float) -> tuple[float, float]:
    mu, sd = float(np.mean(values)), float(np.std(values, ddof=1))
    if sd == 0:
        return np.nan, np.nan
    return min(usl - mu, mu - lsl) / (3 * sd), (usl - lsl) / (6 * sd)


# --------------------------------------------------------------------------- anomaly detection
def detect_anomalies(units: pd.DataFrame, z_thresh: float = 3.0, min_units: int = 15) -> pd.DataFrame:
    """Flag line-days and keyboard lots whose yield falls below binomial p-chart limits.

    Baseline for each line-day = pooled yield of the *other* two lines that same week
    (so slow improvement over the ramp isn't flagged). Lots are compared with other lots
    in the same weeks.
    """
    out = []
    ld = units.groupby(["date", "week", "line"]).agg(
        units=("serial", "size"), passed=("final_result", lambda s: (s == "PASS").sum())).reset_index()
    wk_line = ld.groupby(["week", "line"])[["units", "passed"]].sum()
    wk_all = ld.groupby("week")[["units", "passed"]].sum()
    for _, r in ld.iterrows():
        if r["units"] < min_units:
            continue
        others = wk_all.loc[r["week"]] - wk_line.loc[(r["week"], r["line"])]
        p0 = others["passed"] / others["units"]
        y = r["passed"] / r["units"]
        se = np.sqrt(p0 * (1 - p0) / r["units"])
        z = (y - p0) / se if se > 0 else 0
        if z < -z_thresh:
            out.append(dict(kind="Line-day", entity=f"{r['line']} · {r['date']:%a %b %d}",
                            week=int(r["week"]), units=int(r["units"]), yield_=y, expected=p0, z=z,
                            line=r["line"], date=r["date"]))
    # line-week (others = other two lines same week)
    for (w, line), r in wk_line.iterrows():
        o = wk_all.loc[w] - r
        p0 = o["passed"] / o["units"]
        y = r["passed"] / r["units"]
        z = (y - p0) / np.sqrt(p0 * (1 - p0) / r["units"])
        if z < -z_thresh:
            out.append(dict(kind="Line-week", entity=f"{line} · Week {w}", week=int(w), units=int(r["units"]),
                            yield_=y, expected=p0, z=z, line=line, date=pd.NaT))
    # shift-week
    sw = units.groupby(["week", "shift"]).agg(units=("serial", "size"),
                                              passed=("final_result", lambda s: (s == "PASS").sum())).reset_index()
    for w, g in sw.groupby("week"):
        for _, r in g.iterrows():
            o = g[g["shift"] != r["shift"]]
            p0 = o["passed"].sum() / o["units"].sum()
            y = r["passed"] / r["units"]
            z = (y - p0) / np.sqrt(p0 * (1 - p0) / r["units"])
            if z < -z_thresh:
                out.append(dict(kind="Shift-week", entity=f"{r['shift']} shift · Week {w}", week=int(w),
                                units=int(r["units"]), yield_=y, expected=p0, z=z, line="", date=pd.NaT))
    # keyboard lots (keyboard-station FPY vs other lots in the same weeks)
    for lot, g in units.groupby("kb_lot"):
        weeks = g["week"].unique()
        ref = units[units["week"].isin(weeks) & (units["kb_lot"] != lot)]
        def kb_ok(df):
            return (df["fail_station"] != "Keyboard / Trackpad")
        y, p0 = kb_ok(g).mean(), kb_ok(ref).mean()
        z = (y - p0) / np.sqrt(p0 * (1 - p0) / len(g))
        if z < -z_thresh and len(g) >= min_units:
            out.append(dict(kind="Supplier lot", entity=f"{lot} (keyboard station)",
                            week=int(weeks.min()), units=len(g), yield_=y, expected=p0, z=z, line="", date=pd.NaT))
    df = pd.DataFrame(out)
    if df.empty:
        return df
    return df.sort_values("z").reset_index(drop=True)


# --------------------------------------------------------------------------- root-cause hints
FEATURE_LABELS = {
    "cure_temp_c": "cure temp", "cure_time_min": "cure time", "screw_torque_kgfcm": "screw torque",
    "is_night": "night shift", "week": "week",
}


def _feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in ["cure_temp_c", "cure_time_min", "screw_torque_kgfcm"]:
        X[c] = df[c]
    X["is_night"] = (df["shift"] == "Night").astype(int)
    for line in sorted(df["line"].unique()):
        X[f"line={line}"] = (df["line"] == line).astype(int)
    for lot in sorted(df["kb_lot"].unique()):
        X[f"kb_lot={lot}"] = (df["kb_lot"] == lot).astype(int)
    for lot in sorted(df["display_lot"].unique()):
        X[f"display_lot={lot}"] = (df["display_lot"] == lot).astype(int)
    return X


def _describe(feat: str, thr: float, left: bool) -> tuple[str, callable]:
    """Human-readable condition and a mask function for a tree split."""
    if "=" in feat:
        name, val = feat.split("=", 1)
        nice = {"line": val, "kb_lot": f"keyboard lot {val}", "display_lot": f"display lot {val}"}[name]
        if left:
            return f"not {nice}", lambda d: d[feat] <= 0.5
        return nice, lambda d: d[feat] > 0.5
    if feat == "is_night":
        return ("day shift", lambda d: d[feat] <= 0.5) if left else ("night shift", lambda d: d[feat] > 0.5)
    unit = SPECS[feat]["unit"]
    lbl = FEATURE_LABELS[feat]
    fmt = f"{thr:.2f}" if feat == "screw_torque_kgfcm" else f"{thr:.1f}"
    if left:
        return f"{lbl} ≤ {fmt} {unit}", lambda d: d[feat] <= thr
    return f"{lbl} > {fmt} {unit}", lambda d: d[feat] > thr


@dataclass
class Hint:
    station: str
    defect_code: str
    condition: str
    risk_ratio: float          # week-adjusted (Mantel-Haenszel) risk ratio
    rate_in: float
    rate_out: float
    n_in: int
    share_of_failures: float
    p_value: float
    context: str = ""

    @property
    def sentence(self) -> str:
        ctx = f" {self.context}" if self.context else ""
        return (f"**{self.station}** failures ({self.defect_code}) are **{self.risk_ratio:.1f}× more likely** "
                f"when **{self.condition}**{ctx} — {self.rate_in:.1%} vs {self.rate_out:.1%} of units; "
                f"this condition accounts for {self.share_of_failures:.0%} of those failures.")


def _mh_risk_ratio(y: np.ndarray, mask: np.ndarray, strata: np.ndarray) -> float:
    """Mantel-Haenszel risk ratio of y between mask / ~mask, stratified (here: by week)."""
    num = den = 0.0
    for s in np.unique(strata):
        k = strata == s
        n1, n0 = mask[k].sum(), (~mask[k]).sum()
        if n1 == 0 or n0 == 0:
            continue
        a, c, n = y[k & mask].sum(), y[k & ~mask].sum(), k.sum()
        num += a * n0 / n
        den += c * n1 / n
    return num / den if den > 0 else np.inf


def root_cause_hints(sr: pd.DataFrame, top_n_codes: int = 8, min_support: int = 40,
                     min_rr: float = 2.0) -> list[Hint]:
    """For each top defect code, find the single unit-context split that best separates
    failures (depth-1 decision tree; 'week' is offered as a feature so a plain learning-curve
    effect wins over spurious time-confounded factors). Keep splits whose week-adjusted
    risk ratio is large, then describe where the at-risk units concentrate."""
    hints: list[Hint] = []
    p = pareto(sr)
    for _, row in p.head(top_n_codes).iterrows():
        code, station = row["defect_code"], row["station"]
        d = sr[sr["station"] == station]
        y = (d["defect_code"] == code).astype(int).to_numpy()
        if y.sum() < 15:
            continue
        X = _feature_frame(d)
        X["week"] = d["week"].to_numpy()
        tree = DecisionTreeClassifier(max_depth=1, criterion="entropy",
                                      min_samples_leaf=min_support, random_state=0).fit(X, y)
        t = tree.tree_
        if t.node_count < 3:
            continue
        feat, thr = X.columns[t.feature[0]], t.threshold[0]
        rates = [t.value[c][0][1] / t.value[c][0].sum() for c in (t.children_left[0], t.children_right[0])]
        left = rates[0] > rates[1]
        if feat == "week":
            # Time matters - look one level deeper inside the high-risk time window
            tree = DecisionTreeClassifier(max_depth=2, criterion="entropy",
                                          min_samples_leaf=min_support, random_state=0).fit(X, y)
            t = tree.tree_
            child = t.children_left[0] if left else t.children_right[0]
            if t.children_left[child] == -1 or X.columns[t.feature[child]] == "week":
                continue  # generic learning-curve defect: no specific factor
            feat, thr = X.columns[t.feature[child]], t.threshold[child]
            l, r = t.children_left[child], t.children_right[child]
            left = (t.value[l][0][1] / t.value[l][0].sum()) > (t.value[r][0][1] / t.value[r][0].sum())
        cond, fn = _describe(feat, thr, left)
        if cond.startswith("not "):
            continue
        mask = fn(X).to_numpy()
        n_in = int(mask.sum())
        if n_in < min_support or n_in == len(d):
            continue
        rr = _mh_risk_ratio(y, mask, d["week"].to_numpy())
        if not np.isfinite(rr) or rr < min_rr:
            continue
        a, c = y[mask].sum(), y[~mask].sum()
        crude = (a / n_in) / (c / (~mask).sum()) if c > 0 else np.inf
        if crude < 1.5:
            continue  # adjusted-only effect (e.g. competing defect codes) - not actionable
        _, pval, _, _ = stats.chi2_contingency([[a, n_in - a], [c, (~mask).sum() - c]])
        # Where do the at-risk units concentrate? (line / shift / supplier)
        ctx_parts = []
        sub = d[mask]
        for col, fmt in (("line", "on {}"), ("shift", "on {} shift"), ("kb_supplier", "from {}")):
            if feat.startswith(col) or (col == "shift" and feat == "is_night"):
                continue
            share = sub[col].value_counts(normalize=True)
            base = d[col].value_counts(normalize=True)
            top = share.index[0]
            if share.iloc[0] >= 0.7 and share.iloc[0] > base.get(top, 0) + 0.2:
                ctx_parts.append(fmt.format(top))
        wk = sub.loc[sub["defect_code"] == code, "week"]
        ctx_parts.append(f"(failures concentrated in weeks {int(wk.quantile(.05))}–{int(wk.quantile(.95))})")
        if pval > 1e-6:
            continue  # many splits are searched - demand strong evidence
        hints.append(Hint(station, code, cond, rr, a / n_in, c / (~mask).sum(), n_in,
                          a / y.sum(), pval, " ".join(ctx_parts)))
    return sorted(hints, key=lambda h: -h.risk_ratio)


def factor_association(units: pd.DataFrame) -> pd.DataFrame:
    """Week-stratified chi-square of final failure vs each categorical factor.

    Stratifying by week compares levels only against units built the same week, so the
    overall learning curve doesn't make time-ordered factors (lots) look guilty.
    'Adjusted risk' = observed / expected failures for the worst level, where expected
    uses each week's overall failure rate."""
    d = units.copy()
    d["fail"] = (d["final_result"] == "FAIL").astype(int)
    d["cure_temp_band"] = np.where(d["cure_temp_c"] > 85, "> 85 °C (above USL)", "≤ 85 °C")
    d["torque_band"] = np.where((d["screw_torque_kgfcm"] < 1.6) | (d["screw_torque_kgfcm"] > 2.0),
                                "out of spec", "in spec")
    d["exp"] = d.groupby("week")["fail"].transform("mean")
    names = {"kb_lot": "Keyboard lot", "cure_temp_band": "Cure temp band", "shift": "Shift",
             "line": "Assembly line", "kb_supplier": "Keyboard supplier", "display_lot": "Display lot",
             "torque_band": "Screw torque band"}
    rows = []
    for col, nice in names.items():
        chi2_sum, dof_sum = 0.0, 0
        for _, g in d.groupby("week"):
            ct = pd.crosstab(g[col], g["fail"])
            if ct.shape[0] < 2 or ct.shape[1] < 2:
                continue
            c2, _, dof, _ = stats.chi2_contingency(ct, correction=False)
            chi2_sum += c2
            dof_sum += dof
        if dof_sum == 0:
            continue
        lv = d.groupby(col).agg(obs=("fail", "sum"), exp=("exp", "sum"), n=("fail", "size"))
        lv = lv[lv["n"] >= 30]
        lv["ratio"] = lv["obs"] / lv["exp"]
        worst = lv["ratio"].idxmax()
        pval = stats.chi2.sf(chi2_sum, dof_sum)
        rows.append(dict(factor=nice, chi2=chi2_sum, dof=dof_sum, p_value=pval,
                         strength=(chi2_sum - dof_sum) / len(d),
                         worst_level=str(worst), adj_risk=lv.loc[worst, "ratio"],
                         worst_fail_rate=lv.loc[worst, "obs"] / lv.loc[worst, "n"]))
    out = pd.DataFrame(rows).sort_values("strength", ascending=False).reset_index(drop=True)
    out["significant"] = out["p_value"] < 0.001
    return out


# --------------------------------------------------------------------------- DOE
def doe_analysis(doe: pd.DataFrame) -> dict:
    fact = doe[doe["temp_coded"] != 0]
    y = fact["display_attach_yield_pct"]
    a, b = fact["temp_coded"], fact["time_coded"]
    eff_a = y[a == 1].mean() - y[a == -1].mean()
    eff_b = y[b == 1].mean() - y[b == -1].mean()
    eff_ab = y[a * b == 1].mean() - y[a * b == -1].mean()
    cells = fact.groupby(["cure_temp_c", "cure_time_min"])["display_attach_yield_pct"].mean().reset_index()
    best = cells.loc[cells["display_attach_yield_pct"].idxmax()]
    # replicate-based standard error of an effect
    s2 = fact.groupby(["temp_coded", "time_coded"])["display_attach_yield_pct"].var().mean()
    se = np.sqrt(4 * s2 / len(fact))
    centers = doe[doe["temp_coded"] == 0]["display_attach_yield_pct"]
    tl, th = sorted(fact["cure_temp_c"].unique())
    ml, mh = sorted(fact["cure_time_min"].unique())
    return dict(effects={f"Cure temp ({tl:g}→{th:g} °C)": eff_a, f"Cure time ({ml:g}→{mh:g} min)": eff_b,
                         "Temp × Time interaction": eff_ab},
                se=se, cells=cells, best=best, center_mean=centers.mean(), grand_mean=y.mean())


# --------------------------------------------------------------------------- rule-based Q&A
EXAMPLE_QUESTIONS = [
    "Which line has the lowest yield?",
    "What is the top defect?",
    "Which supplier lot is worst?",
    "Is night shift worse than day shift?",
    "How has yield changed?",
    "Which parameter is least capable?",
    "What fixes were made?",
]


def answer_question(q: str, data: dict) -> str:
    """Keyword/intent matcher over the data. No API key or network needed."""
    ql = q.lower()
    u, sr, fixes = data["units"], data["sr"], data["fixes"]
    wk = re.search(r"week\s*(\d+)", ql)
    if wk:
        w = int(wk.group(1))
        u, sr = u[u["week"] == w], sr[sr["week"] == w]
        scope = f"In week {w}"
        if u.empty:
            return f"There is no data for week {w} (data covers weeks 1–12)."
    else:
        scope = "Across all 12 weeks"

    if any(k in ql for k in ["fix", "action", "change made", "what changed", "corrective"]):
        lines = [f"- **Week {r.week}** – {r.title} (owner: {r.owner})" for r in fixes.itertuples()]
        return "Corrective actions on record:\n" + "\n".join(lines)
    if "line" in ql and any(k in ql for k in ["worst", "lowest", "bad", "which"]):
        t = yield_by(u, "line").sort_values("yield")
        w, b = t.iloc[0], t.iloc[-1]
        return (f"{scope}, **{w['line']}** has the lowest final yield at **{w['yield']:.1%}** "
                f"({(b['yield'] - w['yield']) * 100:.1f} pts below {b['line']}). "
                "Check *AI Insights → Root-cause hints* for the driver.")
    if any(k in ql for k in ["lot", "supplier"]):
        kb = u.groupby("kb_lot").agg(n=("serial", "size"),
                                     kb_fail=("fail_station", lambda s: (s == "Keyboard / Trackpad").mean()))
        kb = kb[kb["n"] >= 30].sort_values("kb_fail", ascending=False)
        top = kb.index[0]
        med = kb["kb_fail"].median()
        return (f"{scope}, keyboard lot **{top}** is worst: **{kb.iloc[0]['kb_fail']:.1%}** of its units fail at "
                f"Keyboard/Trackpad vs a median of {med:.1%} for other lots "
                f"({kb.iloc[0]['kb_fail'] / max(med, 1e-9):.1f}×).")
    if any(k in ql for k in ["shift", "night", "day"]):
        t = yield_by(u, "shift").set_index("shift")["yield"]
        cos = sr[sr["station"] == "Cosmetic Inspection"].groupby("shift")["result"].apply(lambda s: (s == "FAIL").mean())
        return (f"{scope}, day shift yield is **{t.get('Day', np.nan):.1%}** vs night **{t.get('Night', np.nan):.1%}**. "
                f"Cosmetic-inspection fail rate: day {cos.get('Day', np.nan):.1%}, night {cos.get('Night', np.nan):.1%}.")
    if any(k in ql for k in ["defect", "pareto", "failure mode", "top fail", "most common"]):
        p = pareto(sr)
        if p.empty:
            return f"{scope}, no failures were recorded."
        top3 = ", ".join(f"{r.defect_code} ({r.pct:.0%})" for r in p.head(3).itertuples())
        return f"{scope}, the top defect is **{p.iloc[0]['defect_code']}** at {p.iloc[0]['station']}. Top 3: {top3}."
    if any(k in ql for k in ["cpk", "capab", "parameter", "spc", "torque", "temp", "cure"]):
        parts = []
        for col, s in SPECS.items():
            c, _ = cpk(u[col].to_numpy(), s["lsl"], s["usl"])
            parts.append((c, s["label"]))
        parts.sort()
        txt = "; ".join(f"{lbl}: Cpk {c:.2f}" for c, lbl in parts)
        return f"{scope}, the least capable parameter is **{parts[0][1]}** (Cpk {parts[0][0]:.2f}; target ≥ 1.33). All: {txt}."
    if any(k in ql for k in ["yield", "trend", "improve", "progress", "rty", "fpy"]):
        t = weekly_trend(data["units"], data["sr"])
        first, last = t.iloc[0], t.iloc[-1]
        return (f"Final yield went from **{first['final_yield']:.0%}** in week 1 to **{last['final_yield']:.0%}** in week 12 "
                f"(FPY {first['fpy']:.0%} → {last['fpy']:.0%}; RTY {first['rty']:.0%} → {last['rty']:.0%}). "
                "The biggest step-ups follow the week 5, 7 and 9 corrective actions.")
    return ("I can answer questions about: worst line, top defect, worst supplier lot, day vs night shift, "
            "yield trend, parameter capability (Cpk) and fixes made. Add 'week N' to scope a question.")
