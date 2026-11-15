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

import i18n

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
# KPI definitions (shown under each KPI card; kept here so code and UI agree)
KPI_DEFS = {
    "final_yield": ("Units passing all 6 stations (retests allowed) ÷ units started",
                    "通过全部 6 个工站（允许复测）的数量 ÷ 投入数量"),
    "fpy": ("Units passing all 6 stations on the first attempt, no retest ÷ units started",
            "6 个工站全部一次通过、无复测的数量 ÷ 投入数量"),
    "rty": ("Product of the 6 station first-pass yields. Usually slightly below unit-level FPY, because defects tend to cluster on the same units.",
            "6 个工站首次通过率的乘积。通常略低于整机 FPY，因为缺陷往往集中在同一批产品上。"),
    "dppm": ("Failed first-pass station tests ÷ all station tests × 1,000,000",
             "首次测试失败的工站测试数 ÷ 全部工站测试数 × 1,000,000"),
    "retest_rate": ("Station tests that failed first, then passed on retest ÷ all station tests",
                    "首次失败、复测后通过的工站测试数 ÷ 全部工站测试数"),
    "units": ("Units started in the week", "本周投入数量"),
}


def kpis(units: pd.DataFrame, sr: pd.DataFrame) -> dict[str, float]:
    """Yield KPIs for whatever slice of data is passed in (see KPI_DEFS).

    Identities that hold by construction (checked in `kpi_consistency`):
      DPPM / 1e6 = 1 − pooled station first-pass yield = retest rate + confirmed-fail rate
      RTY        = Π station first-pass yields  (same station FPYs as the Drill-down page)
    """
    n = len(units)
    if n == 0:
        return dict(final_yield=np.nan, fpy=np.nan, rty=np.nan, dppm=np.nan, retest_rate=np.nan,
                    confirmed_fail_rate=np.nan, units=0)
    station_fpy = sr.groupby("station")["first_pass"].mean()
    rty = float(station_fpy.prod()) if len(station_fpy) else np.nan
    fp_fail = ~sr["first_pass"]
    passed = sr["result"] == "PASS"
    return dict(
        final_yield=(units["final_result"] == "PASS").mean(),
        fpy=units["first_pass_all"].mean(),
        rty=rty,
        dppm=fp_fail.mean() * 1e6,
        retest_rate=(fp_fail & passed).mean(),
        confirmed_fail_rate=(~passed).mean(),
        units=n,
    )


def kpi_consistency(units: pd.DataFrame, sr: pd.DataFrame, tol: float = 1e-9) -> list[str]:
    """Return a list of violated KPI relationships for every week (empty list = consistent)."""
    problems = []
    for w in sorted(units["week"].unique()):
        u, s = units[units["week"] == w], sr[sr["week"] == w]
        k = kpis(u, s)
        st_fpy = s.groupby("station")["first_pass"].mean()
        pooled = (s.groupby("station").size() * st_fpy).sum() / len(s)
        checks = {
            "RTY = product of station FPYs": abs(k["rty"] - st_fpy.prod()) < tol,
            "FPY >= RTY (defects cluster on same units)": k["fpy"] >= k["rty"],
            "FPY <= final yield": k["fpy"] <= k["final_yield"] + tol,
            "RTY <= worst station FPY": k["rty"] <= st_fpy.min() + tol,
            "DPPM = (1 - pooled station FPY) x 1e6": abs(k["dppm"] - (1 - pooled) * 1e6) < 1e-3,
            "DPPM = (retest rate + confirmed-fail rate) x 1e6":
                abs(k["dppm"] - (k["retest_rate"] + k["confirmed_fail_rate"]) * 1e6) < 1e-3,
            "1 - RTY <= sum of station fail rates": 1 - k["rty"] <= (1 - st_fpy).sum() + tol,
            "retest rate <= DPPM / 1e6": k["retest_rate"] <= k["dppm"] / 1e6 + tol,
        }
        problems += [f"Week {w}: {name}" for name, ok in checks.items() if not ok]
    return problems


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
def _z_two_prop(pass1: float, n1: int, pass0: float, n0: int) -> tuple[float, float, float]:
    """Two-proportion z-test (pooled SE) of group pass rate vs its reference group.

    Uses the uncertainty of *both* groups, so a small reference group can't make a
    routine difference look like a many-sigma event."""
    y, p0 = pass1 / n1, pass0 / n0
    pp = (pass1 + pass0) / (n1 + n0)
    se = np.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n0))
    return y, p0, ((y - p0) / se if se > 0 else 0.0)


