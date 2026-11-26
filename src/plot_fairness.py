"""Create editable Matplotlib figures from saved baseline and fairness reports.

Run: python src/plot_fairness.py
Use --show to open the figures after saving, or edit STYLE and TARGETS below.
No optimizer runs are performed. Rates in the first group come from the
original saved baseline, not the rebalanced throughput-optimal reference.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]

# Edit these settings to change the appearance and selected experiments.
STYLE = {
    "two_day": "#E69F00",
    "standard": "#2855A6",
    "points": "#233C64",
    "threshold": "#737C87",
    "infeasible": "#F9DFDA",
    "infeasible_edge": "#B44738",
    "text": "#202C40",
    "grid": "#E4E7EC",
}
TARGETS = (0.75, 0.78, 0.80, 0.82)  # Deliberately exclude 85%.
SERVICE_TARGET = 0.80
OPTIONS = (("two_day", "Two-Day"), ("standard", "Standard"))
FORMATS = ("png", "pdf", "svg")
FONT_DIRECTORY = ROOT / "assets" / "fonts"
FONT_FAMILY = "Nimbus Sans"  # Helvetica-compatible family used for LaTeX-style text.


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def load_data(baseline_dir, fairness_dir):
    totals = defaultdict(lambda: [0.0, 0])
    for row in read_rows(baseline_dir / "decisions.csv"):
        values = totals[row["ship_option"]]
        values[0] += float(row["demand"])
        values[1] += int(row["accepted"])
    baseline_rates = {s: totals[s][1] / totals[s][0] for s, _ in OPTIONS}
    original_total = sum(values[1] for values in totals.values())
    summary = read_rows(fairness_dir / "fairness_summary.csv")
    fair_rates = {}
    fair_total = None
    for row in summary:
        if row["minimum_required_rate"] and abs(
            float(row["minimum_required_rate"]) - SERVICE_TARGET
        ) < 1e-9:
            if row["status"] != "optimal":
                raise ValueError("The selected service-floor case is not optimal")
            fair_total = int(row["accepted"])
    for row in read_rows(fairness_dir / "option_acceptance.csv"):
        if row["minimum_required_rate"] and abs(
            float(row["minimum_required_rate"]) - SERVICE_TARGET
        ) < 1e-9:
            if row["status"] != "optimal":
                raise ValueError("The selected service-floor case is not optimal")
            s = row["ship_option"]
            if s in totals and float(row["demand"]) != totals[s][0]:
                raise ValueError("Baseline and fairness demand totals do not match")
            fair_rates[s] = float(row["acceptance_rate"])
    if fair_total is None or any(s not in fair_rates for s, _ in OPTIONS):
        raise ValueError("The selected service-floor reports are missing")
    selected = []
    for target in TARGETS:
        matches = [r for r in summary if r["minimum_required_rate"] and
                   abs(float(r["minimum_required_rate"]) - target) < 1e-9]
        if len(matches) != 1:
            raise ValueError(f"Expected one summary row for service target {target}")
        if matches[0]["status"] not in ("optimal", "infeasible"):
            raise ValueError(f"Unexpected solver status for target {target}")
        selected.append(matches[0])
    # Check that both comparisons have the same capacity and buffer.
    original_limits = {r["locker_id"]: (float(r["capacity"]), float(r["alpha"]))
                       for r in read_rows(baseline_dir / "daily_occupancy.csv")}
    selected_case = next(r["case"] for r in selected
                         if abs(float(r["minimum_required_rate"]) - SERVICE_TARGET) < 1e-9)
    fair_limits = {r["locker_id"]: (float(r["capacity"]), float(r["alpha"]))
                   for r in read_rows(fairness_dir / selected_case / "daily_occupancy.csv")}
    if original_limits != fair_limits:
        raise ValueError("Baseline and fairness capacities or alpha differ")
    return baseline_rates, fair_rates, original_total, fair_total, selected


def style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#BEC4CD")
    ax.tick_params(axis="both", length=0, pad=8)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=STYLE["grid"], linewidth=0.8)


def plot_acceptance(ax, baseline, fair, original_total, fair_total):
    width = 0.28
    for offset, (option, label) in zip((-width / 2, width / 2), OPTIONS):
        bars = ax.bar(
            [offset, 1 + offset],
            [100 * baseline[option], 100 * fair[option]],
            width=width, color=STYLE[option], label=label, zorder=3,
        )
        ax.bar_label(bars, fmt="%.2f%%", padding=6, fontsize=11, fontweight="bold",
                     bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
    ax.axhline(100 * SERVICE_TARGET, color=STYLE["threshold"],
               linestyle=(0, (5, 4)), linewidth=1.2, zorder=2)
    handles, labels = ax.get_legend_handles_labels()
    handles.append(Line2D([0], [0], color=STYLE["threshold"],
                          linestyle="--", linewidth=1.2))
    labels.append(f"{SERVICE_TARGET:.0%} minimum")
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.13),
              ncol=3, frameon=False, fontsize=10, handlelength=1.5, columnspacing=1.2)
    ax.set_xticks([0, 1], [f"Original saved optimum\n{original_total} accepted",
                           f"{SERVICE_TARGET:.0%} minimum\n{fair_total} accepted"])
    ax.set_ylim(0, 103)
    ax.set_xlim(-0.5, 1.5)
    ax.set_yticks(range(0, 101, 20))
    ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.set_ylabel("Acceptance rate")
    style_axes(ax)


def plot_tradeoff(ax, rows, original_total):
    feasible = [r for r in rows if r["status"] == "optimal"]
    infeasible = [r for r in rows if r["status"] == "infeasible"]
    x = [100 * float(r["minimum_required_rate"]) for r in feasible]
    y = [int(r["accepted"]) for r in feasible]
    ax.scatter(x, y, s=95, color=STYLE["points"], zorder=4)
    for xx, yy in zip(x, y):
        ax.annotate(str(yy), (xx, yy), xytext=(0, 12),
                    textcoords="offset points", ha="center", fontweight="bold")
    for row in infeasible:
        xx = 100 * float(row["minimum_required_rate"])
        ax.axvspan(xx - 0.6, xx + 0.6, facecolor=STYLE["infeasible"],
                   edgecolor=STYLE["infeasible_edge"], hatch="///",
                   linewidth=1.0, zorder=0)
        # Axis-relative text has no numerical throughput value: infeasible != 0.
        ax.text(xx, 0.52, "Infeasible", transform=ax.get_xaxis_transform(),
                ha="center", va="center", rotation=90,
                color=STYLE["infeasible_edge"], fontsize=13, fontweight="bold",
                bbox={"facecolor": STYLE["infeasible"], "edgecolor": "none", "pad": 5})
    ax.set_xticks([100 * target for target in TARGETS],
                  [f"{100 * target:.0f}%" for target in TARGETS])
    ax.set_xlim(min(100 * t for t in TARGETS) - 0.7,
                max(100 * t for t in TARGETS) + 0.8)
    # A narrow, explicitly labelled scale exposes the two-package difference.
    ax.set_ylim(min(y) - 1, max(y) + 1)
    ax.set_yticks(range(min(y) - 1, max(y) + 2))
    ax.set_xlabel("Minimum acceptance rate required for each option", labelpad=12)
    ax.set_ylabel("Total packages accepted")
    style_axes(ax)


def save_figure(fig, output_dir, name):
    for extension in FORMATS:
        fig.savefig(output_dir / f"{name}.{extension}", dpi=300,
                    bbox_inches="tight", facecolor="white")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, default=ROOT / "reports" / "base")
    parser.add_argument("--fairness-dir", type=Path, default=ROOT / "reports" / "fairness")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "fairness" / "figures")
    parser.add_argument("--show", action="store_true", help="Open figures for interactive editing")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fonts = list(FONT_DIRECTORY.glob("NimbusSans-*.otf"))
    if not fonts:
        raise FileNotFoundError(f"Matching poster fonts are missing from {FONT_DIRECTORY}")
    for font in fonts:
        font_manager.fontManager.addfont(font)
    plt.rcParams.update({
        "font.family": FONT_FAMILY, "font.size": 11,
        "text.color": STYLE["text"], "axes.labelcolor": STYLE["text"],
        "xtick.color": STYLE["text"], "ytick.color": STYLE["text"],
        "pdf.fonttype": 42, "svg.fonttype": "none",
    })
    baseline, fair, original_total, fair_total, rows = load_data(
        args.baseline_dir, args.fairness_dir
    )
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.0))
    plot_acceptance(axes[0], baseline, fair, original_total, fair_total)
    plot_tradeoff(axes[1], rows, original_total)
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.22, top=0.84, wspace=0.30)
    fig.text(0.065, 0.035, "46 slots per locker | Safety factor 0.9 | 909 requests | "
             "Infeasible targets have no throughput value", fontsize=10, color="#68717E")
    save_figure(fig, args.output_dir, "fairness_comparison")
    # Also save separate panels for flexible placement on a poster.
    for name, callback in (
        ("acceptance_rates", lambda ax: plot_acceptance(ax, baseline, fair, original_total, fair_total)),
        ("service_tradeoff", lambda ax: plot_tradeoff(ax, rows, original_total)),
    ):
        panel, ax = plt.subplots(figsize=(7.2, 6.0))
        callback(ax)
        panel.subplots_adjust(left=0.13, right=0.97, bottom=0.22,
                              top=0.95 if name == "service_tradeoff" else 0.84)
        save_figure(panel, args.output_dir, name)
    print(f"Figures saved to {args.output_dir}")
    if args.show:
        plt.show()
    plt.close("all")


if __name__ == "__main__":
    main()
