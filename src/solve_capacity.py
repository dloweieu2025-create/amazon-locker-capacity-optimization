#!/usr/bin/env python3
"""Solve locker ship-option capacity reservations from the project CSV files."""

import argparse
import csv
import math
from pathlib import Path

import pyomo.environ as pyo
from pyomo.opt import TerminationCondition

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        data = list(reader)
        columns = reader.fieldnames or []
    if not data:
        raise ValueError(f"{path} has no data rows")
    return columns, data


def load_inputs(locker_file, demand_file, occupancy_file):
    locker_cols, locker_rows = read_csv(locker_file)
    demand_cols, demand_rows = read_csv(demand_file)
    occupancy_cols, occupancy_rows = read_csv(occupancy_file)

    if not {"locker_id", "capacity"} <= set(locker_cols):
        raise ValueError("locker.csv requires locker_id and capacity")
    if not {"locker_id", "day"} <= set(demand_cols):
        raise ValueError("demand.csv requires locker_id and day")
    if "days_since_arrival" not in occupancy_cols:
        raise ValueError("occupancy.csv requires days_since_arrival")

    options = [c for c in demand_cols if c not in {"locker_id", "day"}]
    occupancy_options = [c for c in occupancy_cols if c != "days_since_arrival"]
    if not options or set(options) != set(occupancy_options):
        raise ValueError("Ship-option columns must match in demand and occupancy")

    lockers = [r["locker_id"].strip() for r in locker_rows]
    capacity = {r["locker_id"].strip(): int(r["capacity"]) for r in locker_rows}
    days = sorted({int(r["day"]) for r in demand_rows})
    ages = sorted(int(r["days_since_arrival"]) for r in occupancy_rows)
    if len(lockers) != len(set(lockers)) or any(not l for l in lockers):
        raise ValueError("Locker IDs must be nonempty and unique")
    if any(c <= 0 for c in capacity.values()):
        raise ValueError("Locker capacities must be positive integers")
    if days != list(range(1, max(days) + 1)):
        raise ValueError("Demand days must be contiguous and start at 1")
    pairs = [(r["locker_id"].strip(), int(r["day"])) for r in demand_rows]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Each locker/day pair must occur exactly once")
    if set(pairs) != {(l, t) for l in lockers for t in days}:
        raise ValueError("Demand must contain every locker/day pair and no unknown lockers")
    if len(ages) != len(set(ages)):
        raise ValueError("Occupancy ages must be unique")
    if ages != list(range(max(ages) + 1)):
        raise ValueError("days_since_arrival must be contiguous and start at 0")

    demand = {
        (r["locker_id"].strip(), s, int(r["day"])): float(r[s])
        for r in demand_rows for s in options
    }
    occupancy = {
        (s, int(r["days_since_arrival"])): float(r[s])
        for r in occupancy_rows
        for s in options
    }
    if any(not math.isfinite(v) or v < 0 for v in demand.values()):
        raise ValueError("Demand must be finite and nonnegative")
    if any(not math.isfinite(v) or v < 0 or v > 1 for v in occupancy.values()):
        raise ValueError("Occupancy probabilities must be between 0 and 1")
    for s in options:
        if occupancy[s, 0] != 1:
            raise ValueError("Arrival-day occupancy must equal 1")
        if any(occupancy[s, a] < occupancy[s, a + 1] for a in ages[:-1]):
            raise ValueError("Occupancy probabilities must be nonincreasing with age")
    return lockers, options, days, ages, capacity, demand, occupancy


def build_model(data, alpha=1.0):
    if not math.isfinite(alpha) or not 0 < alpha <= 1:
        raise ValueError("alpha must satisfy 0 < alpha <= 1")
    lockers, options, days, ages, capacity, demand, occupancy = data
    model = pyo.ConcreteModel("locker_capacity_reservation")
    model.alpha = pyo.Param(initialize=alpha)
    model.L = pyo.Set(initialize=lockers, ordered=True)
    model.S = pyo.Set(initialize=options, ordered=True)
    model.T = pyo.Set(initialize=days, ordered=True)
    model.y = pyo.Var(model.L, model.S, model.T, domain=pyo.NonNegativeIntegers)
    model.objective = pyo.Objective(
        expr=sum(model.y[l, s, t] for l in model.L for s in model.S for t in model.T),
        sense=pyo.maximize,
    )
    max_age = max(ages)

    def reservation(m, locker, option, target):
        return sum(
            occupancy[option, target - arrival] * m.y[locker, option, arrival]
            for arrival in m.T
            if arrival <= target and target - arrival <= max_age
        )

    model.x = pyo.Expression(model.L, model.S, model.T, rule=reservation)
    model.capacity_limit = pyo.Constraint(
        model.L,
        model.T,
        rule=lambda m, l, t: sum(m.x[l, s, t] for s in m.S) <= m.alpha * capacity[l],
    )
    # Each location has its own demand; packages cannot be reassigned.
    model.demand_limit = pyo.Constraint(
        model.L,
        model.S,
        model.T,
        rule=lambda m, l, s, t: m.y[l, s, t] <= demand[l, s, t],
    )
    return model


def get_solver(requested):
    candidates = [requested] if requested != "auto" else [
        "appsi_highs", "highs", "cbc", "glpk"
    ]
    for name in candidates:
        try:
            solver = pyo.SolverFactory(name)
            if solver.available(exception_flag=False):
                return name, solver
        except Exception:
            pass
    raise RuntimeError("No solver available. Install one with: pip install highspy")


