#!/usr/bin/env python3
"""Generate vector PDF charts for poster.tex from project CSV reports."""

import csv
from pathlib import Path
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Rect, String, Line, PolyLine, Circle
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parents[1]
REPORTS, DATA = ROOT / "reports", ROOT / "data"
OUT = Path(__file__).resolve().parent / "images"
OUT.mkdir(parents=True, exist_ok=True)
NAVY, BLUE = colors.HexColor("#071F45"), colors.HexColor("#2446A6")
ORANGE, RED = colors.HexColor("#FF9900"), colors.HexColor("#D95D55")
PALE, GRID = colors.HexColor("#DCE8F8"), colors.HexColor("#D8DEE8")
TEAL, PURPLE = colors.HexColor("#00A6A6"), colors.HexColor("#7D5BA6")


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save(d, name):
    renderPDF.drawToFile(d, str(OUT / name))


def text(d, x, y, value, size=8, bold=False, color=colors.HexColor("#17243B")):
    d.add(String(x, y, value, fontName="Helvetica-Bold" if bold else "Helvetica",
                 fontSize=size, fillColor=color))


def scenario_chart():
    cases = [("23 slots", "capacity_23"), ("46 slots", "base"),
             ("69 slots", "capacity_69"), ("Pickup +1 day", "slower_pickups")]
    values = []
    for label, folder in cases:
        r = read(REPORTS / folder / "locker_summary.csv")
        a = sum(int(x["accepted"]) for x in r)
        j = round(sum(float(x["rejected"]) for x in r))
        values.append((label, a, j))
    d = Drawing(560, 245)
    text(d, 25, 220, "Accepted and rejected package requests", 14, True, NAVY)
    for i, (label, a, j) in enumerate(values):
        y = 175 - i * 42
        text(d, 25, y + 6, label, 9)
        width = 390
        d.add(Rect(125, y, width * a / 909, 20, fillColor=BLUE, strokeColor=None))
        d.add(Rect(125 + width * a / 909, y, width * j / 909, 20,
                   fillColor=RED, strokeColor=None))
        text(d, 522, y + 6, f"{100*a/909:.1f}%", 9, True, NAVY)
    d.add(Rect(340, 220, 10, 8, fillColor=BLUE, strokeColor=None))
    text(d, 355, 220, "Accepted", 8)
    d.add(Rect(425, 220, 10, 8, fillColor=RED, strokeColor=None))
    text(d, 440, 220, "Rejected", 8)
    save(d, "scenario_comparison.pdf")


def occupancy_chart():
    r = read(REPORTS / "base" / "daily_occupancy.csv")
    lockers = [("hopkins", "Hopkins", BLUE), ("caleido", "Caleido", ORANGE),
               ("enara", "Enara", TEAL), ("alcala_norte", "Alcala Norte", PURPLE)]
    d = Drawing(560, 255)
    text(d, 40, 230, "Baseline expected occupancy by day", 14, True, NAVY)
    x0, y0, w, h = 55, 40, 430, 165
    for level in range(30, 49, 3):
        y = y0 + (level - 30) / 18 * h
        d.add(Line(x0, y, x0 + w, y, strokeColor=GRID, strokeWidth=.5))
        text(d, 28, y - 3, str(level), 7)
    for day in range(1, 8):
        x = x0 + (day - 1) / 6 * w
        text(d, x - 2, 25, str(day), 7)
    for key, label, color in lockers:
        vals = sorted((int(x["day"]), float(x["expected_occupancy"]))
                      for x in r if x["locker_id"] == key)
        pts = []
        for day, value in vals:
            x = x0 + (day - 1) / 6 * w
            y = y0 + (value - 30) / 18 * h
            pts.extend([x, y])
            d.add(Circle(x, y, 2.5, fillColor=color, strokeColor=color))
        d.add(PolyLine(pts, strokeColor=color, strokeWidth=2))
    cap_y = y0 + 16 / 18 * h
    d.add(Line(x0, cap_y, x0 + w, cap_y, strokeColor=RED, strokeWidth=1.5))
    for i, (_, label, color) in enumerate(lockers + [("", "Capacity", RED)]):
        x = 55 + (i % 3) * 150
        y = 216 - (i // 3) * 12
        d.add(Rect(x, y, 9, 3, fillColor=color, strokeColor=None))
        text(d, x + 13, y - 2, label, 7.5)
    text(d, 235, 10, "Planning day", 8)
    save(d, "baseline_occupancy.pdf")


def locker_chart():
    r = read(REPORTS / "base" / "locker_summary.csv")
    labels = ["Hopkins", "Caleido", "Enara", "Alcala Norte"]
    d = Drawing(560, 235)
    text(d, 35, 212, "Baseline demand and accepted packages by locker", 14, True, NAVY)
    x0, y0, h = 65, 35, 155
    for level in range(0, 251, 50):
        y = y0 + level / 250 * h
        d.add(Line(x0, y, 500, y, strokeColor=GRID, strokeWidth=.5))
        text(d, 35, y - 3, str(level), 7)
    for i, row in enumerate(r):
        x = 95 + i * 100
        demand, accepted = float(row["demand"]), float(row["accepted"])
        d.add(Rect(x, y0, 28, demand / 250 * h, fillColor=PALE, strokeColor=None))
        d.add(Rect(x + 31, y0, 28, accepted / 250 * h, fillColor=BLUE, strokeColor=None))
        text(d, x - 2, 20, labels[i], 7.5)
    d.add(Rect(350, 212, 10, 8, fillColor=PALE, strokeColor=None))
    text(d, 364, 212, "Demand", 8)
    d.add(Rect(420, 212, 10, 8, fillColor=BLUE, strokeColor=None))
    text(d, 434, 212, "Accepted", 8)
    save(d, "locker_performance.pdf")


def dwell_chart():
    r = read(DATA / "occupancy.csv")
    d = Drawing(520, 205)
    text(d, 35, 182, "Probability that a package still occupies a slot", 13, True, NAVY)
    x0, y0, w, h = 55, 35, 390, 125
    for level in range(0, 101, 25):
        y = y0 + level / 100 * h
        d.add(Line(x0, y, x0 + w, y, strokeColor=GRID, strokeWidth=.5))
        text(d, 28, y - 3, str(level), 7)
    for field, color, label in [("two_day", BLUE, "Two-Day"),
                                ("standard", ORANGE, "Standard")]:
        pts = []
        for row in r:
            day = int(row["days_since_arrival"])
            val = 100 * float(row[field])
            x = x0 + day / 3 * w
            y = y0 + val / 100 * h
            pts.extend([x, y])
            d.add(Circle(x, y, 3, fillColor=color, strokeColor=color))
            text(d, x - 2, 20, str(day), 7)
        d.add(PolyLine(pts, strokeColor=color, strokeWidth=2.5))
    d.add(Rect(335, 182, 10, 3, fillColor=BLUE, strokeColor=None))
    text(d, 350, 179, "Two-Day", 8)
    d.add(Rect(415, 182, 10, 3, fillColor=ORANGE, strokeColor=None))
    text(d, 430, 179, "Standard", 8)
    text(d, 205, 8, "Days since arrival", 8)
    save(d, "dwell_probabilities.pdf")


if __name__ == "__main__":
    scenario_chart()
    occupancy_chart()
    locker_chart()
    dwell_chart()
    print(f"Figures written to {OUT}")