# station -> (action EN, action ZH, owner EN, owner ZH, timeframe EN, timeframe ZH); {w}/{wz} = where
ACTIONS = {
    "Display Attach": ("Audit {w} adhesive cure oven temperature control", "核查{wz}胶水固化烤炉的温度控制",
                       "Process Engineer", "工艺工程师", "24h", "24 小时"),
    "Keyboard / Trackpad": ("Check keyboard lot mix on {w}; hold suspect lots", "核对{wz}使用的键盘批次；扣留可疑批次",
                            "SQE", "SQE", "24h", "24 小时"),
    "Cosmetic Inspection": ("Retrain {w} operators on cosmetic handling & inspection standard",
                            "对{wz}操作员进行外观搬运与检验标准再培训", "Line Supervisor", "产线主管", "1 week", "1 周"),
    "SMT / Board Test": ("Review SMT reflow profile and stencil on {w}", "检查{wz}的 SMT 回流曲线和钢网",
                         "Process Engineer", "工艺工程师", "48h", "48 小时"),
    "Enclosure Assembly": ("Calibrate screwdriver torque on {w}", "校准{wz}的电批扭矩",
                           "Equipment Engineer", "设备工程师", "48h", "48 小时"),
    "Functional Test": ("Check test fixtures and station calibration on {w}", "检查{wz}的测试治具与工站校准",
                        "Test Engineer", "测试工程师", "48h", "48 小时"),
}
LOT_ACTION = ("Quarantine lot {lot} and request supplier 8D", "隔离批次 {lot}，并要求供应商提交 8D",
              "SQE", "SQE", "24h", "24 小时")


def _driver_station(group: pd.DataFrame, ref: pd.DataFrame) -> str:
    """Station whose failure rate is most elevated in `group` vs `ref`."""
    g = group["fail_station"].value_counts() / len(group)
    r = ref["fail_station"].value_counts() / max(len(ref), 1)
    excess = {st: g.get(st, 0) - r.get(st, 0) for st in STATIONS}
    return max(excess, key=excess.get)


def _action(kind: str, station: str, where_en: str, where_zh: str, lot: str = "") -> dict:
    if kind == "Supplier lot":
        a = LOT_ACTION
        return dict(driver_station=station, action_en=a[0].format(lot=lot), action_zh=a[1].format(lot=lot),
                    owner_en=a[2], owner_zh=a[3], timeframe_en=a[4], timeframe_zh=a[5])
    a = ACTIONS[station]
    return dict(driver_station=station, action_en=a[0].format(w=where_en), action_zh=a[1].format(wz=where_zh),
                owner_en=a[2], owner_zh=a[3], timeframe_en=a[4], timeframe_zh=a[5])


def detect_anomalies(units: pd.DataFrame, z_thresh: float = 3.0, min_units: int = 15) -> pd.DataFrame:
    """Flag line-days, line-weeks, shift-weeks and keyboard lots whose yield is significantly
    below their peers built in the same week (two-proportion z-test).

    Comparing against same-week peers means the normal ramp-up improvement isn't flagged.
    Each anomaly gets a rule-based suggested action, owner role and timeframe, chosen from
    the station whose failures are most elevated in that group.
    """
    out = []
    passed = units["final_result"] == "PASS"
    u = units.assign(_pass=passed)

    def add(kind, entity, week, grp, ref, line="", date=pd.NaT, where=("", ""), lot=""):
        y, p0, z = _z_two_prop(grp["_pass"].sum(), len(grp), ref["_pass"].sum(), len(ref))
        if z < -z_thresh:
            st = "Keyboard / Trackpad" if kind == "Supplier lot" else _driver_station(grp, ref)
            out.append(dict(kind=kind, entity=entity, week=int(week), units=len(grp), yield_=y, expected=p0, z=z,
                            line=line, date=date, **_action(kind, st, where[0], where[1], lot)))

    def line_where(line):
        return line, f"{line.split()[-1]}号线"

    for (date, week, line), g in u.groupby(["date", "week", "line"]):
        if len(g) < min_units:
            continue
        ref = u[(u["week"] == week) & (u["line"] != line)]
        add("Line-day", f"{line} · {date:%a %b %d}", week, g, ref, line, date, line_where(line))
    for (week, line), g in u.groupby(["week", "line"]):
        ref = u[(u["week"] == week) & (u["line"] != line)]
        add("Line-week", f"{line} · Week {week}", week, g, ref, line, pd.NaT, line_where(line))
    for (week, sh), g in u.groupby(["week", "shift"]):
        ref = u[(u["week"] == week) & (u["shift"] != sh)]
        add("Shift-week", f"{sh} shift · Week {week}", week, g, ref,
            where=(f"{sh.lower()}-shift", "夜班" if sh == "Night" else "白班"))
    # keyboard lots: keyboard-station pass rate vs other lots built in the same weeks
    for lot, g in u.groupby("kb_lot"):
        if len(g) < min_units:
            continue
        weeks = g["week"].unique()
        ref = u[u["week"].isin(weeks) & (u["kb_lot"] != lot)]
        gk = g.assign(_pass=g["fail_station"] != "Keyboard / Trackpad")
        rk = ref.assign(_pass=ref["fail_station"] != "Keyboard / Trackpad")
        add("Supplier lot", f"{lot} (keyboard station)", weeks.min(), gk, rk, lot=lot)
    df = pd.DataFrame(out)
    if df.empty:
        return df
    return df.sort_values("z").reset_index(drop=True)


