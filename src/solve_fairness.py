"""Sweep weekly shipping-option service floors without changing baseline reports."""

import argparse
import math
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

import pyomo.environ as pyo
from pyomo.opt import TerminationCondition

from solve_capacity import (
    DATA_DIR, DEFAULT_ALPHA, PROJECT_ROOT, build_model, export_results,
    get_solver, load_inputs, safety_factor, write_csv,
)

DEFAULT_TARGETS = (0.75, 0.78, 0.80, 0.82, 0.85)


def service_rate(value):
    rate = float(value)
    if not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError("Service rate must be finite and between 0 and 1")
    return rate


def option_demand(data):
    lockers, options, days, _, _, demand, _ = data
    return {s: sum((Decimal(str(demand[l, s, t])) for l in lockers for t in days),
                   Decimal(0)) for s in options}


def required_packages(requested, rate):
    """Round up exact decimal service requirements, since packages are integer."""
    return int((requested * Decimal(str(rate))).to_integral_value(rounding=ROUND_CEILING))


def solve_fair_plan(data, solver, alpha=DEFAULT_ALPHA, rate=None):
    """First maximize throughput, then the minimum option acceptance rate.

    Floors are aggregated across all lockers and days, not imposed per locker.
    The secondary objective never sacrifices an optimal accepted package.
    """
    if rate is not None:
        rate = service_rate(rate)
    requested = option_demand(data)
    model = build_model(data, alpha=alpha)
    model.option_accepted = pyo.Expression(
        model.S, rule=lambda m, s: sum(m.y[l, s, t] for l in m.L for t in m.T)
    )
    if rate is not None:
        model.service_floor = pyo.Constraint(
            model.S,
            rule=lambda m, s: m.option_accepted[s] >= required_packages(requested[s], rate),
        )
    result = solver.solve(model, load_solutions=False)
    status = result.solver.termination_condition
    if status == TerminationCondition.infeasible:
        return "infeasible", None
    if status != TerminationCondition.optimal:
        raise RuntimeError(f"Throughput solve ended with {status}")
    model.solutions.load_from(result)
    total = sum(model.option_accepted[s] for s in model.S)
    best = int(round(pyo.value(total)))
    model.keep_optimal_throughput = pyo.Constraint(expr=total == best)
    model.minimum_acceptance_rate = pyo.Var(bounds=(0, 1))
    model.balance_service = pyo.Constraint(
        model.S, rule=lambda m, s: m.option_accepted[s]
        >= float(requested[s]) * m.minimum_acceptance_rate
        if requested[s] > 0 else pyo.Constraint.Skip,
    )
    model.objective.set_value(model.minimum_acceptance_rate)
    result = solver.solve(model, load_solutions=False)
    status = result.solver.termination_condition
    if status != TerminationCondition.optimal:
        raise RuntimeError(f"Service-balance solve ended with {status}")
    model.solutions.load_from(result)
    return "optimal", model


def run_experiment(data, solver, output_dir, alpha=DEFAULT_ALPHA, targets=DEFAULT_TARGETS):
    targets = [service_rate(rate) for rate in targets]
    if len(set(targets)) != len(targets):
        raise ValueError("Service targets must be unique")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    requested = option_demand(data)
    total_demand = float(sum(requested.values()))
    summaries, rates = [], []
    reference = None
    for name, target in [("unconstrained", None)] + [
        (f"rho_{format(rate, '.12g').replace('.', '_')}", rate) for rate in targets
    ]:
        print(f"Solving {name} ...", flush=True)
        status, model = solve_fair_plan(data, solver, alpha=alpha, rate=target)
        row = {
            "case": name, "minimum_required_rate": target if target is not None else "",
            "status": status, "alpha": alpha, "demand": total_demand,
            "accepted": "", "rejected": "", "acceptance_rate": "",
            "throughput_cost": "", "minimum_achieved_rate": "", "rate_gap_pp": "",
        }
        if model is not None:
            export_results(model, data, output_dir / name)
            accepted = {s: int(round(pyo.value(model.option_accepted[s]))) for s in data[1]}
            total = sum(accepted.values())
            if reference is None:
                reference = total
            actual_rates = [accepted[s] / float(requested[s])
                            for s in data[1] if requested[s] > 0]
            row.update({
                "accepted": total, "rejected": total_demand - total,
                "acceptance_rate": total / total_demand if total_demand else "",
                "throughput_cost": reference - total,
                "minimum_achieved_rate": min(actual_rates) if actual_rates else "",
                "rate_gap_pp": 100 * (max(actual_rates) - min(actual_rates))
                if actual_rates else "",
            })
        for s in data[1]:
            amount = int(round(pyo.value(model.option_accepted[s]))) if model is not None else ""
            rates.append({
                "case": name, "minimum_required_rate": row["minimum_required_rate"],
                "status": status, "ship_option": s, "demand": float(requested[s]),
                "minimum_required_packages": required_packages(requested[s], target)
                if target is not None else "",
                "accepted": amount,
                "acceptance_rate": amount / float(requested[s])
                if model is not None and requested[s] > 0 else "",
            })
        summaries.append(row)
        # Save completed cases even if a later solve is interrupted.
        write_csv(output_dir / "fairness_summary.csv", summaries)
        write_csv(output_dir / "option_acceptance.csv", rates)
        print(f"  {status}; accepted={row['accepted']}; cost={row['throughput_cost']}", flush=True)
    return summaries, rates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locker", type=Path, default=DATA_DIR / "locker.csv")
    parser.add_argument("--demand", type=Path, default=DATA_DIR / "demand.csv")
    parser.add_argument("--occupancy", type=Path, default=DATA_DIR / "occupancy.csv")
    parser.add_argument("--alpha", type=safety_factor, default=DEFAULT_ALPHA)
    parser.add_argument("--solver", default="auto")
    parser.add_argument("--targets", type=service_rate, nargs="+", default=DEFAULT_TARGETS)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "fairness")
    args = parser.parse_args()
    data = load_inputs(args.locker, args.demand, args.occupancy)
    _, solver = get_solver(args.solver)
    run_experiment(data, solver, args.output_dir, alpha=args.alpha, targets=args.targets)


if __name__ == "__main__":
    main()
