"""Check the greedy benchmark's timing, capacity limits, and request order."""

import sys
import unittest
from pathlib import Path

import pyomo.environ as pyo
from pyomo.opt import TerminationCondition

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solve_capacity import build_model, get_solver, run_fcfs


class FCFSTests(unittest.TestCase):
    def data(self, capacity=2):
        return (
            ["locker"], ["fast", "slow"], [1, 2, 3, 4], [0, 1, 2, 3],
            {"locker": capacity},
            {("locker", s, t): (1 if (s == "slow" and t == 1)
                               or (s == "fast" and t > 1) else 0)
             for s in ("fast", "slow") for t in (1, 2, 3, 4)},
            {(s, a): (1 if s == "slow" or a == 0 else 0)
             for s in ("fast", "slow") for a in (0, 1, 2, 3)},
        )

    def decisions(self, model):
        return {key: pyo.value(variable) for key, variable in model.y.items()}

    def test_fcfs_accepts_early_request_even_when_optimization_would_wait(self):
        data = self.data(capacity=1)
        fcfs = run_fcfs(data, alpha=1)
        self.assertEqual(pyo.value(fcfs.y["locker", "slow", 1]), 1)
        self.assertEqual(pyo.value(fcfs.objective), 1)
        optimized = build_model(data, alpha=1)
        _, solver = get_solver("auto")
        result = solver.solve(optimized)
        self.assertEqual(result.solver.termination_condition, TerminationCondition.optimal)
        self.assertEqual(pyo.value(optimized.objective), 3)

    def test_released_space_is_used_on_later_days(self):
        model = run_fcfs(self.data(), alpha=1)
        self.assertEqual(pyo.value(model.objective), 4)
        for t in (2, 3, 4):
            self.assertEqual(pyo.value(model.y["locker", "fast", t]), 1)
            self.assertEqual(sum(pyo.value(model.x["locker", s, t])
                                 for s in model.S), 2)

    def test_fractional_buffer_leaves_no_room_for_a_second_package(self):
        model = run_fcfs(self.data(), alpha=0.9)
        self.assertEqual(pyo.value(model.objective), 1)
        for t in model.T:
            self.assertLessEqual(sum(pyo.value(model.x["locker", s, t])
                                     for s in model.S), 1.8)

    def test_future_demand_does_not_change_earlier_decisions(self):
        data = self.data()
        original = run_fcfs(data)
        data[5]["locker", "fast", 4] = 100
        changed = run_fcfs(data)
        for key, accepted in self.decisions(original).items():
            if key[2] < 4:
                self.assertEqual(pyo.value(changed.y[key]), accepted)

    def test_seeded_order_is_repeatable_and_independent_of_column_order(self):
        data = self.data(capacity=10)
        for key in data[5]:
            data[5][key] = 20
        first = self.decisions(run_fcfs(data, seed=42))
        self.assertEqual(first, self.decisions(run_fcfs(data, seed=42)))
        reversed_options = (data[0], list(reversed(data[1])), *data[2:])
        self.assertEqual(first, self.decisions(run_fcfs(reversed_options, seed=42)))
        self.assertNotEqual(first, self.decisions(run_fcfs(data, seed=43)))

    def test_fractional_demand_and_zero_demand(self):
        data = self.data(capacity=100)
        for key in data[5]:
            data[5][key] = 1.9
        model = run_fcfs(data)
        self.assertTrue(all(value == 1 for value in self.decisions(model).values()))
        for key in data[5]:
            data[5][key] = 0
        self.assertEqual(pyo.value(run_fcfs(data).objective), 0)


if __name__ == "__main__":
    unittest.main()
