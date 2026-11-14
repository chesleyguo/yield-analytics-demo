"""Headless smoke test: every page and key interaction renders without exceptions,
and the AI Insights page surfaces all three embedded root causes.

Run:  python tests/smoke_test.py
"""
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
failures = []


def check(at, label):
    errs = [e.value for e in at.exception]
    print(f"{'FAIL' if errs else 'ok  '}  {label}")
    if errs:
        failures.append((label, errs))


def page_radio(at):
    """The page's own radio (not the sidebar language switch)."""
    return next(r for r in at.radio if "Language" not in r.label)


def open_page(slug, lang):
    os.environ["DEMO_START_PAGE"] = slug
    os.environ["DEMO_LANG"] = lang
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    return t


EXPECTED = {
    "en": {"Line 2 cure-temp drift": ("DSP-ADHESIVE-DELAM", "cure temp >", "Line 2"),
           "Bad keyboard lot": ("KB-KEY-STICK", "KB-B-3104"),
           "Night-shift cosmetic": ("COS-SCRATCH", "night shift")},
    "zh": {"Line 2 cure-temp drift": ("DSP-ADHESIVE-DELAM", "固化温度 >", "2号线"),
           "Bad keyboard lot": ("KB-KEY-STICK", "KB-B-3104"),
           "Night-shift cosmetic": ("COS-SCRATCH", "夜班")},
}
QUESTIONS = {"en": ["Which line has the lowest yield in week 4?", "What fixes were made?"],
             "zh": ["第4周哪条产线良率最低？", "做了哪些改进措施？"]}

for lang in ["en", "zh"]:
    print(f"\n=== {lang} ===")
    at = open_page("overview", lang); check(at, "Overview")

    at = open_page("drilldown", lang); check(at, "Drill-down / Station")
    dims = {"en": ["Line", "Shift", "Supplier lot", "Phase"], "zh": ["产线", "班次", "供应商批次", "阶段"]}[lang]
    for dim in dims:
        page_radio(at).set_value(dim).run(); check(at, f"Drill-down / {dim}")

    at = open_page("pareto", lang); check(at, "Pareto / single period")
    page_radio(at).set_value({"en": "Before vs after fixes", "zh": "改进前 vs 改进后"}[lang]).run(); check(at, "Pareto / before vs after")

    at = open_page("spc", lang); check(at, "SPC / cure temp, Line 2")
    for param in ["cure_time_min", "screw_torque_kgfcm"]:
        for line in ["Line 1", "Line 3"]:
            at.selectbox[0].set_value(param); at.selectbox[1].set_value(line).run()
            check(at, f"SPC / {param}, {line}")

    at = open_page("ai-insights", lang); check(at, "AI Insights")
    html = " ".join(m.value for m in at.markdown)
    for name, needles in EXPECTED[lang].items():
        found = any(all(n in seg for n in needles) for seg in html.split('<div class="hint">'))
        print(f"{'ok  ' if found else 'FAIL'}  Root cause detected: {name}")
        if not found:
            failures.append((lang, name, "not detected"))
    for q in QUESTIONS[lang]:
        at.text_input[0].set_value(q).run(); check(at, f"Q&A: {q}")
        ans = [m.value for m in at.markdown if "border-left-color:#2a78d6" in m.value]
        print("      →", ans[0][:140].split(">", 1)[-1] if ans else "NO ANSWER")
        if not ans:
            failures.append((lang, q, "no answer"))

    at = open_page("program", lang); check(at, "Program view")

print("\nALL PASSED" if not failures else f"\n{len(failures)} FAILURE(S): {failures}")
raise SystemExit(1 if failures else 0)