def format_sigma(z: float, cap: float = 10.0) -> str:
    """Display helper: |z| beyond `cap` is shown as '>10σ' (exact value kept in the data)."""
    return f">{cap:g}σ" if abs(z) > cap else f"{abs(z):.1f}σ"


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
    context_zh: str = ""

    def text(self, lang: str = "en") -> str:
        return self.sentence_zh if lang == "zh" else self.sentence

    @property
    def sentence_zh(self) -> str:
        ctx = f"{self.context_zh}" if self.context_zh else ""
        return (f"**{i18n.station(self.station, 'zh')}** 失效（{self.defect_code}）在 **{i18n.text(self.condition, 'zh')}** "
                f"条件下**高出 {self.risk_ratio:.1f} 倍**{ctx} —— {self.rate_in:.1%} 对比 {self.rate_out:.1%}；"
                f"该条件解释了此类失效的 {self.share_of_failures:.0%}。")

    @property
    def sentence(self) -> str:
        ctx = f" {self.context}" if self.context else ""
        return (f"**{self.station}** failures ({self.defect_code}) are **{self.risk_ratio:.1f}× more likely** "
                f"when **{self.condition}**{ctx} — {self.rate_in:.1%} vs {self.rate_out:.1%} of units; "
                f"this condition accounts for {self.share_of_failures:.0%} of those failures.")


def _cmh_pvalue(y: np.ndarray, mask: np.ndarray, strata: np.ndarray) -> float:
    """Cochran-Mantel-Haenszel test of y vs mask, stratified (here: by build week)."""
    num, var = 0.0, 0.0
    for s in np.unique(strata):
        k = strata == s
        n = k.sum()
        n1, c1 = mask[k].sum(), y[k].sum()
        if n < 2 or n1 in (0, n) or c1 in (0, n):
            continue
        a = y[k & mask].sum()
        num += a - n1 * c1 / n
        var += n1 * (n - n1) * c1 * (n - c1) / (n ** 2 * (n - 1))
    if var <= 0:
        return 1.0
    chi2 = (abs(num) - 0.5) ** 2 / var
    return float(stats.chi2.sf(chi2, 1))


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
        pval = _cmh_pvalue(y, mask, d["week"].to_numpy())  # week-stratified, like the risk ratio
        # Where do the at-risk units concentrate? (line / shift / supplier)
        ctx_parts, ctx_zh = [], []
        sub = d[mask]
        zh_fmt = {"line": lambda v: f"（集中在 {i18n.line(v, 'zh')}）", "shift": lambda v: f"（集中在{i18n.shift(v, 'zh')}）",
                  "kb_supplier": lambda v: f"（来自 {v}）"}
        for col, fmt in (("line", "on {}"), ("shift", "on {} shift"), ("kb_supplier", "from {}")):
            if feat.startswith(col) or (col == "shift" and feat == "is_night"):
                continue
            share = sub[col].value_counts(normalize=True)
            base = d[col].value_counts(normalize=True)
            top = share.index[0]
            if share.iloc[0] >= 0.7 and share.iloc[0] > base.get(top, 0) + 0.2:
                ctx_parts.append(fmt.format(top))
                ctx_zh.append(zh_fmt[col](top))
        wk = sub.loc[sub["defect_code"] == code, "week"]
        w_lo, w_hi = int(wk.quantile(.05)), int(wk.quantile(.95))
        ctx_parts.append(f"(failures concentrated in weeks {w_lo}–{w_hi})")
        ctx_zh.append(f"（失效集中在第 {w_lo}–{w_hi} 周）")
        if pval > 1e-6:
            continue  # many splits are searched - demand strong evidence
        hints.append(Hint(station, code, cond, rr, a / n_in, c / (~mask).sum(), n_in,
                          a / y.sum(), pval, " ".join(ctx_parts), "".join(ctx_zh)))
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
EXAMPLE_QUESTIONS = {
    "en": [
        "Which line has the lowest yield?",
        "What is the top defect?",
        "Which supplier lot is worst?",
        "Is night shift worse than day shift?",
        "How has yield changed?",
        "Which parameter is least capable?",
        "What fixes were made?",
    ],
    "zh": [
        "哪条产线良率最低？",
        "最主要的缺陷是什么？",
        "哪个供应商批次最差？",
        "夜班比白班差吗？",
        "良率趋势如何？",
        "哪个工艺参数能力最差？",
        "做了哪些改进措施？",
    ],
}


