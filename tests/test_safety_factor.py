"""Regression checks for capacity buffers and their reported limits."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import pyomo.environ as pyo
from pyomo.opt import TerminationCondition

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solve_capacity import build_model, export_results, get_solver, scenario_inputs


class SafetyFactorTests(unittest.TestCase):
    def setUp(self):
        self.data = (
            ["locker"], ["standard"], [1], [0], {"locker": 10},
            {("locker", "standard", 1): 100}, {("standard", 0): 1.0},
        )
        _, self.solver = get_solver("auto")

    def solve(self, data=None, **kwargs):
        model = build_model(self.data if data is None else data, **kwargs)
        result = self.solver.solve(model)
        self.assertEqual(result.solver.termination_condition, TerminationCondition.optimal)
        return model

    def test_default_buffer_and_unbuffered_benchmark(self):
        self.assertEqual(pyo.value(self.solve().objective), 9)
        self.assertEqual(pyo.value(self.solve(alpha=1).objective), 10)

    def test_fractional_limit_keeps_acceptance_integer(self):
        model = self.solve(alpha=0.95)
        self.assertAlmostEqual(pyo.value(model.capacity_limit["locker", 1].upper), 9.5)
        self.assertEqual(pyo.value(model.objective), 9)

    def test_buffer_includes_packages_remaining_from_previous_days(self):
        data = (
            ["locker"], ["standard"], [1, 2], [0, 1], {"locker": 10},
            {("locker", "standard", 1): 8, ("locker", "standard", 2): 8},
            {("standard", 0): 1.0, ("standard", 1): 0.5},
        )
        self.assertEqual(pyo.value(self.solve(data).objective), 13)
        self.assertEqual(pyo.value(self.solve(data, alpha=1).objective), 14)

    def test_scenario_capacity_is_scaled_once_and_reported(self):
        for capacity in (23, 46, 69):
            with self.subTest(capacity=capacity):
                data = scenario_inputs(self.data, capacity_override=capacity)
                model = self.solve(data)
                effective = 0.9 * capacity
                self.assertAlmostEqual(
                    pyo.value(model.capacity_limit["locker", 1].upper), effective
                )
                with tempfile.TemporaryDirectory() as directory:
                    summaries = export_results(model, data, Path(directory))
                    self.assertEqual(summaries[0]["capacity"], capacity)
                    self.assertAlmostEqual(summaries[0]["effective_capacity"], effective)
                    with (Path(directory) / "daily_occupancy.csv").open() as file:
                        row = next(csv.DictReader(file))
                    occupied = float(row["expected_occupancy"])
                    self.assertLessEqual(occupied, effective + 1e-6)
                    self.assertAlmostEqual(float(row["unused_capacity"]), capacity - occupied)
                    self.assertAlmostEqual(
                        float(row["unused_effective_capacity"]), effective - occupied
                    )

    def test_invalid_factors_are_rejected(self):
        for alpha in (0, -0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                build_model(self.data, alpha=alpha)


if __name__ == "__main__":
    unittest.main()
