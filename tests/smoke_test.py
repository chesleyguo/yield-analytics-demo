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


def open_page(slug):
    os.environ["DEMO_START_PAGE"] = slug
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    return t


at = open_page("overview"); check(at, "Overview")

at = open_page("drilldown"); check(at, "Drill-down / Station")
for dim in ["Line", "Shift", "Supplier lot", "Phase"]:
    at.radio[0].set_value(dim).run(); check(at, f"Drill-down / {dim}")

at = open_page("pareto"); check(at, "Pareto / single period")
at.radio[0].set_value("Before vs after fixes").run(); check(at, "Pareto / before vs after")

at = open_page("spc"); check(at, "SPC / cure temp, Line 2")
for param in ["cure_time_min", "screw_torque_kgfcm"]:
    for line in ["Line 1", "Line 3"]:
        at.selectbox[0].set_value(param); at.selectbox[1].set_value(line).run()
        check(at, f"SPC / {param}, {line}")

at = open_page("ai-insights"); check(at, "AI Insights")
html = " ".join(m.value for m in at.markdown)
expected = {
    "Line 2 cure-temp drift": ("DSP-ADHESIVE-DELAM", "cure temp >", "Line 2"),
    "Bad keyboard lot": ("KB-KEY-STICK", "KB-B-3104"),
    "Night-shift cosmetic": ("COS-SCRATCH", "night shift"),
}
for name, needles in expected.items():
    found = any(all(n in seg for n in needles) for seg in html.split('<div class="hint">'))
    print(f"{'ok  ' if found else 'FAIL'}  Root cause detected: {name}")
    if not found:
        failures.append((name, "not detected"))
for i, q in enumerate(["Which line has the lowest yield in week 4?", "What fixes were made?"]):
    at.text_input[0].set_value(q).run(); check(at, f"Q&A: {q}")

at = open_page("program"); check(at, "Program view")

print("\nALL PASSED" if not failures else f"\n{len(failures)} FAILURE(S): {failures}")
raise SystemExit(1 if failures else 0)
