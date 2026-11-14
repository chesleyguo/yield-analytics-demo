"""Product X Yield Analytics - interactive demo dashboard.

SIMULATED DATA - FOR DEMONSTRATION ONLY.  Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analytics as A

st.set_page_config(page_title="Product X Yield Analytics", page_icon="📈", layout="wide")

# --------------------------------------------------------------------------- style
PASS, FAIL = "#1baf7a", "#e34948"
BEFORE, AFTER = "#a3a29c", "#2a78d6"
TARGET = "#52514e"
LINE_COLORS = {"Line 1": "#2a78d6", "Line 2": "#eb6834", "Line 3": "#6250d6"}
SHIFT_COLORS = {"Day": "#eda100", "Night": "#6250d6"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
PHASE_FILL = {"EVT": "rgba(42,120,214,0.05)", "DVT": "rgba(42,120,214,0.10)",
              "PVT": "rgba(42,120,214,0.05)", "Ramp": "rgba(42,120,214,0.10)"}

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1400px;}
  h1 {font-size: 2.1rem !important; margin-bottom: 0 !important;}
  h2 {font-size: 1.55rem !important;}
  h3 {font-size: 1.25rem !important;}
  .sim-banner {background:#fff4e0; border:1px solid #f0c36d; color:#5c4100; padding:6px 14px;
               border-radius:8px; font-size:0.95rem; display:inline-block; margin:4px 0 10px 0;}
  .takeaway {border-left:4px solid #2a78d6; background:#f2f6fc; padding:8px 14px; border-radius:4px;
             font-size:1.05rem; margin:2px 0 18px 0; color:#1b1b1b;}
  .kpi {background:#ffffff; border:1px solid #e4e2dc; border-radius:12px; padding:14px 16px;}
  .kpi .lbl {font-size:0.92rem; color:#52514e; margin-bottom:2px;}
  .kpi .val {font-size:2.0rem; font-weight:650; color:#0b0b0b; line-height:1.15;}
  .kpi .dlt {font-size:0.95rem; margin-top:2px;}
  .good {color:#0e7a52;} .bad {color:#c22f2e;} .flat {color:#6b6a65;}
  .hint {background:#ffffff; border:1px solid #e4e2dc; border-left:5px solid #eb6834; border-radius:8px;
         padding:12px 16px; margin-bottom:10px; font-size:1.08rem;}
  .card {background:#ffffff; border:1px solid #e4e2dc; border-radius:12px; padding:14px 18px; height:100%;}
  .card h4 {margin:0 0 6px 0; font-size:1.1rem;}
  [data-testid="stSidebarNav"] span {font-size:1.05rem;}
</style>
""", unsafe_allow_html=True)


def banner():
    st.markdown('<div class="sim-banner">⚠️ <b>Simulated data – for demonstration only.</b> '
                'Generic “Product X”; not based on any real company, product or process.</div>',
                unsafe_allow_html=True)


def takeaway(text: str):
    st.markdown(f'<div class="takeaway">💡 {text}</div>', unsafe_allow_html=True)


