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
import i18n

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

# --------------------------------------------------------------------------- language
_init_lang = st.query_params.get("lang", os.environ.get("DEMO_LANG", "en"))
_lang_label = st.sidebar.radio("🌐 Language / 语言", list(i18n.LANGS.values()),
                               index=1 if _init_lang == "zh" else 0, horizontal=True, key="lang")
LANG = {v: k for k, v in i18n.LANGS.items()}[_lang_label]
if st.query_params.get("lang") != LANG:
    st.query_params["lang"] = LANG  # keep the choice on refresh / in shared links
ZH = LANG == "zh"


def T(en: str, zh: str) -> str:
    """Pick the English or Chinese string for the current language."""
    return zh if ZH else en


def tr_station(x):
    return i18n.station(x, LANG)


def tr_line(x):
    return i18n.line(x, LANG)


def tr_shift(x):
    return i18n.shift(x, LANG)


def tr_text(x):
    return i18n.text(x, LANG)


def wk_label(w):
    return f"W{w}"


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
    st.markdown('<div class="sim-banner">⚠️ <b>' + T("Simulated data – for demonstration only.", "模拟数据 – 仅用于演示。")
                + '</b> ' + T("Generic “Product X”; not based on any real company, product or process.",
                              "通用“产品 X”；不基于任何真实公司、产品或工艺。") + '</div>', unsafe_allow_html=True)


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
@st.cache_data(show_spinner="Loading simulated data… / 正在加载模拟数据…")
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
                      annotation_text=i18n.phase(ph, LANG), annotation_position="top left",
                      annotation=dict(font=dict(size=13, color="#52514e")))


def add_fix_lines(fig, x_of_week=lambda w: w - 0.5, label=True):
    for r in FIXES.itertuples():
        fig.add_vline(x=x_of_week(r.week), line=dict(color="#0b0b0b", width=1.5, dash="dot"))
        if label:
            fig.add_annotation(x=x_of_week(r.week), y=0.02, yref="paper", text=f"<b>{T('Fix', '改进')}:</b> {fix_short(r)}",
                               showarrow=False, xanchor="left", xshift=4, font=dict(size=13, color="#0b0b0b"),
                               bgcolor="rgba(255,255,255,0.85)")


def fix_short(r):
    return i18n.FIX_SHORT_ZH.get(r.week, r.short) if ZH else r.short


def spec_label(param):
    return i18n.SPEC_LABEL_ZH[param] if ZH else A.SPECS[param]["label"]


# =========================================================================== pages
def page_overview():
    st.title(T("Product X — Yield Ramp Overview", "产品 X — 良率爬坡总览"))
    banner()
    trend = get_trend()
    c0, _ = st.columns([1, 3])
    wk = c0.select_slider(T("Week shown in KPI cards", "KPI 卡片显示的周"), options=WEEKS, value=WEEKS[-1],
                          format_func=lambda w: T(f"Week {w} ({PHASE_OF[w]})", f"第 {w} 周（{i18n.phase(PHASE_OF[w], 'zh')}）"))
    cur = trend.set_index("week").loc[wk]
    prev = trend.set_index("week").loc[wk - 1] if wk > 1 else None

    specs = [(T("Final yield", "最终良率"), "final_yield", "pct", True),
             (T("First-pass yield (FPY)", "直通率 (FPY)"), "fpy", "pct", True),
             (T("Rolled throughput yield (RTY)", "滚动直通率 (RTY)"), "rty", "pct", True),
             (T("DPPM (station fails)", "DPPM（工站失效）"), "dppm", "int", False),
             (T("Retest rate", "复测率"), "retest_rate", "pct", False), (T("Units built", "生产数量"), "units", "int", None)]
    cols = st.columns(6)
    for col, (lbl, key, fmt, higher_good) in zip(cols, specs):
        v = cur[key]
        val = pct(v) if fmt == "pct" else f"{v:,.0f}"
        if prev is None:
            dl, cls = T("first week", "首周"), "flat"
        else:
            dv = v - prev[key]
            if fmt == "pct":
                dl = T(f"{'▲' if dv >= 0 else '▼'} {abs(dv) * 100:.1f} pts WoW", f"环比 {'▲' if dv >= 0 else '▼'} {abs(dv) * 100:.1f}pp")
            else:
                dl = T(f"{'▲' if dv >= 0 else '▼'} {abs(dv) / max(prev[key], 1) * 100:.0f}% WoW",
                       f"环比 {'▲' if dv >= 0 else '▼'} {abs(dv) / max(prev[key], 1) * 100:.0f}%")
            cls = "flat" if higher_good is None or abs(dv) < 1e-9 else ("good" if (dv > 0) == higher_good else "bad")
        col.markdown(f'<div class="kpi"><div class="lbl">{lbl}</div><div class="val">{val}</div>'
                     f'<div class="dlt {cls}">{dl}</div></div>', unsafe_allow_html=True)
    st.write("")

    st.subheader(T("Weekly yield trend with corrective actions", "每周良率趋势与纠正措施"))
    fig = go.Figure()
    add_phase_bands(fig)
    fig.add_hline(y=0.90, line=dict(color=TARGET, dash="dash", width=1),
                  annotation_text=T("90% target", "90% 目标"), annotation_position="bottom left")
    for key, name, color, width in [("final_yield", T("Final yield (after rework/retest)", "最终良率（含返工/复测）"), AFTER, 4),
                                    ("fpy", T("First-pass yield", "直通率"), "#eb6834", 2.5)]:
        fig.add_trace(go.Scatter(x=trend["week"], y=trend[key], name=name, mode="lines+markers",
                                 line=dict(color=color, width=width), marker=dict(size=9),
                                 hovertemplate=f"{name}: %{{y:.1%}}<extra>W%{{x}}</extra>"))
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
        gains.append(f"{fix_short(r)} +{(b.get(r.week, np.nan) - b.get(r.week - 1, np.nan)) * 100:.0f} {T('pts', '个百分点')}")
    takeaway(T(f"Final yield climbed from <b>{pct(f['final_yield'], 0)}</b> (W1) to <b>{pct(l['final_yield'], 0)}</b> (W12); "
               f"yield steps up right after each fix: {', '.join(gains)}.",
               f"最终良率从 <b>{pct(f['final_yield'], 0)}</b>（W1）提升到 <b>{pct(l['final_yield'], 0)}</b>（W12）；"
               f"每次改进后良率都立即跃升：{'，'.join(gains)}。"))

    st.subheader(T("Where yield is lost — failures per 100 units started, by station", "良率损失在哪里 — 各工站每百台失效数"))
    loss = UNITS[UNITS["final_result"] == "FAIL"].groupby(["week", "fail_station"]).size().unstack(fill_value=0)
    loss = loss.div(UNITS.groupby("week").size(), axis=0).reindex(columns=A.STATIONS, fill_value=0) * 100
    fig = go.Figure()
    for i, stn in enumerate(A.STATIONS):
        fig.add_trace(go.Bar(x=loss.index, y=loss[stn], name=tr_station(stn), marker_color=SERIES[i],
                             marker_line=dict(color="#ffffff", width=1.5),
                             hovertemplate=f"{tr_station(stn)}: %{{y:.1f}} {T('per 100', '/百台')}<extra>W%{{x}}</extra>"))
    add_fix_lines(fig, label=False)
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(tickmode="array", tickvals=WEEKS, ticktext=[f"W{w}" for w in WEEKS])
    fig.update_yaxes(title=T("Failures per 100 units", "每百台失效数"))
    show(style_fig(fig, 400))
    steps = []
    for r in FIXES.itertuples():
        st_ = r.affected_station
        before = loss.loc[max(1, r.week - 2):r.week - 1, st_].mean()
        after = loss.loc[r.week:r.week + 1, st_].mean()
        steps.append(T(f"{st_} {before:.0f} → {after:.0f} after W{r.week}",
                       f"{tr_station(st_)} 在 W{r.week} 后 {before:.0f} → {after:.0f}"))
    takeaway(T("Loss fell at every station as the process matured, but three stations show a <b>step change right after "
               f"a fix</b>: {'; '.join(steps)} (failures per 100 units).",
               "随着工艺成熟，各工站损失都在下降，但有三个工站在<b>改进后立即出现阶跃式下降</b>："
               f"{'；'.join(steps)}（每百台失效数）。"))