def _has(ql: str, *words) -> bool:
    return any(w in ql for w in words)


def answer_question(q: str, data: dict, lang: str = "en") -> str:
    """Keyword/intent matcher over the data (English or Chinese). No API key or network needed."""
    zh = lang == "zh"
    ql = q.lower()
    u, sr, fixes = data["units"], data["sr"], data["fixes"]
    wk = re.search(r"week\s*(\d+)|第\s*(\d+)\s*周|w(\d+)\b", ql)
    if wk:
        w = int(next(g for g in wk.groups() if g))
        u, sr = u[u["week"] == w], sr[sr["week"] == w]
        scope = f"第 {w} 周" if zh else f"In week {w}"
        if u.empty:
            return f"没有第 {w} 周的数据（数据覆盖第 1–12 周）。" if zh else f"There is no data for week {w} (data covers weeks 1–12)."
    else:
        scope = "12 周整体来看" if zh else "Across all 12 weeks"
    L = lambda en, cn: cn if zh else en

    if _has(ql, "fix", "action", "change made", "what changed", "corrective", "修复", "措施", "改进", "纠正"):
        if zh:
            lines = [f"- **第 {r.week} 周** – {i18n.FIX_TITLE_ZH.get(r.week, r.title)}（负责：{i18n.FIX_OWNER_ZH.get(r.week, r.owner)}）"
                     for r in fixes.itertuples()]
            return "已记录的纠正措施：\n" + "\n".join(lines)
        lines = [f"- **Week {r.week}** – {r.title} (owner: {r.owner})" for r in fixes.itertuples()]
        return "Corrective actions on record:\n" + "\n".join(lines)
    if (_has(ql, "line") and _has(ql, "worst", "lowest", "bad", "which")) or _has(ql, "产线", "哪条线", "线体"):
        t = yield_by(u, "line").sort_values("yield")
        w, b = t.iloc[0], t.iloc[-1]
        gap = (b["yield"] - w["yield"]) * 100
        return L(f"{scope}, **{w['line']}** has the lowest final yield at **{w['yield']:.1%}** "
                 f"({gap:.1f} pts below {b['line']}). Check *AI Insights → Root-cause hints* for the driver.",
                 f"{scope}，**{i18n.line(w['line'], 'zh')}** 的最终良率最低，为 **{w['yield']:.1%}**"
                 f"（比 {i18n.line(b['line'], 'zh')} 低 {gap:.1f} 个百分点）。原因见 *AI 洞察 → 根因提示*。")
    if _has(ql, "lot", "supplier", "批次", "供应商"):
        kb = u.groupby("kb_lot").agg(n=("serial", "size"),
                                     kb_fail=("fail_station", lambda s: (s == "Keyboard / Trackpad").mean()))
        kb = kb[kb["n"] >= 30].sort_values("kb_fail", ascending=False)
        if kb.empty:
            return L("Not enough units per lot in this scope.", "该范围内各批次数量不足。")
        top, med = kb.index[0], kb["kb_fail"].median()
        r = kb.iloc[0]["kb_fail"] / max(med, 1e-9)
        return L(f"{scope}, keyboard lot **{top}** is worst: **{kb.iloc[0]['kb_fail']:.1%}** of its units fail at "
                 f"Keyboard/Trackpad vs a median of {med:.1%} for other lots ({r:.1f}×).",
                 f"{scope}，键盘批次 **{top}** 最差：**{kb.iloc[0]['kb_fail']:.1%}** 的产品在键盘/触控板工站失效，"
                 f"其他批次中位数为 {med:.1%}（{r:.1f} 倍）。")
    if _has(ql, "shift", "night", "day", "班"):
        t = yield_by(u, "shift").set_index("shift")["yield"]
        cos = sr[sr["station"] == "Cosmetic Inspection"].groupby("shift")["result"].apply(lambda s: (s == "FAIL").mean())
        return L(f"{scope}, day shift yield is **{t.get('Day', np.nan):.1%}** vs night **{t.get('Night', np.nan):.1%}**. "
                 f"Cosmetic-inspection fail rate: day {cos.get('Day', np.nan):.1%}, night {cos.get('Night', np.nan):.1%}.",
                 f"{scope}，白班良率 **{t.get('Day', np.nan):.1%}**，夜班 **{t.get('Night', np.nan):.1%}**。"
                 f"外观检验失效率：白班 {cos.get('Day', np.nan):.1%}，夜班 {cos.get('Night', np.nan):.1%}。")
    if _has(ql, "defect", "pareto", "failure mode", "top fail", "most common", "缺陷", "不良", "失效模式", "柏拉图"):
        p = pareto(sr)
        if p.empty:
            return L(f"{scope}, no failures were recorded.", f"{scope}没有记录到失效。")
        top3 = ", ".join(f"{r.defect_code} ({r.pct:.0%})" for r in p.head(3).itertuples())
        return L(f"{scope}, the top defect is **{p.iloc[0]['defect_code']}** at {p.iloc[0]['station']}. Top 3: {top3}.",
                 f"{scope}，最主要的缺陷是 **{p.iloc[0]['defect_code']}**（{i18n.station(p.iloc[0]['station'], 'zh')}）。"
                 f"前三名：{top3}。")
    if _has(ql, "cpk", "capab", "parameter", "spc", "torque", "temp", "cure", "能力", "参数", "扭矩", "温度", "固化"):
        parts = []
        for col, s in SPECS.items():
            c, _ = cpk(u[col].to_numpy(), s["lsl"], s["usl"])
            parts.append((c, i18n.SPEC_LABEL_ZH[col] if zh else s["label"]))
        parts.sort()
        txt = ("；" if zh else "; ").join(f"{lbl}: Cpk {c:.2f}" for c, lbl in parts)
        return L(f"{scope}, the least capable parameter is **{parts[0][1]}** (Cpk {parts[0][0]:.2f}; target ≥ 1.33). All: {txt}.",
                 f"{scope}，能力最差的参数是 **{parts[0][1]}**（Cpk {parts[0][0]:.2f}；目标 ≥ 1.33）。全部：{txt}。")
    if _has(ql, "yield", "trend", "improve", "progress", "rty", "fpy", "良率", "趋势", "提升", "进展"):
        t = weekly_trend(data["units"], data["sr"])
        f, l = t.iloc[0], t.iloc[-1]
        return L(f"Final yield went from **{f['final_yield']:.0%}** in week 1 to **{l['final_yield']:.0%}** in week 12 "
                 f"(FPY {f['fpy']:.0%} → {l['fpy']:.0%}; RTY {f['rty']:.0%} → {l['rty']:.0%}). "
                 "The biggest step-ups follow the week 5, 7 and 9 corrective actions.",
                 f"最终良率从第 1 周的 **{f['final_yield']:.0%}** 提升到第 12 周的 **{l['final_yield']:.0%}**"
                 f"（FPY {f['fpy']:.0%} → {l['fpy']:.0%}；RTY {f['rty']:.0%} → {l['rty']:.0%}）。"
                 "最大的跃升紧跟在第 5、7、9 周的纠正措施之后。")
    return L("I can answer questions about: worst line, top defect, worst supplier lot, day vs night shift, "
             "yield trend, parameter capability (Cpk) and fixes made. Add 'week N' to scope a question.",
             "我可以回答：最差产线、主要缺陷、最差供应商批次、白班 vs 夜班、良率趋势、参数能力（Cpk）、"
             "已做的改进措施。加上“第 N 周”可以限定范围。")