def md_html(text: str) -> str:
    """Convert **bold** / *italic* / newlines-with-bullets markdown to HTML for use inside styled divs."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text.replace("\n- ", "<br>• ").replace("\n", "<br>")


def style_fig(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=10, r=10, t=30, b=10),
        font=dict(size=15, color="#1b1b1b"), hoverlabel=dict(font_size=14),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=14)),
        showlegend=legend, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
    )
    fig.update_xaxes(showgrid=False, linecolor="#c9c7c0", tickfont=dict(size=14))
    fig.update_yaxes(gridcolor="#eceae5", zeroline=False, tickfont=dict(size=14))
    return fig


def show(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def pct(x, d=1):
    return "–" if pd.isna(x) else f"{x * 100:.{d}f}%"


# --------------------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading simulated data…")
def get_data():
    if not (A.DATA_DIR / "station_results.csv").exists():
        import generate_data
        generate_data.main(str(A.DATA_DIR))
    return A.load_data()


@st.cache_data
def get_trend():
    d = get_data()
    return A.weekly_trend(d["units"], d["sr"])


@st.cache_data
def get_hints(w0: int, w1: int):
    d = get_data()
    sr = d["sr"][d["sr"]["week"].between(w0, w1)]
    return A.root_cause_hints(sr)


@st.cache_data
def get_factors(w0: int, w1: int):
    d = get_data()
    return A.factor_association(d["units"][d["units"]["week"].between(w0, w1)])


@st.cache_data
def get_anomalies(z: float):
    return A.detect_anomalies(get_data()["units"], z_thresh=z)


@st.cache_data
def get_subgroups(param: str):
    return A.spc_subgroups(get_data()["units"], param)


DATA = get_data()
UNITS, SR, FIXES, DOE = DATA["units"], DATA["sr"], DATA["fixes"], DATA["doe"]
WEEKS = sorted(UNITS["week"].unique())
PHASE_OF = UNITS.groupby("week")["phase"].first().to_dict()


def add_phase_bands(fig, x_is_week=True, y_top=1.0):
    for ph in ["EVT", "DVT", "PVT", "Ramp"]:
        ws = [w for w, p in PHASE_OF.items() if p == ph]
        fig.add_vrect(x0=min(ws) - 0.5, x1=max(ws) + 0.5, fillcolor=PHASE_FILL[ph], line_width=0, layer="below",
                      annotation_text=ph, annotation_position="top left",
                      annotation=dict(font=dict(size=13, color="#52514e")))


def add_fix_lines(fig, x_of_week=lambda w: w - 0.5, label=True):
    for r in FIXES.itertuples():
        fig.add_vline(x=x_of_week(r.week), line=dict(color="#0b0b0b", width=1.5, dash="dot"))
        if label:
            fig.add_annotation(x=x_of_week(r.week), y=0.02, yref="paper", text=f"<b>Fix:</b> {r.short}",
                               showarrow=False, xanchor="left", xshift=4, font=dict(size=13, color="#0b0b0b"),
                               bgcolor="rgba(255,255,255,0.85)")


# =========================================================================== pages
def page_overview():
    st.title("Product X — Yield Ramp Overview")
    banner()
    trend = get_trend()
    c0, _ = st.columns([1, 3])
    wk = c0.select_slider("Week shown in KPI cards", options=WEEKS, value=WEEKS[-1],
                          format_func=lambda w: f"Week {w} ({PHASE_OF[w]})")
    cur = trend.set_index("week").loc[wk]
    prev = trend.set_index("week").loc[wk - 1] if wk > 1 else None

    specs = [("Final yield", "final_yield", "pct", True), ("First-pass yield (FPY)", "fpy", "pct", True),
             ("Rolled throughput yield (RTY)", "rty", "pct", True), ("DPPM (station fails)", "dppm", "int", False),
             ("Retest rate", "retest_rate", "pct", False), ("Units built", "units", "int", None)]
    cols = st.columns(6)
    for col, (lbl, key, fmt, higher_good) in zip(cols, specs):
        v = cur[key]
        val = pct(v) if fmt == "pct" else f"{v:,.0f}"
        if prev is None:
            dl, cls = "first week", "flat"
        else:
            dv = v - prev[key]
            if fmt == "pct":
                dl = f"{'▲' if dv >= 0 else '▼'} {abs(dv) * 100:.1f} pts WoW"
            else:
                dl = f"{'▲' if dv >= 0 else '▼'} {abs(dv) / max(prev[key], 1) * 100:.0f}% WoW"
            cls = "flat" if higher_good is None or abs(dv) < 1e-9 else ("good" if (dv > 0) == higher_good else "bad")
        col.markdown(f'<div class="kpi"><div class="lbl">{lbl}</div><div class="val">{val}</div>'
                     f'<div class="dlt {cls}">{dl}</div></div>', unsafe_allow_html=True)
    st.write("")

    st.subheader("Weekly yield trend with corrective actions")
    fig = go.Figure()
    add_phase_bands(fig)
    fig.add_hline(y=0.90, line=dict(color=TARGET, dash="dash", width=1),
                  annotation_text="90% target", annotation_position="bottom left")
    for key, name, color, width in [("final_yield", "Final yield (after rework/retest)", AFTER, 4),
                                    ("fpy", "First-pass yield", "#eb6834", 2.5)]:
        fig.add_trace(go.Scatter(x=trend["week"], y=trend[key], name=name, mode="lines+markers",
                                 line=dict(color=color, width=width), marker=dict(size=9),
                                 hovertemplate=f"{name}: %{{y:.1%}}<extra>Week %{{x}}</extra>"))
    add_fix_lines(fig)
    fig.add_annotation(x=trend["week"].iloc[0], y=trend["final_yield"].iloc[0], text=f"{pct(trend['final_yield'].iloc[0], 0)}",
                       showarrow=True, arrowhead=0, ax=-10, ay=-35, font=dict(size=15))
    fig.add_annotation(x=trend["week"].iloc[-1], y=trend["final_yield"].iloc[-1], text=f"{pct(trend['final_yield'].iloc[-1], 0)}",
                       showarrow=True, arrowhead=0, ax=0, ay=-35, font=dict(size=15))
    fig.update_yaxes(tickformat=".0%", range=[0, 1.04], title=None)
    fig.update_xaxes(tickmode="array", tickvals=WEEKS, ticktext=[f"W{w}" for w in WEEKS], title=None)
    show(style_fig(fig, 460))
    f, l = trend.iloc[0], trend.iloc[-1]
    gains = []
    for r in FIXES.itertuples():
        b = trend.set_index("week")["final_yield"]
        gains.append(f"{r.short} +{(b.get(r.week, np.nan) - b.get(r.week - 1, np.nan)) * 100:.0f} pts")
    takeaway(f"Final yield climbed from <b>{pct(f['final_yield'], 0)}</b> (W1) to <b>{pct(l['final_yield'], 0)}</b> (W12); "
             f"yield steps up right after each fix: {', '.join(gains)}.")

    st.subheader("Where yield is lost — failures per 100 units started, by station")
    loss = UNITS[UNITS["final_result"] == "FAIL"].groupby(["week", "fail_station"]).size().unstack(fill_value=0)
    loss = loss.div(UNITS.groupby("week").size(), axis=0).reindex(columns=A.STATIONS, fill_value=0) * 100
    fig = go.Figure()
    for i, stn in enumerate(A.STATIONS):
        fig.add_trace(go.Bar(x=loss.index, y=loss[stn], name=stn, marker_color=SERIES[i],
                             marker_line=dict(color="#ffffff", width=1.5),
                             hovertemplate=f"{stn}: %{{y:.1f}} per 100<extra>Week %{{x}}</extra>"))
    add_fix_lines(fig, label=False)
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(tickmode="array", tickvals=WEEKS, ticktext=[f"W{w}" for w in WEEKS])
    fig.update_yaxes(title="Failures per 100 units")
    show(style_fig(fig, 400))
    steps = []
    for r in FIXES.itertuples():
        st_ = r.affected_station
        before = loss.loc[max(1, r.week - 2):r.week - 1, st_].mean()
        after = loss.loc[r.week:r.week + 1, st_].mean()
        steps.append(f"{st_} {before:.0f} → {after:.0f} after W{r.week}")
    takeaway("Loss fell at every station as the process matured, but three stations show a <b>step change right after "
             f"a fix</b>: {'; '.join(steps)} (failures per 100 units).")


def page_drilldown():
    st.title("Drill-down — where is yield lost?")
    banner()
    c1, c2, c3, c4 = st.columns([2, 1.3, 1.1, 1.4])
    w0, w1 = c1.select_slider("Weeks", options=WEEKS, value=(WEEKS[0], WEEKS[-1]), format_func=lambda w: f"W{w}")
    lines = c2.multiselect("Lines", sorted(UNITS["line"].unique()), default=sorted(UNITS["line"].unique()))
    shifts = c3.multiselect("Shifts", ["Day", "Night"], default=["Day", "Night"])
    phases = c4.multiselect("Phases", ["EVT", "DVT", "PVT", "Ramp"], default=["EVT", "DVT", "PVT", "Ramp"])
    um = (UNITS["week"].between(w0, w1) & UNITS["line"].isin(lines) & UNITS["shift"].isin(shifts)
          & UNITS["phase"].isin(phases))
    sm = (SR["week"].between(w0, w1) & SR["line"].isin(lines) & SR["shift"].isin(shifts) & SR["phase"].isin(phases))
    u, s = UNITS[um], SR[sm]
    if u.empty:
        st.warning("No units match these filters.")
        return
    dim = st.radio("Break down by", ["Station", "Line", "Shift", "Supplier lot", "Phase"], horizontal=True)

    if dim == "Station":
        t = A.station_fpy(s)
        fig = go.Figure(go.Bar(x=t["station"].astype(str), y=t["fpy"], marker_color=AFTER,
                               text=[pct(v) for v in t["fpy"]], textposition="outside",
                               hovertemplate="%{x}<br>FPY %{y:.1%}<extra></extra>"))
        worst = t.loc[t["fpy"].idxmin()]
        fig.update_yaxes(tickformat=".0%", range=[max(0, t["fpy"].min() - 0.1), 1.02], title="First-pass yield")
        show(style_fig(fig, 420, legend=False))
        takeaway(f"<b>{worst['station']}</b> has the lowest first-pass yield ({pct(worst['fpy'])}) in this slice; "
                 f"RTY across all six stations is {pct(t['fpy'].prod())}.")
        st.subheader("Station FPY by week")
        hm = A.station_fpy(s, by="week").pivot(index="station", columns="week", values="fpy")
        fig = go.Figure(go.Heatmap(z=hm.values, x=[f"W{w}" for w in hm.columns], y=hm.index.astype(str),
                                   colorscale=[[0, "#e34948"], [0.5, "#f7f6f2"], [1, "#2a78d6"]], zmin=0.7, zmax=1.0,
                                   text=[[pct(v, 0) for v in row] for row in hm.values], texttemplate="%{text}",
                                   textfont=dict(size=13), colorbar=dict(tickformat=".0%"),
                                   hovertemplate="%{y} · %{x}<br>FPY %{z:.1%}<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        show(style_fig(fig, 360, legend=False))
        takeaway("Red cells mark station-weeks below ~85% FPY — watch Display Attach turn red in W3–W4 and recover after W5.")

    elif dim in ("Line", "Shift"):
        col = dim.lower()
        colors = LINE_COLORS if col == "line" else SHIFT_COLORS
        wk = u.groupby(["week", col])["final_result"].apply(lambda x: (x == "PASS").mean()).unstack()
        fig = go.Figure()
        add_phase_bands(fig)
        for k in wk.columns:
            fig.add_trace(go.Scatter(x=wk.index, y=wk[k], name=k, mode="lines+markers",
                                     line=dict(color=colors[k], width=3), marker=dict(size=8),
                                     hovertemplate=f"{k}: %{{y:.1%}}<extra>Week %{{x}}</extra>"))
        add_fix_lines(fig)
        fig.update_yaxes(tickformat=".0%", title="Final yield")
        fig.update_xaxes(tickmode="array", tickvals=WEEKS, ticktext=[f"W{w}" for w in WEEKS])
        show(style_fig(fig, 440))
        gap = (wk.max(axis=1) - wk.min(axis=1))
        gw = gap.idxmax()
        lo = wk.loc[gw].idxmin()
        takeaway(f"The widest gap is in <b>week {gw}</b>: {lo} trails by <b>{gap.max() * 100:.0f} pts</b>"
                 + (" — the Line 2 cure-oven drift." if col == "line" else " — night-shift cosmetic losses until the W9 retraining."))
        st.subheader(f"Station first-pass yield by {col}")
        t = A.station_fpy(s, by=col)
        fig = go.Figure()
        for k in sorted(t[col].unique()):
            tt = t[t[col] == k]
            fig.add_trace(go.Bar(x=tt["station"].astype(str), y=tt["fpy"], name=k, marker_color=colors[k],
                                 hovertemplate=f"{k}<br>%{{x}}: %{{y:.1%}}<extra></extra>"))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05)
        fig.update_yaxes(tickformat=".0%", range=[0.75, 1.0])
        show(style_fig(fig, 380))
        diff = t.pivot(index="station", columns=col, values="fpy")
        spread = (diff.max(axis=1) - diff.min(axis=1))
        st_w = spread.idxmax()
        takeaway(f"The {col}s differ most at <b>{st_w}</b> ({spread.max() * 100:.1f} pts FPY spread); "
                 "other stations are nearly identical — the problem is local, not systemic.")

    elif dim == "Supplier lot":
        kb = s[s["station"] == "Keyboard / Trackpad"]
        t = kb.groupby(["kb_lot", "kb_supplier"]).agg(tested=("serial", "size"),
                                                      fail=("result", lambda x: (x == "FAIL").mean())).reset_index()
        t = t[t["tested"] >= 20].sort_values("fail", ascending=False)
        med = t["fail"].median()
        colors = [FAIL if v > 3 * med else ("#eb6834" if r == "Supplier B" else AFTER)
                  for v, r in zip(t["fail"], t["kb_supplier"])]
        fig = go.Figure(go.Bar(x=t["kb_lot"], y=t["fail"], marker_color=colors,
                               customdata=np.stack([t["tested"], t["kb_supplier"]], axis=1),
                               hovertemplate="%{x} (%{customdata[1]})<br>Keyboard-station fail rate %{y:.1%}"
                                             "<br>%{customdata[0]} units<extra></extra>"))
        fig.add_hline(y=med, line=dict(dash="dash", color=TARGET), annotation_text=f"median {pct(med)}")
        fig.update_yaxes(tickformat=".0%", title="Keyboard/Trackpad fail rate")
        fig.update_xaxes(tickangle=-45)
        show(style_fig(fig, 440, legend=False))
        st.caption("Red = > 3× median lot fail rate · orange = Supplier B · blue = Supplier A")
        top = t.iloc[0]
        takeaway(f"Keyboard lot <b>{top['kb_lot']}</b> fails at <b>{pct(top['fail'])}</b> — "
                 f"{top['fail'] / med:.0f}× the median lot. Every other lot from the same supplier is normal, "
                 "so this is a lot-specific escape, not a supplier-wide problem.")

    else:  # Phase
        t = A.yield_by(u, "phase").set_index("phase").reindex(["EVT", "DVT", "PVT", "Ramp"]).dropna().reset_index()
        fig = go.Figure(go.Bar(x=t["phase"], y=t["yield"], marker_color=AFTER, text=[pct(v) for v in t["yield"]],
                               textposition="outside", hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
        fig.add_hline(y=0.9, line=dict(dash="dash", color=TARGET), annotation_text="90% target")
        fig.update_yaxes(tickformat=".0%", range=[0, 1.05], title="Final yield")
        show(style_fig(fig, 400, legend=False))
        takeaway(f"Yield rose every build phase — {' → '.join(pct(v, 0) for v in t['yield'])} — "
                 "and only the Ramp phase clears the 90% target.")


def page_pareto():
    st.title("Defect Pareto — what fails most?")
    banner()
    c1, c2, _ = st.columns([1.3, 2, 1])
    mode = c1.radio("View", ["Single period", "Before vs after fixes"], horizontal=False)
    stations = c2.multiselect("Stations", A.STATIONS, default=A.STATIONS)

    def pareto_fig(s, height=440):
        p = A.pareto(s[s["station"].isin(stations)]).head(12)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=p["defect_code"], y=p["pct"], name="% of failures", marker_color=FAIL,
                             customdata=np.stack([p["count"], p["station"]], axis=1),
                             hovertemplate="%{x}<br>%{customdata[1]}<br>%{customdata[0]} failures (%{y:.1%})<extra></extra>"))
        fig.add_trace(go.Scatter(x=p["defect_code"], y=p["cum_pct"], name="Cumulative %", mode="lines+markers",
                                 line=dict(color="#0b0b0b", width=2), marker=dict(size=8),
                                 hovertemplate="Cumulative %{y:.0%}<extra></extra>"))
        fig.add_hline(y=0.8, line=dict(dash="dash", color=TARGET), annotation_text="80%")
        fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
        fig.update_xaxes(tickangle=-35)
        return style_fig(fig, height), p

    if mode == "Single period":
        w0, w1 = st.select_slider("Weeks (default: W3–W6, when all three issues were active)", options=WEEKS,
                                  value=(3, 6), format_func=lambda w: f"W{w}")
        s = SR[SR["week"].between(w0, w1)]
        fig, p = pareto_fig(s)
        show(fig)
        if p.empty:
            return
        n80 = int((p["cum_pct"] < 0.8).sum() + 1)
        allp = A.pareto(s[s["station"].isin(stations)])
        takeaway(f"<b>{n80}</b> of {len(allp)} defect codes make up 80% of failures; the top three — "
                 f"{', '.join(p['defect_code'].head(3))} — account for <b>{pct(p['cum_pct'].iloc[min(2, len(p) - 1)], 0)}</b>. "
                 "Start with the codes that point at a specific cause (lot, shift, parameter), then the broad ones.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Before: weeks 1–4")
            fb, pb = pareto_fig(SR[SR["week"].between(1, 4)], 420)
            show(fb)
        with c2:
            st.subheader("After: weeks 10–12")
            fa, pa = pareto_fig(SR[SR["week"].between(10, 12)], 420)
            show(fa)
        rate = lambda s: (s["result"] == "FAIL").sum() / s["serial"].nunique() * 100
        b, a = rate(SR[SR["week"].between(1, 4)]), rate(SR[SR["week"].between(10, 12)])
        takeaway(f"Failures fell from <b>{b:.0f}</b> to <b>{a:.0f}</b> per 100 units. The targeted codes "
                 "(DSP-ADHESIVE-DELAM, KB-KEY-STICK, COS-SCRATCH) dropped out of the top of the Pareto — "
                 "what's left is a flatter, 'normal' mix of residual defects.")


def page_spc():
    st.title("SPC — are key process parameters in control?")
    banner()
    c1, c2, c3 = st.columns([1.6, 1, 1.4])
    param = c1.selectbox("Process parameter", list(A.SPECS), format_func=lambda k: A.SPECS[k]["label"])
    line = c2.selectbox("Line", ["Line 1", "Line 2", "Line 3"], index=1)
    bw = c3.select_slider("Control limits computed from", options=WEEKS, value=(1, 1),
                          format_func=lambda w: f"W{w}")
    spec = A.SPECS[param]
    sg = get_subgroups(param)
    sg = sg[sg["line"] == line].reset_index(drop=True)
    lim = A.control_limits(sg[sg["week"].between(*bw)])
    flags = A.western_electric(sg["xbar"].to_numpy(), lim["cl"], lim["sigma"])
    sg["rules"] = [", ".join(f"R{r}" for r in sorted(f)) for f in flags]
    viol = sg[sg["rules"] != ""]

    x = np.arange(len(sg))
    fig = go.Figure()
    fig.add_hrect(y0=lim["cl"] - 2 * lim["sigma"], y1=lim["cl"] + 2 * lim["sigma"], fillcolor="rgba(42,120,214,0.06)",
                  line_width=0, layer="below")
    fig.add_trace(go.Scatter(x=x, y=sg["xbar"], mode="lines+markers", name="Subgroup mean (n=5)",
                             line=dict(color=AFTER, width=1.5), marker=dict(size=6),
                             customdata=np.stack([sg["label"], sg["week"]], axis=1),
                             hovertemplate="%{customdata[0]} (W%{customdata[1]})<br>X̄ = %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=viol.index, y=viol["xbar"], mode="markers", name="Western Electric violation",
                             marker=dict(size=11, color=FAIL, line=dict(color="#ffffff", width=1.5)),
                             customdata=np.stack([viol["label"], viol["rules"]], axis=1) if len(viol) else None,
                             hovertemplate="%{customdata[0]}<br>X̄ = %{y:.2f}<br>Rules: %{customdata[1]}<extra></extra>"))
    for y, nm, dash in [(lim["ucl"], "UCL", "dash"), (lim["cl"], "CL", "solid"), (lim["lcl"], "LCL", "dash")]:
        fig.add_hline(y=y, line=dict(color="#0b0b0b" if nm == "CL" else FAIL, dash=dash, width=1.3),
                      annotation_text=f"{nm} {y:.2f}", annotation_position="right",
                      annotation=dict(font=dict(size=13)))
    # Fix markers on subgroup axis
    for r in FIXES.itertuples():
        idx = sg.index[sg["week"] >= r.week]
        if len(idx):
            fig.add_vline(x=idx[0] - 0.5, line=dict(color="#52514e", dash="dot", width=1.2))
            fig.add_annotation(x=idx[0], y=1, yref="paper", text=r.short, showarrow=False, xanchor="left",
                               font=dict(size=12, color="#52514e"))
    wk_starts = sg.groupby("week").head(1)
    fig.update_xaxes(tickmode="array", tickvals=wk_starts.index, ticktext=[f"W{w}" for w in wk_starts["week"]])
    fig.update_yaxes(title=spec["label"])
    st.subheader(f"X̄ chart — {spec['label']}, {line}")
    style_fig(fig, 430)
    fig.update_layout(margin=dict(r=95))
    show(fig)
    if len(viol):
        # first sustained signal: first violation followed by >= 3 more within the next 6 subgroups
        vi = viol.index.to_numpy()
        sustained = [i for i in vi if ((vi > i) & (vi <= i + 6)).sum() >= 3]
        first = sg.loc[sustained[0]] if sustained else viol.iloc[0]
        takeaway(f"<b>{len(viol)}</b> of {len(sg)} subgroups break a Western Electric rule. The first sustained signal is "
                 f"<b>{first['label']} (week {first['week']})</b> — an SPC alarm here would have flagged the problem "
                 "weeks before it showed up in yield.")
    else:
        takeaway("No Western Electric rule violations — this parameter is in statistical control on this line.")

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.subheader("Capability before vs after the week-5 fix")
        u = UNITS[UNITS["line"] == line]
        pre, post = u[u["week"] < 5][param], u[u["week"] >= 5][param]
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=pre, name="Weeks 1–4", marker_color=BEFORE, opacity=0.75, nbinsx=50,
                                   histnorm="probability density"))
        fig.add_trace(go.Histogram(x=post, name="Weeks 5–12", marker_color=AFTER, opacity=0.75, nbinsx=50,
                                   histnorm="probability density"))
        for v, nm in [(spec["lsl"], "LSL"), (spec["usl"], "USL")]:
            fig.add_vline(x=v, line=dict(color=FAIL, width=2), annotation_text=nm)
        fig.add_vline(x=spec["target"], line=dict(color="#0b0b0b", dash="dot"), annotation_text="target")
        fig.update_layout(barmode="overlay")
        fig.update_xaxes(title=spec["label"])
        fig.update_yaxes(showticklabels=False, title=None)
        show(style_fig(fig, 340))
    with c2:
        cb, _ = A.cpk(pre.to_numpy(), spec["lsl"], spec["usl"])
        ca, _ = A.cpk(post.to_numpy(), spec["lsl"], spec["usl"])
        st.subheader("Cpk")
        m1, m2 = st.columns(2)
        m1.markdown(f'<div class="kpi"><div class="lbl">Weeks 1–4</div><div class="val">{cb:.2f}</div>'
                    f'<div class="dlt {"good" if cb >= 1.33 else "bad"}">{"capable" if cb >= 1.33 else "not capable"}</div></div>',
                    unsafe_allow_html=True)
        m2.markdown(f'<div class="kpi"><div class="lbl">Weeks 5–12</div><div class="val">{ca:.2f}</div>'
                    f'<div class="dlt {"good" if ca >= 1.33 else "bad"}">{"capable" if ca >= 1.33 else "not capable"}</div></div>',
                    unsafe_allow_html=True)
        st.caption("Target Cpk ≥ 1.33. Spec: " f"{spec['lsl']}–{spec['usl']} {spec['unit']}.")
        if len(viol):
            cnt = pd.Series([r for f in flags for r in f]).value_counts().sort_index()
            st.markdown("**Rules triggered**")
            for r, n in cnt.items():
                st.markdown(f"- R{r}: {A.WE_RULES[r]} — **{n}×**")
    takeaway(f"Cpk moved from <b>{cb:.2f}</b> to <b>{ca:.2f}</b> on {line} — "
             + ("the process is now capable, so the gain is being held." if ca >= 1.33 and cb < 1.33
                else "compare lines: Line 2's cure temperature is the one that was out of control."))


def page_ai():
    st.title("AI Insights — let the data point to the root cause")
    banner()
    tabs = st.tabs(["🚨 Anomaly detection", "🔍 Root-cause hints", "🧪 DOE: cure temp × time", "💬 Ask the data"])

    with tabs[0]:
        c1, _ = st.columns([1, 2])
        z = c1.slider("Sensitivity (flag if yield is this many σ below expected)", 2.5, 5.0, 3.0, 0.5)
        an = get_anomalies(z)
        if an.empty:
            st.success("No anomalies at this threshold.")
        else:
            an = an.copy()
            an["Severity"] = np.where(an["z"] < -5, "🔴 Critical", np.where(an["z"] < -3.5, "🟠 High", "🟡 Watch"))
            an["group"] = np.where(an["kind"] == "Supplier lot", an["entity"],
                                   np.where(an["kind"] == "Shift-week", an["entity"].str.split(" ·").str[0], an["line"]))
            groups = an.groupby("group", sort=False)
            for gname, g in list(groups)[:4]:
                r = g.iloc[0]
                what = "keyboard-station pass rate" if r["kind"] == "Supplier lot" else "final yield"
                ow = sorted(set(g["week"]) - {r["week"]})
                more = f" · also flagged in week{'s' if len(ow) > 1 else ''} {', '.join(map(str, ow))}" if ow else ""
                st.markdown(f'<div class="hint">{r["Severity"]} &nbsp;<b>{r["entity"]}</b> — {what} '
                            f'<b>{pct(r["yield_"])}</b> vs expected {pct(r["expected"])} '
                            f'({abs(r["z"]):.1f}σ below normal; {r["units"]:,} units){more}</div>',
                            unsafe_allow_html=True)
            tbl = an.rename(columns={"kind": "Type", "entity": "Where", "week": "Week", "units": "Units",
                                     "yield_": "Observed", "expected": "Expected", "z": "σ from expected"})
            st.dataframe(tbl[["Severity", "Type", "Where", "Week", "Units", "Observed", "Expected", "σ from expected"]],
                         hide_index=True, width="stretch",
                         column_config={"Observed": st.column_config.NumberColumn(format="percent"),
                                        "Expected": st.column_config.NumberColumn(format="percent"),
                                        "σ from expected": st.column_config.NumberColumn(format="%.1f")})
            st.caption("Method: binomial p-chart. Each line / shift / lot is compared against its peers built in the "
                       "same week, so the normal ramp-up improvement isn't flagged as an anomaly.")
            top3 = list(dict.fromkeys(an["group"]))[:3]
            takeaway(f"<b>{len(an)}</b> anomalies flagged automatically, and they cluster on just a few places — "
                     f"<b>{', '.join(top3)}</b>. That's where the engineers should look first.")

    with tabs[1]:
        c1, _ = st.columns([1.2, 2])
        w0, w1 = c1.select_slider("Analyse weeks", options=WEEKS, value=(WEEKS[0], WEEKS[-1]),
                                  format_func=lambda w: f"W{w}", key="rc_weeks")
        hints = get_hints(w0, w1)
        if not hints:
            st.info("No factor stands out beyond the normal learning curve in this window — "
                    "consistent with the fixes having held.")
        for h in hints:
            st.markdown(f'<div class="hint">{md_html(h.sentence)}</div>', unsafe_allow_html=True)
        st.caption("Method: for each top defect code a shallow decision tree searches line, shift, supplier lots and "
                   "process parameters (cure temp, cure time, torque) for the split that best separates failures. "
                   "Risk ratios are Mantel-Haenszel adjusted for build week, so the general learning curve "
                   "doesn't create false leads. Only hints with adjusted risk ≥ 2× are shown.")

        st.subheader("Which factors are associated with final failure?")
        fa = get_factors(w0, w1)
        fa = fa.sort_values("strength")
        fig = go.Figure(go.Bar(y=fa["factor"], x=fa["strength"] * 100, orientation="h",
                               marker_color=[FAIL if s else BEFORE for s in fa["significant"]],
                               customdata=np.stack([fa["worst_level"], fa["p_value"], fa["adj_risk"]], axis=1),
                               hovertemplate="%{y}<br>Worst level: %{customdata[0]}<br>"
                                             "Week-adjusted risk: %{customdata[2]:.2f}×<br>p = %{customdata[1]:.1e}<extra></extra>"))
        fig.update_xaxes(title="Association strength (week-stratified χ², per 100 units)")
        show(style_fig(fig, 340, legend=False))
        st.caption("Red = significant at p < 0.001 · grey = not significant. Display lot is a built-in negative control.")
        top = fa.iloc[-1]
        takeaway(f"<b>{top['factor']}</b> (worst: {top['worst_level']}) is the factor most associated with failure, "
                 "while display-panel lots show no real effect — the method separates signal from noise.")

    with tabs[2]:
        res = A.doe_analysis(DOE)
        st.markdown("A 2×2 full-factorial DOE (3 replicates + 3 center points, 200 units/run) run on the pilot line "
                    "to choose the new adhesive-cure recipe after the Line 2 finding.")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Main & interaction effects")
            eff = pd.Series(res["effects"])
            fig = go.Figure(go.Bar(y=eff.index, x=eff.values, orientation="h",
                                   marker_color=[FAIL if v < 0 else PASS for v in eff.values],
                                   text=[f"{v:+.1f} pts" for v in eff.values], textposition="outside",
                                   cliponaxis=False, textfont=dict(size=15),
                                   hovertemplate="%{y}: %{x:+.2f} pts<extra></extra>"))
            fig.add_vline(x=0, line=dict(color="#0b0b0b", width=1))
            fig.update_xaxes(title="Effect on display-attach yield (pts)",
                             range=[min(eff.min(), 0) * 1.6, max(eff.max(), 0) * 1.8])
            show(style_fig(fig, 320, legend=False))
            sig = (eff.abs() > 2 * res["se"]).all()
            st.caption(f"Noise band (±2 SE from replicates): ±{2 * res['se']:.1f} pts — "
                       + ("all three effects are real." if sig else "effects inside this band are not significant."))
        with c2:
            st.subheader("Interaction plot")
            cells = res["cells"]
            fig = go.Figure()
            for i, (tm, g) in enumerate(cells.groupby("cure_time_min")):
                fig.add_trace(go.Scatter(x=g["cure_temp_c"], y=g["display_attach_yield_pct"], mode="lines+markers",
                                         name=f"{tm:g} min cure", line=dict(width=3, color=[BEFORE, AFTER][i]),
                                         marker=dict(size=11),
                                         hovertemplate="%{x} °C: %{y:.1f}%<extra>" + f"{tm:g} min</extra>"))
            fig.update_xaxes(title="Cure temperature (°C)", tickvals=sorted(cells["cure_temp_c"].unique()))
            fig.update_yaxes(title="Display-attach yield (%)")
            show(style_fig(fig, 320))
        b = res["best"]
        st.success(f"**Recommended setting: {b['cure_temp_c']:g} °C for {b['cure_time_min']:g} min** → "
                   f"{b['display_attach_yield_pct']:.1f}% display-attach yield (adopted as the week-5 recipe).")
        takeaway("Higher cure temperature is the dominant <i>negative</i> effect, and longer cure time helps mainly at "
                 "low temperature (non-parallel lines = interaction). Lower temp + longer time is the robust setting.")

    with tabs[3]:
        st.markdown("Ask a question in plain English. Answers are computed from the data with rule-based intent "
                    "matching — **no API key or internet needed**. Add “week N” to scope a question.")
        def _ask(question):
            st.session_state["qa_input"] = question
        cols = st.columns(4)
        for i, q in enumerate(A.EXAMPLE_QUESTIONS):
            cols[i % 4].button(q, key=f"ex{i}", width="stretch", on_click=_ask, args=(q,))
        q = st.text_input("Your question", key="qa_input",
                          placeholder="e.g. Which line has the lowest yield in week 4?")
        if q:
            st.markdown(f'<div class="hint" style="border-left-color:#2a78d6">{md_html(A.answer_question(q, DATA))}</div>',
                        unsafe_allow_html=True)


def page_program():
    st.title("Program view — taking the tool from demo to deployment")
    banner()
    st.markdown("How I would run this as a cross-functional program: who uses it, what it connects to, how it rolls out, "
                "and how we'd know it's working.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("""<div class="card"><h4>👥 Users & their question</h4>