def page_drilldown():
    st.title(T("Drill-down — where is yield lost?", "下钻分析 — 良率损失在哪里？"))
    banner()
    c1, c2, c3, c4 = st.columns([2, 1.3, 1.1, 1.4])
    w0, w1 = c1.select_slider(T("Weeks", "周"), options=WEEKS, value=(WEEKS[0], WEEKS[-1]), format_func=wk_label)
    lines = c2.multiselect(T("Lines", "产线"), sorted(UNITS["line"].unique()), default=sorted(UNITS["line"].unique()),
                           format_func=tr_line)
    shifts = c3.multiselect(T("Shifts", "班次"), ["Day", "Night"], default=["Day", "Night"], format_func=tr_shift)
    phases = c4.multiselect(T("Phases", "阶段"), ["EVT", "DVT", "PVT", "Ramp"], default=["EVT", "DVT", "PVT", "Ramp"],
                            format_func=lambda p: i18n.phase(p, LANG))
    um = (UNITS["week"].between(w0, w1) & UNITS["line"].isin(lines) & UNITS["shift"].isin(shifts)
          & UNITS["phase"].isin(phases))
    sm = (SR["week"].between(w0, w1) & SR["line"].isin(lines) & SR["shift"].isin(shifts) & SR["phase"].isin(phases))
    u, s = UNITS[um], SR[sm]
    if u.empty:
        st.warning(T("No units match these filters.", "没有符合筛选条件的产品。"))
        return
    dim_names = {"Station": T("Station", "工站"), "Line": T("Line", "产线"), "Shift": T("Shift", "班次"),
                 "Supplier lot": T("Supplier lot", "供应商批次"), "Phase": T("Phase", "阶段")}
    _dim = st.radio(T("Break down by", "按维度拆分"), list(dim_names.values()), horizontal=True)
    dim = {v: k for k, v in dim_names.items()}[_dim]

    if dim == "Station":
        t = A.station_fpy(s)
        fig = go.Figure(go.Bar(x=[tr_station(x) for x in t["station"].astype(str)], y=t["fpy"], marker_color=AFTER,
                               text=[pct(v) for v in t["fpy"]], textposition="outside",
                               hovertemplate="%{x}<br>FPY %{y:.1%}<extra></extra>"))
        worst = t.loc[t["fpy"].idxmin()]
        fig.update_yaxes(tickformat=".0%", range=[max(0, t["fpy"].min() - 0.1), 1.02], title=T("First-pass yield", "直通率"))
        show(style_fig(fig, 420, legend=False))
        takeaway(T(f"<b>{worst['station']}</b> has the lowest first-pass yield ({pct(worst['fpy'])}) in this slice; "
                   f"RTY across all six stations is {pct(t['fpy'].prod())}.",
                   f"在当前筛选范围内，<b>{tr_station(worst['station'])}</b> 的直通率最低（{pct(worst['fpy'])}）；"
                   f"六个工站的滚动直通率 (RTY) 为 {pct(t['fpy'].prod())}。"))
        st.subheader(T("Station FPY by week", "各工站每周直通率"))
        hm = A.station_fpy(s, by="week").pivot(index="station", columns="week", values="fpy")
        fig = go.Figure(go.Heatmap(z=hm.values, x=[f"W{w}" for w in hm.columns], y=[tr_station(x) for x in hm.index.astype(str)],
                                   colorscale=[[0, "#e34948"], [0.5, "#f7f6f2"], [1, "#2a78d6"]], zmin=0.7, zmax=1.0,
                                   text=[[pct(v, 0) for v in row] for row in hm.values], texttemplate="%{text}",
                                   textfont=dict(size=13), colorbar=dict(tickformat=".0%"),
                                   hovertemplate="%{y} · %{x}<br>FPY %{z:.1%}<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        show(style_fig(fig, 360, legend=False))
        takeaway(T("Red cells mark station-weeks below ~85% FPY — watch Display Attach turn red in W3–W4 and recover after W5.",
                   "红色格子表示直通率低于约 85% 的工站-周 —— 注意屏幕贴合在 W3–W4 变红，W5 之后恢复。"))

    elif dim in ("Line", "Shift"):
        col = dim.lower()
        colors = LINE_COLORS if col == "line" else SHIFT_COLORS
        tr_k = tr_line if col == "line" else tr_shift
        wk = u.groupby(["week", col])["final_result"].apply(lambda x: (x == "PASS").mean()).unstack()
        fig = go.Figure()
        add_phase_bands(fig)
        for k in wk.columns:
            fig.add_trace(go.Scatter(x=wk.index, y=wk[k], name=tr_k(k), mode="lines+markers",
                                     line=dict(color=colors[k], width=3), marker=dict(size=8),
                                     hovertemplate=f"{tr_k(k)}: %{{y:.1%}}<extra>W%{{x}}</extra>"))
        add_fix_lines(fig)
        fig.update_yaxes(tickformat=".0%", title=T("Final yield", "最终良率"))
        fig.update_xaxes(tickmode="array", tickvals=WEEKS, ticktext=[f"W{w}" for w in WEEKS])
        show(style_fig(fig, 440))
        gap = (wk.max(axis=1) - wk.min(axis=1))
        gw = gap.idxmax()
        lo = wk.loc[gw].idxmin()
        takeaway(T(f"The widest gap is in <b>week {gw}</b>: {lo} trails by <b>{gap.max() * 100:.0f} pts</b>"
                   + (" — the Line 2 cure-oven drift." if col == "line" else " — night-shift cosmetic losses until the W9 retraining."),
                   f"差距最大的是<b>第 {gw} 周</b>：{tr_k(lo)} 落后 <b>{gap.max() * 100:.0f} 个百分点</b>"
                   + (" —— 2号线固化烤炉漂移。" if col == "line" else " —— 夜班外观损失，直到 W9 再培训。")))
        st.subheader(T(f"Station first-pass yield by {col}", f"各工站直通率（按{dim_names[dim]}）"))
        t = A.station_fpy(s, by=col)
        fig = go.Figure()
        for k in sorted(t[col].unique()):
            tt = t[t[col] == k]
            fig.add_trace(go.Bar(x=[tr_station(x) for x in tt["station"].astype(str)], y=tt["fpy"], name=tr_k(k),
                                 marker_color=colors[k], hovertemplate=f"{tr_k(k)}<br>%{{x}}: %{{y:.1%}}<extra></extra>"))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05)
        fig.update_yaxes(tickformat=".0%", range=[0.75, 1.0])
        show(style_fig(fig, 380))
        diff = t.pivot(index="station", columns=col, values="fpy")
        spread = (diff.max(axis=1) - diff.min(axis=1))
        st_w = spread.idxmax()
        takeaway(T(f"The {col}s differ most at <b>{st_w}</b> ({spread.max() * 100:.1f} pts FPY spread); "
                   "other stations are nearly identical — the problem is local, not systemic.",
                   f"各{dim_names[dim]}之间差异最大的是 <b>{tr_station(st_w)}</b>（直通率相差 {spread.max() * 100:.1f} 个百分点）；"
                   "其他工站几乎一致 —— 问题是局部的，而非系统性的。"))

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
                               hovertemplate="%{x} (%{customdata[1]})<br>" + T("Keyboard-station fail rate", "键盘工站失效率")
                                             + " %{y:.1%}<br>%{customdata[0]} " + T("units", "台") + "<extra></extra>"))
        fig.add_hline(y=med, line=dict(dash="dash", color=TARGET), annotation_text=f"{T('median', '中位数')} {pct(med)}")
        fig.update_yaxes(tickformat=".0%", title=T("Keyboard/Trackpad fail rate", "键盘/触控板失效率"))
        fig.update_xaxes(tickangle=-45)
        show(style_fig(fig, 440, legend=False))
        st.caption(T("Red = > 3× median lot fail rate · orange = Supplier B · blue = Supplier A",
                     "红色 = 失效率 > 批次中位数 3 倍 · 橙色 = Supplier B · 蓝色 = Supplier A"))
        top = t.iloc[0]
        takeaway(T(f"Keyboard lot <b>{top['kb_lot']}</b> fails at <b>{pct(top['fail'])}</b> — "
                   f"{top['fail'] / med:.0f}× the median lot. Every other lot from the same supplier is normal, "
                   "so this is a lot-specific escape, not a supplier-wide problem.",
                   f"键盘批次 <b>{top['kb_lot']}</b> 的失效率为 <b>{pct(top['fail'])}</b> —— 是批次中位数的 "
                   f"{top['fail'] / med:.0f} 倍。同一供应商的其他批次都正常，说明这是单一批次的质量逃逸，而不是整个供应商的问题。"))

    else:  # Phase
        t = A.yield_by(u, "phase").set_index("phase").reindex(["EVT", "DVT", "PVT", "Ramp"]).dropna().reset_index()
        fig = go.Figure(go.Bar(x=[i18n.phase(p, LANG) for p in t["phase"]], y=t["yield"], marker_color=AFTER, text=[pct(v) for v in t["yield"]],
                               textposition="outside", hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
        fig.add_hline(y=0.9, line=dict(dash="dash", color=TARGET), annotation_text=T("90% target", "90% 目标"))
        fig.update_yaxes(tickformat=".0%", range=[0, 1.05], title=T("Final yield", "最终良率"))
        show(style_fig(fig, 400, legend=False))
        takeaway(T(f"Yield rose every build phase — {' → '.join(pct(v, 0) for v in t['yield'])} — "
                   "and only the Ramp phase clears the 90% target.",
                   f"良率在每个阶段都在提升 —— {' → '.join(pct(v, 0) for v in t['yield'])} —— 只有量产爬坡阶段达到 90% 目标。"))


def page_pareto():
    st.title(T("Defect Pareto — what fails most?", "缺陷柏拉图 — 什么失效最多？"))
    banner()
    c1, c2, _ = st.columns([1.3, 2, 1])
    modes = {"single": T("Single period", "单一时段"), "compare": T("Before vs after fixes", "改进前 vs 改进后")}
    _mode = c1.radio(T("View", "视图"), list(modes.values()), horizontal=False)
    mode = {v: k for k, v in modes.items()}[_mode]
    stations = c2.multiselect(T("Stations", "工站"), A.STATIONS, default=A.STATIONS, format_func=tr_station)

    def pareto_fig(s, height=440):
        p = A.pareto(s[s["station"].isin(stations)]).head(12)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=p["defect_code"], y=p["pct"], name=T("% of failures", "失效占比"), marker_color=FAIL,
                             customdata=np.stack([p["count"], [tr_station(x) for x in p["station"]]], axis=1),
                             hovertemplate="%{x}<br>%{customdata[1]}<br>%{customdata[0]} " + T("failures", "次失效")
                                           + " (%{y:.1%})<extra></extra>"))
        fig.add_trace(go.Scatter(x=p["defect_code"], y=p["cum_pct"], name=T("Cumulative %", "累计占比"), mode="lines+markers",
                                 line=dict(color="#0b0b0b", width=2), marker=dict(size=8),
                                 hovertemplate=T("Cumulative", "累计") + " %{y:.0%}<extra></extra>"))
        fig.add_hline(y=0.8, line=dict(dash="dash", color=TARGET), annotation_text="80%")
        fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
        fig.update_xaxes(tickangle=-35)
        return style_fig(fig, height), p

    if mode == "single":
        w0, w1 = st.select_slider(T("Weeks (default: W3–W6, when all three issues were active)",
                                    "周（默认 W3–W6，三个问题同时存在的时期）"), options=WEEKS,
                                  value=(3, 6), format_func=wk_label)
        s = SR[SR["week"].between(w0, w1)]
        fig, p = pareto_fig(s)
        show(fig)
        if p.empty:
            return
        n80 = int((p["cum_pct"] < 0.8).sum() + 1)
        allp = A.pareto(s[s["station"].isin(stations)])
        top3p = pct(p['cum_pct'].iloc[min(2, len(p) - 1)], 0)
        takeaway(T(f"<b>{n80}</b> of {len(allp)} defect codes make up 80% of failures; the top three — "
                   f"{', '.join(p['defect_code'].head(3))} — account for <b>{top3p}</b>. "
                   "Start with the codes that point at a specific cause (lot, shift, parameter), then the broad ones.",
                   f"{len(allp)} 个缺陷代码中有 <b>{n80}</b> 个占了 80% 的失效；前三名 —— "
                   f"{', '.join(p['defect_code'].head(3))} —— 合计占 <b>{top3p}</b>。"
                   "先处理指向具体原因（批次、班次、参数）的代码，再处理分散的。"))
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(T("Before: weeks 1–4", "改进前：第 1–4 周"))
            fb, pb = pareto_fig(SR[SR["week"].between(1, 4)], 420)
            show(fb)
        with c2:
            st.subheader(T("After: weeks 10–12", "改进后：第 10–12 周"))
            fa, pa = pareto_fig(SR[SR["week"].between(10, 12)], 420)
            show(fa)
        rate = lambda s: (s["result"] == "FAIL").sum() / s["serial"].nunique() * 100
        b, a = rate(SR[SR["week"].between(1, 4)]), rate(SR[SR["week"].between(10, 12)])
        takeaway(T(f"Failures fell from <b>{b:.0f}</b> to <b>{a:.0f}</b> per 100 units. The targeted codes "
                   "(DSP-ADHESIVE-DELAM, KB-KEY-STICK, COS-SCRATCH) dropped out of the top of the Pareto — "
                   "what's left is a flatter, 'normal' mix of residual defects.",
                   f"每百台失效数从 <b>{b:.0f}</b> 降到 <b>{a:.0f}</b>。被针对的缺陷代码"
                   "（DSP-ADHESIVE-DELAM、KB-KEY-STICK、COS-SCRATCH）已退出柏拉图前列 —— "
                   "剩下的是更平坦、“正常”的残余缺陷组合。"))


