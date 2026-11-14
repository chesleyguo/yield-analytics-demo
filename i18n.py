"""English / Chinese (中文) display translations.

Data values (station names, lines, shifts, defect codes, lot IDs) stay in English
inside the data; these helpers translate them only for display.
"""
from __future__ import annotations

import re

LANGS = {"en": "English", "zh": "中文"}

STATION_ZH = {
    "SMT / Board Test": "SMT / 板测",
    "Display Attach": "屏幕贴合",
    "Enclosure Assembly": "外壳组装",
    "Keyboard / Trackpad": "键盘 / 触控板",
    "Functional Test": "功能测试",
    "Cosmetic Inspection": "外观检验",
}
SHIFT_ZH = {"Day": "白班", "Night": "夜班"}
PHASE_ZH = {"EVT": "EVT", "DVT": "DVT", "PVT": "PVT", "Ramp": "量产爬坡"}
SPEC_LABEL_ZH = {
    "cure_temp_c": "胶水固化温度 (°C)",
    "cure_time_min": "胶水固化时间 (分钟)",
    "screw_torque_kgfcm": "螺丝扭矩 (kgf·cm)",
}
FACTOR_ZH = {
    "Keyboard lot": "键盘批次", "Cure temp band": "固化温度区间", "Shift": "班次",
    "Assembly line": "产线", "Keyboard supplier": "键盘供应商", "Display lot": "屏幕批次",
    "Screw torque band": "螺丝扭矩区间",
}
WE_RULES_ZH = {
    1: "1 个点超出 3σ",
    2: "连续 3 点中有 2 点超出 2σ（同侧）",
    3: "连续 5 点中有 4 点超出 1σ（同侧）",
    4: "连续 8 点落在中心线同一侧",
}
FIX_SHORT_ZH = {5: "烤炉修复（2号线）", 7: "批次隔离", 9: "夜班培训"}
FIX_TITLE_ZH = {
    5: "2号线固化烤炉重新校准；采用 DOE 配方 80°C / 25 分钟",
    7: "隔离键盘批次 KB-B-3104；向供应商发起 8D",
    9: "夜班搬运操作再培训 + 外观限度样品",
}
FIX_OWNER_ZH = {5: "工艺工程", 7: "SQE / 供应商管理", 9: "制造运营 / 质量"}


def station(name: str, lang: str) -> str:
    return STATION_ZH.get(name, name) if lang == "zh" else name


def line(name: str, lang: str) -> str:
    """'Line 2' -> '2号线'."""
    if lang != "zh":
        return name
    m = re.fullmatch(r"Line (\d+)", str(name))
    return f"{m.group(1)}号线" if m else name


def shift(name: str, lang: str) -> str:
    return SHIFT_ZH.get(name, name) if lang == "zh" else name


def phase(name: str, lang: str) -> str:
    return PHASE_ZH.get(name, name) if lang == "zh" else name


def text(s: str, lang: str) -> str:
    """Translate free text built from known English terms (entities, conditions, levels)."""
    if lang != "zh" or not isinstance(s, str):
        return s
    for en, zh in sorted(STATION_ZH.items(), key=lambda kv: -len(kv[0])):
        s = s.replace(en, zh)
    reps = [
        (r"\(keyboard station\)", "（键盘工站）"),
        (r"Night shift", "夜班"), (r"Day shift", "白班"),
        (r"night shift", "夜班"), (r"day shift", "白班"),
        (r"\bNight\b", "夜班"), (r"\bDay\b", "白班"),
        (r"Week (\d+)", r"第\1周"),
        (r"Line (\d+)", r"\1号线"),
        (r"keyboard lot ", "键盘批次 "), (r"display lot ", "屏幕批次 "),
        (r"cure temp", "固化温度"), (r"cure time", "固化时间"), (r"screw torque", "螺丝扭矩"),
        (r"\(above USL\)", "（超上限）"), (r"out of spec", "超规格"), (r"in spec", "规格内"),
        (r"\bmin\b", "分钟"),
        (r"\bMon\b", "周一"), (r"\bTue\b", "周二"), (r"\bWed\b", "周三"), (r"\bThu\b", "周四"),
        (r"\bFri\b", "周五"), (r"\bSat\b", "周六"),
    ]
    for pat, rep in reps:
        s = re.sub(pat, rep, s)
    return s