<b>Factory / process engineers</b> — <i>Which station, line, parameter is hurting yield right now?</i><br><br>
<b>Quality & SQE</b> — <i>Is this a supplier-lot escape? Is the CAPA holding?</i><br><br>
<b>Supplier management</b> — <i>Which supplier needs an 8D, with evidence?</i><br><br>
<b>Ops / program leads</b> — <i>Are we on the yield-ramp plan for the next build gate?</i></div>""",
                unsafe_allow_html=True)
    c2.markdown("""<div class="card"><h4>🔌 Data sources</h4>
<b>MES</b> — unit genealogy: serial → line, shift, timestamps, station route<br><br>
<b>Test logs</b> — pass/fail, retest count, failure codes, measurements<br><br>
<b>Process / equipment data</b> — oven temp, cure time, screwdriver torque<br><br>
<b>Supplier data</b> — component lot, incoming inspection (IQC)<br><br>
<b>CAPA / 8D tracker</b> — fix events used to annotate trends</div>""", unsafe_allow_html=True)
    c3.markdown("""<div class="card"><h4>⚠️ Key risks & mitigations</h4>
<b>Data quality / genealogy gaps</b> → schema contract with CM; daily completeness checks<br><br>
<b>CM data-sharing constraints</b> → agree data scope & access in the supply agreement early<br><br>
<b>False alarms → alarm fatigue</b> → tune σ thresholds in pilot; humans confirm before action<br><br>
<b>Correlation ≠ causation</b> → hints trigger DOE / failure analysis, never auto-action<br><br>
<b>Adoption</b> → embed in existing daily yield review, not a new meeting</div>""", unsafe_allow_html=True)

    st.subheader("Rollout plan")
    phases = [
        ("1 · Pilot line", 0, 6, AFTER, "1 line at 1 CM. Validate MES/test-log pipeline; compare tool alarms with manual failure analysis.",
         "Exit: data completeness ≥ 98%, alarm precision ≥ 70%"),
        ("2 · All lines", 6, 14, "#6250d6", "All lines at the CM. Daily yield review runs on the tool; SPC alarms routed to line owners.",
         "Exit: used in every daily review; time-to-root-cause < 3 days"),
        ("3 · New suppliers / CMs", 14, 26, "#1baf7a", "Onboard the next CM and key component suppliers; supplier-lot views for SQE.",
         "Exit: new CM live within 2 weeks of first build"),
    ]
    fig = go.Figure()
    for name, s0, s1, col, _, _ in phases:
        fig.add_trace(go.Bar(y=[name], x=[s1 - s0], base=[s0], orientation="h", marker_color=col,
                             text=f"weeks {s0}–{s1}", textposition="inside", insidetextanchor="middle",
                             textfont=dict(color="#ffffff", size=15),
                             hovertemplate=f"{name}<br>weeks {s0}–{s1}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=15))
    fig.update_xaxes(title="Weeks from kickoff", dtick=2)
    show(style_fig(fig, 220, legend=False))
    cols = st.columns(3)
    for c, (name, _, _, col, detail, gate) in zip(cols, phases):
        c.markdown(f'<div class="card" style="border-top:4px solid {col}"><h4>{name}</h4>{detail}'
                   f'<br><br><b>{gate}</b></div>', unsafe_allow_html=True)
    st.write("")

    st.subheader("Success metrics")
    trend = get_trend()
    m = pd.DataFrame([
        dict(Metric="Time to root cause", Baseline="~2–3 weeks (manual pivot tables, FA queue)",
             Target="< 3 days from first SPC / anomaly signal", **{"Simulated result": "SPC flags Line 2 drift in W2; fix in W5"}),
        dict(Metric="Yield ramp speed", Baseline="Weeks to reach 90% final yield",
             Target="≥ 90% by start of mass-production ramp",
             **{"Simulated result": f"{pct(trend['final_yield'].iloc[0], 0)} → {pct(trend['final_yield'].iloc[-1], 0)} in 12 weeks"}),
        dict(Metric="DPPM (station fails)", Baseline=f"{trend['dppm'].iloc[0]:,.0f} (W1)", Target="−80% by Ramp",
             **{"Simulated result": f"{trend['dppm'].iloc[-1]:,.0f} (W12), {(1 - trend['dppm'].iloc[-1] / trend['dppm'].iloc[0]) * 100:.0f}% lower"}),
        dict(Metric="Retest rate", Baseline=pct(trend["retest_rate"].iloc[0]), Target="< 3%",
             **{"Simulated result": pct(trend["retest_rate"].iloc[-1])}),
        dict(Metric="Adoption", Baseline="—", Target="Used in 100% of daily yield reviews; ≥ 80% of CAPAs cite tool evidence",
             **{"Simulated result": "n/a (demo)"}),
    ])
    st.table(m.set_index("Metric"))
    takeaway("The tool's value is measured in <b>days to root cause</b> and <b>weeks to yield target</b> — "
             "not in dashboards built.")


# --------------------------------------------------------------------------- navigation
# DEMO_START_PAGE (env var) chooses the landing page, e.g. DEMO_START_PAGE=ai-insights; also used by tests.
_START = os.environ.get("DEMO_START_PAGE", "overview")
_PAGES = [(page_overview, "Overview", "📊", "overview"), (page_drilldown, "Drill-down", "🔎", "drilldown"),
          (page_pareto, "Defect Pareto", "📉", "pareto"), (page_spc, "SPC", "📏", "spc"),
          (page_ai, "AI Insights", "🤖", "ai-insights"), (page_program, "Program view", "🗺️", "program")]
pg = st.navigation([st.Page(f, title=t, icon=i, url_path=u, default=(u == _START)) for f, t, i, u in _PAGES])
with st.sidebar:
    st.markdown("### Product X · Yield Analytics")
    st.caption("Final assembly + test · 3 lines · 2 shifts · 6 stations · 12 weeks (EVT → DVT → PVT → Ramp)")
    st.markdown('<div class="sim-banner">Simulated data – for demonstration only</div>', unsafe_allow_html=True)
    st.caption(f"{len(UNITS):,} units · {len(SR):,} station records")
pg.run()