def page_spc():
    st.title(T("SPC — are key process parameters in control?", "SPC — 关键工艺参数是否受控？"))
    banner()
    c1, c2, c3 = st.columns([1.6, 1, 1.4])
    param = c1.selectbox(T("Process parameter", "工艺参数"), list(A.SPECS), format_func=spec_label)
    line = c2.selectbox(T("Line", "产线"), ["Line 1", "Line 2", "Line 3"], index=1, format_func=tr_line)
    bw = c3.select_slider(T("Control limits computed from", "控制限计算基准周"), options=WEEKS, value=(1, 1),
                          format_func=wk_label)
    spec = A.SPECS[param]
    sg = get_subgroups(param)
    sg = sg[sg["line"] == line].reset_index(drop=True)
    lim = A.control_limits(sg[sg["week"].between(*bw)])
    flags = A.western_electric(sg["xbar"].to_numpy(), lim["cl"], lim["sigma"])
    sg["rules"] = [", ".join(f"R{r}" for r in sorted(f)) for f in flags]
    if ZH:
        sg["label"] = sg["date"].dt.strftime("%m月%d日") + " " + sg["shift"].map(i18n.SHIFT_ZH)
    viol = sg[sg["rules"] != ""]

    x = np.arange(len(sg))
    fig = go.Figure()
    fig.add_hrect(y0=lim["cl"] - 2 * lim["sigma"], y1=lim["cl"] + 2 * lim["sigma"], fillcolor="rgba(42,120,214,0.06)",
                  line_width=0, layer="below")
    fig.add_trace(go.Scatter(x=x, y=sg["xbar"], mode="lines+markers", name=T("Subgroup mean (n=5)", "子组均值 (n=5)"),
                             line=dict(color=AFTER, width=1.5), marker=dict(size=6),
                             customdata=np.stack([sg["label"], sg["week"]], axis=1),
                             hovertemplate="%{customdata[0]} (W%{customdata[1]})<br>X̄ = %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=viol.index, y=viol["xbar"], mode="markers", name=T("Western Electric violation", "西电规则违规"),
                             marker=dict(size=11, color=FAIL, line=dict(color="#ffffff", width=1.5)),
                             customdata=np.stack([viol["label"], viol["rules"]], axis=1) if len(viol) else None,
                             hovertemplate="%{customdata[0]}<br>X̄ = %{y:.2f}<br>" + T("Rules", "规则") + ": %{customdata[1]}<extra></extra>"))
    for y, nm, dash in [(lim["ucl"], "UCL", "dash"), (lim["cl"], "CL", "solid"), (lim["lcl"], "LCL", "dash")]:
        fig.add_hline(y=y, line=dict(color="#0b0b0b" if nm == "CL" else FAIL, dash=dash, width=1.3),
                      annotation_text=f"{nm} {y:.2f}", annotation_position="right",
                      annotation=dict(font=dict(size=13)))
    # Fix markers on subgroup axis
    for r in FIXES.itertuples():
        idx = sg.index[sg["week"] >= r.week]
        if len(idx):
            fig.add_vline(x=idx[0] - 0.5, line=dict(color="#52514e", dash="dot", width=1.2))
            fig.add_annotation(x=idx[0], y=1, yref="paper", text=fix_short(r), showarrow=False, xanchor="left",
                               font=dict(size=12, color="#52514e"))
    wk_starts = sg.groupby("week").head(1)
    fig.update_xaxes(tickmode="array", tickvals=wk_starts.index, ticktext=[f"W{w}" for w in wk_starts["week"]])
    fig.update_yaxes(title=spec_label(param))
    st.subheader(T(f"X̄ chart — {spec['label']}, {line}", f"X̄ 控制图 — {spec_label(param)}，{tr_line(line)}"))
    style_fig(fig, 430)
    fig.update_layout(margin=dict(r=95))
    show(fig)
    if len(viol):
        # first sustained signal: first violation followed by >= 3 more within the next 6 subgroups
        vi = viol.index.to_numpy()
        sustained = [i for i in vi if ((vi > i) & (vi <= i + 6)).sum() >= 3]
        first = sg.loc[sustained[0]] if sustained else viol.iloc[0]
        takeaway(T(f"<b>{len(viol)}</b> of {len(sg)} subgroups break a Western Electric rule. The first sustained signal is "
                   f"<b>{first['label']} (week {first['week']})</b> — an SPC alarm here would have flagged the problem "
                   "weeks before it showed up in yield.",
                   f"{len(sg)} 个子组中有 <b>{len(viol)}</b> 个违反西电规则。第一个持续信号出现在 "
                   f"<b>{first['label']}（第 {first['week']} 周）</b> —— 如果此时触发 SPC 报警，"
                   "可以比良率下滑提前数周发现问题。"))
    else:
        takeaway(T("No Western Electric rule violations — this parameter is in statistical control on this line.",
                   "没有违反西电规则 —— 该参数在这条产线上处于统计受控状态。"))

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.subheader(T("Capability before vs after the week-5 fix", "第 5 周改进前后的过程能力"))
        u = UNITS[UNITS["line"] == line]
        pre, post = u[u["week"] < 5][param], u[u["week"] >= 5][param]
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=pre, name=T("Weeks 1–4", "第 1–4 周"), marker_color=BEFORE, opacity=0.75, nbinsx=50,
                                   histnorm="probability density"))
        fig.add_trace(go.Histogram(x=post, name=T("Weeks 5–12", "第 5–12 周"), marker_color=AFTER, opacity=0.75, nbinsx=50,
                                   histnorm="probability density"))
        for v, nm in [(spec["lsl"], "LSL"), (spec["usl"], "USL")]:
            fig.add_vline(x=v, line=dict(color=FAIL, width=2), annotation_text=nm)
        fig.add_vline(x=spec["target"], line=dict(color="#0b0b0b", dash="dot"), annotation_text=T("target", "目标"))
        fig.update_layout(barmode="overlay")
        fig.update_xaxes(title=spec_label(param))
        fig.update_yaxes(showticklabels=False, title=None)
        show(style_fig(fig, 340))
    with c2:
        cb, _ = A.cpk(pre.to_numpy(), spec["lsl"], spec["usl"])
        ca, _ = A.cpk(post.to_numpy(), spec["lsl"], spec["usl"])
        st.subheader("Cpk")
        m1, m2 = st.columns(2)
        cap = lambda c: T("capable", "能力充足") if c >= 1.33 else T("not capable", "能力不足")
        m1.markdown(f'<div class="kpi"><div class="lbl">{T("Weeks 1–4", "第 1–4 周")}</div><div class="val">{cb:.2f}</div>'
                    f'<div class="dlt {"good" if cb >= 1.33 else "bad"}">{cap(cb)}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="kpi"><div class="lbl">{T("Weeks 5–12", "第 5–12 周")}</div><div class="val">{ca:.2f}</div>'
                    f'<div class="dlt {"good" if ca >= 1.33 else "bad"}">{cap(ca)}</div></div>', unsafe_allow_html=True)
        st.caption(T("Target Cpk ≥ 1.33. Spec: ", "目标 Cpk ≥ 1.33。规格：") + f"{spec['lsl']}–{spec['usl']} {spec['unit']}.")
        if len(viol):
            cnt = pd.Series([r for f in flags for r in f]).value_counts().sort_index()
            st.markdown(T("**Rules triggered**", "**触发的规则**"))
            for r, n in cnt.items():
                st.markdown(f"- R{r}: {i18n.WE_RULES_ZH[r] if ZH else A.WE_RULES[r]} — **{n}×**")
    held = ca >= 1.33 and cb < 1.33
    takeaway(T(f"Cpk moved from <b>{cb:.2f}</b> to <b>{ca:.2f}</b> on {line} — "
               + ("the process is now capable, so the gain is being held." if held
                  else "compare lines: Line 2's cure temperature is the one that was out of control."),
               f"{tr_line(line)} 的 Cpk 从 <b>{cb:.2f}</b> 变为 <b>{ca:.2f}</b> —— "
               + ("过程能力已经充足，改进成果得以保持。" if held else "对比各产线：失控的是 2号线的固化温度。")))


