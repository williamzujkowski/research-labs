import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('exit_status', ROOT / 'labs/exit-status/run.py')
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class CheckerTests(unittest.TestCase):
    """The checker must be able to fail; a checker that cannot is the lab's own subject."""

    def observation(self, **changes):
        base = {'expect': {}, 'exit': 0, 'stdout': '', 'stdout_sha256': 'a', 'files': {}}
        base.update(changes)
        return base

    def test_wrong_exit_is_reported(self):
        failures = lab.check(self.observation(expect={'exit': 22}, exit=0), {})
        self.assertEqual(failures, ['exit 0 != 22'])

    def test_exit_nonzero_rejects_zero_and_timeout(self):
        self.assertTrue(lab.check(self.observation(expect={'exit_nonzero': True}, exit=0), {}))
        self.assertTrue(lab.check(self.observation(expect={'exit_nonzero': True}, exit=None), {}))
        self.assertFalse(lab.check(self.observation(expect={'exit_nonzero': True}, exit=2), {}))

    def test_file_states_are_distinguished(self):
        empty = {'x': {'size': 0, 'sha256': '', 'head': ''}}
        self.assertTrue(lab.check(self.observation(expect={'files': {'x': 'nonempty'}}, files=empty), {}))
        self.assertTrue(lab.check(self.observation(expect={'files': {'x': 'absent'}}, files=empty), {}))
        self.assertFalse(lab.check(self.observation(expect={'files': {'x': 'empty'}}, files=empty), {}))
        self.assertTrue(lab.check(self.observation(expect={'files': {'x': 'empty'}}), {}))

    def test_stdout_equality_needs_the_other_case(self):
        obs = self.observation(expect={'stdout_equals_case': 'other'})
        self.assertTrue(lab.check(obs, {}))
        self.assertTrue(lab.check(obs, {'other': {'stdout_sha256': 'b'}}))
        self.assertFalse(lab.check(obs, {'other': {'stdout_sha256': 'a'}}))


class LiveCaseTests(unittest.TestCase):
    """Run every case in the pinned container and require the stated outcome."""

    @classmethod
    def setUpClass(cls):
        server = lab.start_server()
        base = f'http://127.0.0.1:{server.server_address[1]}'
        try:
            cls.observed = {case['id']: lab.run_case(case, base) for case in lab.CASES}
        finally:
            server.shutdown()
        server.server_close()

    def test_every_case_matches(self):
        for case_id, observation in self.observed.items():
            with self.subTest(case=case_id):
                self.assertEqual(lab.check(observation, self.observed), [])

    def test_each_published_shape_has_a_control_that_fails(self):
        groups = {c['group'] for c in lab.CASES if c['role'] == 'published'}
        for group in groups:
            with self.subTest(group=group):
                published = [o for o in self.observed.values() if o['group'] == group and o['role'] == 'published']
                self.assertTrue(all(o['exit'] == 0 for o in published))
        # Pi-hole has no corrected CLI form for list management; it is source-only evidence.
        for group in groups - {'pihole'}:
            with self.subTest(group=group):
                self.assertTrue(any(o['exit'] not in (0, None) for o in self.observed.values()
                                    if o['group'] == group and o['role'] in ('control', 'check')))


if __name__ == '__main__':
    unittest.main()
