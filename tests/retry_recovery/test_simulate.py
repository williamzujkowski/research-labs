import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('retry_sim', ROOT / 'labs/retry-recovery/simulate.py')
sim = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sim)
BASE = json.loads((ROOT / 'labs/retry-recovery/config.json').read_text())


class SimulationTests(unittest.TestCase):
    def run_case(self, arrivals, policy='jitter', **changes):
        config = dict(BASE, duration_seconds=100, **changes)
        return sim.simulate(config, 4, 11, True, policy, arrivals)

    def test_success_and_conservation(self):
        run = self.run_case([1, 2, 3])
        self.assertEqual(run['original_statuses'], {'success': 3})
        self.assertEqual(run['totals']['attempts'], 3)
        self.assertEqual(run['totals']['admitted_attempts'], run['totals']['completed_attempts'])
        self.assertEqual(run['unfinished_server_work'], 0)

    def test_timeout_does_not_cancel_server_work(self):
        run = self.run_case([1], policy='none', normal_service_seconds=2)
        self.assertEqual(run['original_statuses'], {'attempts_exhausted': 1})
        self.assertEqual(run['totals']['completed_attempts'], 1)
        self.assertEqual(run['totals']['unused_completions'], 1)
        self.assertEqual(run['terminal_latencies'][0]['seconds'], 1)

    def test_completion_wins_exact_timeout_tie(self):
        run = self.run_case([1], normal_service_seconds=1)
        self.assertEqual(run['original_statuses'], {'success': 1})

    def test_deadline_prevents_later_retry(self):
        run = self.run_case([1], normal_service_seconds=10, original_deadline_seconds=0.5)
        self.assertEqual(run['original_statuses'], {'deadline_expired': 1})
        self.assertEqual(run['totals']['attempts'], 1)

    def test_zero_budget_allows_original_but_denies_retry(self):
        run = self.run_case([1], policy='budget', normal_service_seconds=2,
                            retry_token_capacity=0, retry_tokens_per_second=0)
        self.assertEqual(run['totals']['attempts'], 1)
        self.assertEqual(run['original_statuses'], {'budget_denied': 1})

    def test_queue_cap_and_arrival_drop(self):
        run = self.run_case([1, 1, 1], queue_capacity=1)
        self.assertEqual(run['totals']['dropped_arrivals'], 1)
        self.assertEqual(run['totals']['rejected_attempts'], 1)
        self.assertEqual(run['totals']['attempts'], 3)
        self.assertEqual(sum(run['original_statuses'].values()), 3)

    def test_attempt_cap_censors_without_exceeding_cap(self):
        run = self.run_case([1, 2, 3], attempt_cap=1)
        self.assertEqual(run['stop_reason'], 'attempt_cap')
        self.assertEqual(run['totals']['attempts'], 1)
        self.assertEqual(run['original_statuses'], {'success': 1, 'pending': 1})
        self.assertTrue(run['recovery']['censored'])

    def test_cutoff_preserves_pending_and_server_work(self):
        run = self.run_case([99.9], normal_service_seconds=2)
        self.assertEqual(run['original_statuses'], {'pending': 1})
        self.assertEqual(run['unfinished_server_work'], 1)
        self.assertAlmostEqual(run['pending_original_ages'][0], 0.1)

    def test_fixed_schedules_and_simulation_determinism(self):
        outputs = [sim.simulate(BASE, 4, 11, False, policy) for policy in BASE['policies']]
        self.assertEqual(len({r['arrival_schedule_sha256'] for r in outputs}), 1)
        self.assertEqual(outputs[1], sim.simulate(BASE, 4, 11, False, 'jitter'))
        for run in outputs:
            totals = run['totals']
            self.assertEqual(totals['arrivals'], sum(run['original_statuses'].values()))
            self.assertEqual(totals['admitted_attempts'], totals['completed_attempts'] + run['unfinished_server_work'])
            self.assertEqual(totals['attempts'], totals['admitted_attempts'] + totals.get('rejected_attempts', 0))

    def test_completion_gate_rejects_partial_matrix_and_execution_caps(self):
        case = {'stop_reason': 'observation_cutoff', 'recovery': {'censored': True}}
        result = {'config': BASE, 'runs': [dict(case) for _ in range(54)]}
        self.assertEqual(sim.completion_status(result), 0)
        result['runs'].pop()
        self.assertEqual(sim.completion_status(result), 2)
        result['runs'].append(dict(case, stop_reason='attempt_cap'))
        self.assertEqual(sim.completion_status(result), 2)
        result['runs'][-1] = dict(case)
        result['stop_reason'] = 'wall_clock_budget'
        self.assertEqual(sim.completion_status(result), 2)

    def test_recovery_requires_ten_consecutive_windows(self):
        windows = [{'window_start': n, 'successes': 10} for n in range(100)]
        windows[85]['successes'] = 9
        result = sim.recovery(windows, BASE)
        self.assertEqual(result['qualifying_start'], 86)
        self.assertEqual(result['confirmed_after_seconds'], 16)
        self.assertFalse(result['censored'])
        self.assertTrue(sim.recovery(windows[:95], BASE)['censored'])


if __name__ == '__main__':
    unittest.main()