def page_ai():
    st.title(T("AI Insights — let the data point to the root cause", "AI 洞察 — 让数据指出根因"))
    banner()
    tabs = st.tabs([T("🚨 Anomaly detection", "🚨 异常检测"), T("🔍 Root-cause hints", "🔍 根因提示"),
                    T("🧪 DOE: cure temp × time", "🧪 DOE：固化温度 × 时间"), T("💬 Ask the data", "💬 向数据提问")])

    with tabs[0]:
        c1, _ = st.columns([1, 2])
        z = c1.slider(T("Sensitivity (flag if yield is this many σ below expected)", "灵敏度（良率低于预期多少个 σ 时标记）"),
                      2.5, 5.0, 3.0, 0.5)
        an = get_anomalies(z)
        if an.empty:
            st.success(T("No anomalies at this threshold.", "在此阈值下没有异常。"))
        else:
            an = an.copy()
            an["Severity"] = np.where(an["z"] < -5, T("🔴 Critical", "🔴 严重"),
                                      np.where(an["z"] < -3.5, T("🟠 High", "🟠 高"), T("🟡 Watch", "🟡 关注")))
            kind_zh = {"Supplier lot": "供应商批次", "Shift-week": "班次-周", "Line-week": "产线-周", "Line-day": "产线-日"}
            an["group"] = np.where(an["kind"] == "Supplier lot", an["entity"],
                                   np.where(an["kind"] == "Shift-week", an["entity"].str.split(" ·").str[0], an["line"]))
            groups = an.groupby("group", sort=False)
            for gname, g in list(groups)[:4]:
                r = g.iloc[0]
                what = (T("keyboard-station pass rate", "键盘工站通过率") if r["kind"] == "Supplier lot"
                        else T("final yield", "最终良率"))
                ow = sorted(set(g["week"]) - {r["week"]})
                if ZH:
                    more = f" · 第 {', '.join(map(str, ow))} 周也被标记" if ow else ""
                    body = (f'<b>{tr_text(r["entity"])}</b> — {what} <b>{pct(r["yield_"])}</b>，预期 {pct(r["expected"])}'
                            f'（低于正常波动 {abs(r["z"]):.1f}σ；{r["units"]:,} 台）{more}')
                else:
                    more = f" · also flagged in week{'s' if len(ow) > 1 else ''} {', '.join(map(str, ow))}" if ow else ""
                    body = (f'<b>{r["entity"]}</b> — {what} <b>{pct(r["yield_"])}</b> vs expected {pct(r["expected"])} '
                            f'({abs(r["z"]):.1f}σ below normal; {r["units"]:,} units){more}')
                st.markdown(f'<div class="hint">{r["Severity"]} &nbsp;{body}</div>', unsafe_allow_html=True)
            tbl = an.copy()
            if ZH:
                tbl["kind"] = tbl["kind"].map(kind_zh)
                tbl["entity"] = tbl["entity"].map(tr_text)
            cols = {"Severity": T("Severity", "严重程度"), "kind": T("Type", "类型"), "entity": T("Where", "位置"),
                    "week": T("Week", "周"), "units": T("Units", "数量"), "yield_": T("Observed", "实际"),
                    "expected": T("Expected", "预期"), "z": T("σ from expected", "偏离 σ")}
            tbl = tbl[list(cols)].rename(columns=cols)
            st.dataframe(tbl, hide_index=True, width="stretch",
                         column_config={cols["yield_"]: st.column_config.NumberColumn(format="percent"),
                                        cols["expected"]: st.column_config.NumberColumn(format="percent"),
                                        cols["z"]: st.column_config.NumberColumn(format="%.1f")})
            st.caption(T("Method: binomial p-chart. Each line / shift / lot is compared against its peers built in the "
                         "same week, so the normal ramp-up improvement isn't flagged as an anomaly.",
                         "方法：二项分布 p 控制图。每条产线/班次/批次都与同一周生产的同类对比，"
                         "因此正常的爬坡改善不会被误报为异常。"))
            top3 = [tr_text(x) for x in list(dict.fromkeys(an["group"]))[:3]]
            takeaway(T(f"<b>{len(an)}</b> anomalies flagged automatically, and they cluster on just a few places — "
                       f"<b>{', '.join(top3)}</b>. That's where the engineers should look first.",
                       f"自动标记了 <b>{len(an)}</b> 个异常，且集中在少数几处 —— <b>{'、'.join(top3)}</b>。"
                       "工程师应该先从这里查起。"))

    with tabs[1]:
        c1, _ = st.columns([1.2, 2])
        w0, w1 = c1.select_slider(T("Analyse weeks", "分析的周"), options=WEEKS, value=(WEEKS[0], WEEKS[-1]),
                                  format_func=wk_label, key="rc_weeks")
        hints = get_hints(w0, w1)
        if not hints:
            st.info(T("No factor stands out beyond the normal learning curve in this window — "
                      "consistent with the fixes having held.",
                      "在此时间窗内，除正常学习曲线外没有突出的因素 —— 说明改进措施保持住了。"))
        for h in hints:
            st.markdown(f'<div class="hint">{md_html(h.text(LANG))}</div>', unsafe_allow_html=True)
        st.caption(T("Method: for each top defect code a shallow decision tree searches line, shift, supplier lots and "
                     "process parameters (cure temp, cure time, torque) for the split that best separates failures. "
                     "Risk ratios are Mantel-Haenszel adjusted for build week, so the general learning curve "
                     "doesn't create false leads. Only hints with adjusted risk ≥ 2× are shown.",
                     "方法：对每个主要缺陷代码，用浅层决策树在产线、班次、供应商批次和工艺参数（固化温度、固化时间、扭矩）"
                     "中搜索最能区分失效的切分点。风险比按生产周做 Mantel-Haenszel 校正，避免整体学习曲线造成误导。"
                     "只显示校正后风险 ≥ 2 倍的提示。"))

        st.subheader(T("Which factors are associated with final failure?", "哪些因素与最终失效相关？"))
        fa = get_factors(w0, w1)
        fa = fa.sort_values("strength")
        fnames = [i18n.FACTOR_ZH.get(f, f) if ZH else f for f in fa["factor"]]
        levels = [tr_text(v) for v in fa["worst_level"]]
        fig = go.Figure(go.Bar(y=fnames, x=fa["strength"] * 100, orientation="h",
                               marker_color=[FAIL if s else BEFORE for s in fa["significant"]],
                               customdata=np.stack([levels, fa["p_value"], fa["adj_risk"]], axis=1),
                               hovertemplate="%{y}<br>" + T("Worst level", "最差水平") + ": %{customdata[0]}<br>"
                                             + T("Week-adjusted risk", "周校正风险") + ": %{customdata[2]:.2f}×<br>"
                                             "p = %{customdata[1]:.1e}<extra></extra>"))
        fig.update_xaxes(title=T("Association strength (week-stratified χ², per 100 units)", "关联强度（按周分层 χ²，每百台）"))
        show(style_fig(fig, 340, legend=False))
        st.caption(T("Red = significant at p < 0.001 · grey = not significant. Display lot is a built-in negative control.",
                     "红色 = 显著（p < 0.001）· 灰色 = 不显著。屏幕批次是内置的阴性对照。"))
        takeaway(T(f"<b>{fnames[-1]}</b> (worst: {levels[-1]}) is the factor most associated with failure, "
                   "while display-panel lots show no real effect — the method separates signal from noise.",
                   f"<b>{fnames[-1]}</b>（最差：{levels[-1]}）是与失效关联最强的因素，而屏幕批次没有实际影响 —— "
                   "说明这个方法能区分信号和噪声。"))

    with tabs[2]:
        res = A.doe_analysis(DOE)
        st.markdown(T("A 2×2 full-factorial DOE (3 replicates + 3 center points, 200 units/run) run on the pilot line "
                      "to choose the new adhesive-cure recipe after the Line 2 finding.",
                      "在发现 2号线问题后，于试产线上做了 2×2 全因子 DOE（3 次重复 + 3 个中心点，每次 200 台），"
                      "用来确定新的胶水固化配方。"))
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(T("Main & interaction effects", "主效应与交互效应"))
            eff = pd.Series(res["effects"])
            if ZH:
                eff.index = [k.replace("Cure temp", "固化温度").replace("Cure time", "固化时间").replace("min", "分钟")
                             .replace("Temp × Time interaction", "温度 × 时间交互") for k in eff.index]
            fig = go.Figure(go.Bar(y=eff.index, x=eff.values, orientation="h",
                                   marker_color=[FAIL if v < 0 else PASS for v in eff.values],
                                   text=[f"{v:+.1f} {T('pts', '个百分点')}" for v in eff.values], textposition="outside",
                                   cliponaxis=False, textfont=dict(size=15),
                                   hovertemplate="%{y}: %{x:+.2f} pts<extra></extra>"))
            fig.add_vline(x=0, line=dict(color="#0b0b0b", width=1))
            fig.update_xaxes(title=T("Effect on display-attach yield (pts)", "对屏幕贴合良率的影响（百分点）"),
                             range=[min(eff.min(), 0) * 1.6, max(eff.max(), 0) * 1.8])
            show(style_fig(fig, 320, legend=False))
            sig = (eff.abs() > 2 * res["se"]).all()
            st.caption(T(f"Noise band (±2 SE from replicates): ±{2 * res['se']:.1f} pts — "
                         + ("all three effects are real." if sig else "effects inside this band are not significant."),
                         f"噪声带（基于重复试验的 ±2 SE）：±{2 * res['se']:.1f} 个百分点 —— "
                         + ("三个效应都是真实的。" if sig else "落在噪声带内的效应不显著。")))
        with c2:
            st.subheader(T("Interaction plot", "交互作用图"))
            cells = res["cells"]
            fig = go.Figure()
            for i, (tm, g) in enumerate(cells.groupby("cure_time_min")):
                fig.add_trace(go.Scatter(x=g["cure_temp_c"], y=g["display_attach_yield_pct"], mode="lines+markers",
                                         name=T(f"{tm:g} min cure", f"固化 {tm:g} 分钟"), line=dict(width=3, color=[BEFORE, AFTER][i]),
                                         marker=dict(size=11),
                                         hovertemplate="%{x} °C: %{y:.1f}%<extra>" + f"{tm:g} min</extra>"))
            fig.update_xaxes(title=T("Cure temperature (°C)", "固化温度 (°C)"), tickvals=sorted(cells["cure_temp_c"].unique()))
            fig.update_yaxes(title=T("Display-attach yield (%)", "屏幕贴合良率 (%)"))
            show(style_fig(fig, 320))
        b = res["best"]
        st.success(T(f"**Recommended setting: {b['cure_temp_c']:g} °C for {b['cure_time_min']:g} min** → "
                     f"{b['display_attach_yield_pct']:.1f}% display-attach yield (adopted as the week-5 recipe).",
                     f"**推荐设置：{b['cure_temp_c']:g} °C，{b['cure_time_min']:g} 分钟** → 屏幕贴合良率 "
                     f"{b['display_attach_yield_pct']:.1f}%（已作为第 5 周的新配方采用）。"))
        takeaway(T("Higher cure temperature is the dominant <i>negative</i> effect, and longer cure time helps mainly at "
                   "low temperature (non-parallel lines = interaction). Lower temp + longer time is the robust setting.",
                   "提高固化温度是最主要的<i>负面</i>效应；延长固化时间主要在低温下有帮助（两条线不平行 = 存在交互）。"
                   "低温 + 长时间是稳健的设置。"))

    with tabs[3]:
        st.markdown(T("Ask a question in plain English. Answers are computed from the data with rule-based intent "
                      "matching — **no API key or internet needed**. Add “week N” to scope a question.",
                      "用中文或英文提问。答案由基于规则的意图匹配直接从数据中计算 —— **无需 API key 或网络**。"
                      "加上“第 N 周”可以限定范围。"))
        def _ask(question):
            st.session_state["qa_input"] = question
        cols = st.columns(4)
        for i, q in enumerate(A.EXAMPLE_QUESTIONS[LANG]):
            cols[i % 4].button(q, key=f"ex{i}_{LANG}", width="stretch", on_click=_ask, args=(q,))
        q = st.text_input(T("Your question", "你的问题"), key="qa_input",
                          placeholder=T("e.g. Which line has the lowest yield in week 4?", "例如：第 4 周哪条产线良率最低？"))
        if q:
            st.markdown(f'<div class="hint" style="border-left-color:#2a78d6">{md_html(A.answer_question(q, DATA, LANG))}</div>',
                        unsafe_allow_html=True)