def display(model, solver_name):
    print(f"Solver: {solver_name}")
    print(f"Maximum throughput: {pyo.value(model.objective):.0f} packages")
    print("\nAccepted packages")
    print("locker,day,ship_option,accepted")
    for l in model.L:
        for t in model.T:
            for s in model.S:
                print(f"{l},{t},{s},{pyo.value(model.y[l, s, t]):.0f}")
    print("\nExpected reservations")
    print("locker,day,ship_option,expected_slots")
    for l in model.L:
        for t in model.T:
            for s in model.S:
                print(f"{l},{t},{s},{pyo.value(model.x[l, s, t]):.2f}")
    print("\nExpected total occupancy")
    print("locker,day,expected_occupied_slots")
    for l in model.L:
        for t in model.T:
            total = sum(pyo.value(model.x[l, s, t]) for s in model.S)
            print(f"{l},{t},{total:.2f}")


def scenario_inputs(data, capacity_override=None, pickup_delay=0):
    """Change capacity or pickup timing without regenerating demand."""
    lockers, options, days, ages, capacity, demand, occupancy = data
    if capacity_override is not None:
        capacity = {l: capacity_override for l in lockers}
    if pickup_delay:
        new_ages = list(range(max(ages) + pickup_delay + 1))
        occupancy = {
            (s, a): 1.0 if a < pickup_delay else occupancy[s, a - pickup_delay]
            for s in options for a in new_ages
        }
        ages = new_ages
    return lockers, options, days, ages, capacity, demand, occupancy


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export_results(model, data, output_dir):
    """Export decisions, daily occupancy, and location-level summaries."""
    lockers, options, days, ages, capacity, demand, occupancy = data
    alpha = pyo.value(model.alpha)
    output_dir.mkdir(parents=True, exist_ok=True)
    decisions, daily, summaries = [], [], []
    for l in lockers:
        for t in days:
            for s in options:
                accepted = int(round(pyo.value(model.y[l, s, t])))
                decisions.append({
                    "locker_id": l, "day": t, "ship_option": s,
                    "demand": demand[l, s, t], "accepted": accepted,
                    "rejected": round(demand[l, s, t] - accepted, 6),
                    "expected_slots": round(pyo.value(model.x[l, s, t]), 6),
                })
            occupied = sum(pyo.value(model.x[l, s, t]) for s in options)
            daily.append({
                "locker_id": l, "day": t, "capacity": capacity[l],
                "alpha": alpha, "effective_capacity": alpha * capacity[l],
                "expected_occupancy": round(occupied, 6),
                "unused_capacity": round(capacity[l] - occupied, 6),
            })
        requested = sum(demand[l, s, t] for s in options for t in days)
        accepted = sum(int(round(pyo.value(model.y[l, s, t])))
                       for s in options for t in days)
        summaries.append({
            "locker_id": l, "capacity": capacity[l], "demand": requested,
            "alpha": alpha, "effective_capacity": alpha * capacity[l],
            "accepted": accepted, "rejected": round(requested - accepted, 6),
            "acceptance_rate": round(accepted / requested, 6) if requested else 0,
        })
    write_csv(output_dir / "decisions.csv", decisions)
    write_csv(output_dir / "daily_occupancy.csv", daily)
    write_csv(output_dir / "locker_summary.csv", summaries)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locker", type=Path, default=DATA_DIR / "locker.csv")
    parser.add_argument("--demand", type=Path, default=DATA_DIR / "demand.csv")
    parser.add_argument("--occupancy", type=Path, default=DATA_DIR / "occupancy.csv")
    parser.add_argument("--solver", default="auto")
    parser.add_argument("--tee", action="store_true")
    parser.add_argument("--alpha", type=float, default=1.0,
                        help="Fraction of capacity available for expected occupancy (0 < alpha <= 1)")
    parser.add_argument("--scenarios", action="store_true",
                        help="Also solve 23-slot, 69-slot, and slower-pickup scenarios")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports",
                        help="Directory for result CSV files")
    args = parser.parse_args()
    if not math.isfinite(args.alpha) or not 0 < args.alpha <= 1:
        parser.error("--alpha must satisfy 0 < alpha <= 1")
    data = load_inputs(args.locker, args.demand, args.occupancy)
    solver_name, solver = get_solver(args.solver)
    scenarios = [("base", data)]
    if args.scenarios:
        scenarios.extend([
            ("capacity_23", scenario_inputs(data, capacity_override=23)),
            ("capacity_69", scenario_inputs(data, capacity_override=69)),
            ("slower_pickups", scenario_inputs(data, pickup_delay=1)),
        ])
    comparison = []
    for name, inputs in scenarios:
        model = build_model(inputs, alpha=args.alpha)
        results = solver.solve(model, tee=args.tee)
        if results.solver.termination_condition != TerminationCondition.optimal:
            raise RuntimeError(f"{name}: solver termination: "
                               f"{results.solver.termination_condition}")
        summaries = export_results(model, inputs, args.output_dir / name)
        accepted = sum(r["accepted"] for r in summaries)
        requested = sum(r["demand"] for r in summaries)
        comparison.append({
            "scenario": name, "solver": solver_name, "status": "optimal",
            "total_slots": sum(inputs[4].values()), "demand": requested,
            "alpha": args.alpha,
            "effective_total_capacity": args.alpha * sum(inputs[4].values()),
            "accepted": accepted, "rejected": requested - accepted,
            "acceptance_rate": round(accepted / requested, 6) if requested else 0,
        })
        print(f"\nScenario: {name}")
        print(f"Capacity factor (alpha): {args.alpha:g}")
        display(model, solver_name)
    write_csv(args.output_dir / "scenario_comparison.csv", comparison)
    print(f"\nResults saved to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