def page_program():
    st.title(T("Program view — taking the tool from demo to deployment", "项目视图 — 从演示走向落地"))
    banner()
    st.markdown(T("How I would run this as a cross-functional program: who uses it, what it connects to, how it rolls out, "
                  "and how we'd know it's working.",
                  "如果把它作为一个跨职能项目来推动：谁在用、接哪些数据、如何分阶段上线、以及如何衡量是否成功。"))
    c1, c2, c3 = st.columns(3)
    c1.markdown(T("""<div class="card"><h4>👥 Users & their question</h4>
<b>Factory / process engineers</b> — <i>Which station, line, parameter is hurting yield right now?</i><br><br>
<b>Quality & SQE</b> — <i>Is this a supplier-lot escape? Is the CAPA holding?</i><br><br>
<b>Supplier management</b> — <i>Which supplier needs an 8D, with evidence?</i><br><br>
<b>Ops / program leads</b> — <i>Are we on the yield-ramp plan for the next build gate?</i></div>""",
                  """<div class="card"><h4>👥 用户与他们关心的问题</h4>
<b>工厂 / 工艺工程师</b> — <i>现在是哪个工站、哪条线、哪个参数在拖累良率？</i><br><br>
<b>质量 & SQE</b> — <i>这是供应商批次逃逸吗？CAPA 有没有保持住？</i><br><br>
<b>供应商管理</b> — <i>哪个供应商需要做 8D？证据是什么？</i><br><br>
<b>运营 / 项目负责人</b> — <i>我们能按良率爬坡计划通过下一个阶段关口吗？</i></div>"""), unsafe_allow_html=True)
    c2.markdown(T("""<div class="card"><h4>🔌 Data sources</h4>
<b>MES</b> — unit genealogy: serial → line, shift, timestamps, station route<br><br>
<b>Test logs</b> — pass/fail, retest count, failure codes, measurements<br><br>
<b>Process / equipment data</b> — oven temp, cure time, screwdriver torque<br><br>
<b>Supplier data</b> — component lot, incoming inspection (IQC)<br><br>
<b>CAPA / 8D tracker</b> — fix events used to annotate trends</div>""",
                  """<div class="card"><h4>🔌 数据来源</h4>
<b>MES</b> — 产品履历：序列号 → 产线、班次、时间戳、工站路径<br><br>
<b>测试日志</b> — 通过/失败、复测次数、失效代码、测量值<br><br>
<b>工艺 / 设备数据</b> — 烤炉温度、固化时间、电批扭矩<br><br>
<b>供应商数据</b> — 物料批次、来料检验 (IQC)<br><br>
<b>CAPA / 8D 跟踪</b> — 用于在趋势图上标注的改进事件</div>"""), unsafe_allow_html=True)
    c3.markdown(T("""<div class="card"><h4>⚠️ Key risks & mitigations</h4>
<b>Data quality / genealogy gaps</b> → schema contract with CM; daily completeness checks<br><br>
<b>CM data-sharing constraints</b> → agree data scope & access in the supply agreement early<br><br>
<b>False alarms → alarm fatigue</b> → tune σ thresholds in pilot; humans confirm before action<br><br>
<b>Correlation ≠ causation</b> → hints trigger DOE / failure analysis, never auto-action<br><br>
<b>Adoption</b> → embed in existing daily yield review, not a new meeting</div>""",
                  """<div class="card"><h4>⚠️ 主要风险与应对</h4>
<b>数据质量 / 履历缺失</b> → 与代工厂约定数据格式；每日完整性检查<br><br>
<b>代工厂数据共享限制</b> → 尽早在供货协议中约定数据范围与权限<br><br>
<b>误报 → 报警疲劳</b> → 在试点阶段调优 σ 阈值；行动前由人确认<br><br>
<b>相关 ≠ 因果</b> → 提示只触发 DOE / 失效分析，绝不自动执行<br><br>
<b>推广使用</b> → 嵌入现有的每日良率例会，而不是新开会议</div>"""), unsafe_allow_html=True)

    st.subheader(T("Rollout plan", "上线计划"))
    phases = [
        (T("1 · Pilot line", "1 · 试点产线"), 0, 6, AFTER,
         T("1 line at 1 CM. Validate MES/test-log pipeline; compare tool alarms with manual failure analysis.",
           "1 家代工厂的 1 条产线。验证 MES/测试日志数据管道；将工具报警与人工失效分析对比。"),
         T("Exit: data completeness ≥ 98%, alarm precision ≥ 70%", "出口标准：数据完整性 ≥ 98%，报警准确率 ≥ 70%")),
        (T("2 · All lines", "2 · 全部产线"), 6, 14, "#6250d6",
         T("All lines at the CM. Daily yield review runs on the tool; SPC alarms routed to line owners.",
           "该代工厂所有产线。每日良率例会基于工具进行；SPC 报警推送给产线负责人。"),
         T("Exit: used in every daily review; time-to-root-cause < 3 days", "出口标准：每次例会都在使用；根因定位时间 < 3 天")),
        (T("3 · New suppliers / CMs", "3 · 新供应商 / 代工厂"), 14, 26, "#1baf7a",
         T("Onboard the next CM and key component suppliers; supplier-lot views for SQE.",
           "接入下一家代工厂和关键物料供应商；为 SQE 提供供应商批次视图。"),
         T("Exit: new CM live within 2 weeks of first build", "出口标准：新代工厂在首次生产后 2 周内上线")),
    ]
    fig = go.Figure()
    for name, s0, s1, col, _, _ in phases:
        wk_txt = T(f"weeks {s0}–{s1}", f"第 {s0}–{s1} 周")
        fig.add_trace(go.Bar(y=[name], x=[s1 - s0], base=[s0], orientation="h", marker_color=col,
                             text=wk_txt, textposition="inside", insidetextanchor="middle",
                             textfont=dict(color="#ffffff", size=15),
                             hovertemplate=f"{name}<br>{wk_txt}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=15))
    fig.update_xaxes(title=T("Weeks from kickoff", "项目启动后的周数"), dtick=2)
    show(style_fig(fig, 220, legend=False))
    cols = st.columns(3)
    for c, (name, _, _, col, detail, gate) in zip(cols, phases):
        c.markdown(f'<div class="card" style="border-top:4px solid {col}"><h4>{name}</h4>{detail}'
                   f'<br><br><b>{gate}</b></div>', unsafe_allow_html=True)
    st.write("")

    st.subheader(T("Success metrics", "成功指标"))
    trend = get_trend()
    y0, y1 = pct(trend["final_yield"].iloc[0], 0), pct(trend["final_yield"].iloc[-1], 0)
    d0, d1 = trend["dppm"].iloc[0], trend["dppm"].iloc[-1]
    drop = (1 - d1 / d0) * 100
    cols_ = [T("Metric", "指标"), T("Baseline", "基线"), T("Target", "目标"), T("Simulated result", "模拟结果")]
    rows = [
        (T("Time to root cause", "根因定位时间"), T("~2–3 weeks (manual pivot tables, FA queue)", "约 2–3 周（手工透视表、排队等失效分析）"),
         T("< 3 days from first SPC / anomaly signal", "从首个 SPC/异常信号起 < 3 天"),
         T("SPC flags Line 2 drift in W2; fix in W5", "SPC 在 W2 标记 2号线漂移；W5 修复")),
        (T("Yield ramp speed", "良率爬坡速度"), T("Weeks to reach 90% final yield", "达到 90% 最终良率所需周数"),
         T("≥ 90% by start of mass-production ramp", "量产爬坡开始前 ≥ 90%"),
         T(f"{y0} → {y1} in 12 weeks", f"12 周内 {y0} → {y1}")),
        (T("DPPM (station fails)", "DPPM（工站失效）"), f"{d0:,.0f} (W1)", T("−80% by Ramp", "量产爬坡前降低 80%"),
         T(f"{d1:,.0f} (W12), {drop:.0f}% lower", f"{d1:,.0f}（W12），降低 {drop:.0f}%")),
        (T("Retest rate", "复测率"), pct(trend["retest_rate"].iloc[0]), "< 3%", pct(trend["retest_rate"].iloc[-1])),
        (T("Adoption", "使用率"), "—",
         T("Used in 100% of daily yield reviews; ≥ 80% of CAPAs cite tool evidence", "100% 的每日良率例会使用；≥ 80% 的 CAPA 引用工具证据"),
         T("n/a (demo)", "不适用（演示）")),
    ]
    st.table(pd.DataFrame(rows, columns=cols_).set_index(cols_[0]))
    takeaway(T("The tool's value is measured in <b>days to root cause</b> and <b>weeks to yield target</b> — "
               "not in dashboards built.",
               "这个工具的价值用<b>定位根因所需的天数</b>和<b>达到良率目标所需的周数</b>来衡量 —— 而不是做了多少看板。"))


# --------------------------------------------------------------------------- navigation
# DEMO_START_PAGE (env var) chooses the landing page, e.g. DEMO_START_PAGE=ai-insights; also used by tests.
_START = os.environ.get("DEMO_START_PAGE", "overview")
_PAGES = [(page_overview, T("Overview", "总览"), "📊", "overview"),
          (page_drilldown, T("Drill-down", "下钻分析"), "🔎", "drilldown"),
          (page_pareto, T("Defect Pareto", "缺陷柏拉图"), "📉", "pareto"), (page_spc, "SPC", "📏", "spc"),
          (page_ai, T("AI Insights", "AI 洞察"), "🤖", "ai-insights"),
          (page_program, T("Program view", "项目视图"), "🗺️", "program")]
pg = st.navigation([st.Page(f, title=t, icon=i, url_path=u, default=(u == _START)) for f, t, i, u in _PAGES])
with st.sidebar:
    st.markdown(T("### Product X · Yield Analytics", "### 产品 X · 良率分析"))
    st.caption(T("Final assembly + test · 3 lines · 2 shifts · 6 stations · 12 weeks (EVT → DVT → PVT → Ramp)",
                 "总装 + 测试 · 3 条产线 · 2 个班次 · 6 个工站 · 12 周（EVT → DVT → PVT → 量产爬坡）"))
    st.markdown('<div class="sim-banner">' + T("Simulated data – for demonstration only", "模拟数据 – 仅用于演示")
                + '</div>', unsafe_allow_html=True)
    st.caption(T(f"{len(UNITS):,} units · {len(SR):,} station records", f"{len(UNITS):,} 台 · {len(SR):,} 条工站记录"))
pg.run()
