"""Offline regression tests for fixture safety and result accounting."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


LAB = Path(__file__).resolve().parents[1] / "labs" / "zip-differentials"
sys.path.insert(0, str(LAB))
import fixtures  # noqa: E402
import probe  # noqa: E402
import run  # noqa: E402


class FixtureTests(unittest.TestCase):
    def test_inventory_is_deterministic_and_matches_retained_hashes(self):
        first = fixtures.fixtures()
        self.assertEqual(first, fixtures.fixtures())
        expected = json.loads((LAB / "fixtures.json").read_text())
        actual = {name: {"sha256": hashlib.sha256(data).hexdigest(),
                         "size": len(data)} for name, data in first.items()}
        self.assertEqual(actual, expected)
        self.assertEqual(actual, fixtures.inventory())

    def test_control_is_an_ordinary_readable_zip(self):
        with zipfile.ZipFile(io.BytesIO(fixtures.fixtures()["control"])) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), ["note.txt"])
            self.assertEqual(archive.read("note.txt"), b"ordinary text\n")

    def test_fixed_corpus_is_small_and_paths_and_payloads_are_harmless(self):
        corpus = fixtures.fixtures()
        self.assertIn("control", corpus)
        self.assertLessEqual(len(corpus), 7)  # One control and at most six variants.
        safe_names = {"note.txt", "first.txt", "second.txt", "local.txt",
                      "index.txt", "extra.txt"}
        safe_payloads = {b"ordinary text\n", b"first\n", b"REVIEW-ME\n"}
        for name, data in corpus.items():
            with self.subTest(fixture=name):
                self.assertLess(len(data), 4096)
                # Inspect local records independently: the central directory omits
                # one of them intentionally, so ZipFile alone cannot audit safety.
                cursor = 0
                count = 0
                while data[cursor:cursor + 4] == b"PK\x03\x04":
                    header = struct.unpack_from("<I5H3I2H", data, cursor)
                    _, _, flags, compression, _, _, _, size, decoded, nlen, xlen = header
                    self.assertEqual(flags, 0)
                    self.assertEqual(compression, 0)
                    self.assertEqual(size, decoded)
                    start = cursor + 30
                    self.assertIn(data[start:start + nlen].decode("ascii"), safe_names)
                    start += nlen + xlen
                    self.assertIn(data[start:start + size], safe_payloads)
                    cursor = start + size
                    count += 1
                self.assertGreater(count, 0)
                self.assertLessEqual(count, 20)
                self.assertEqual(data[cursor:cursor + 4], b"PK\x01\x02")
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for info in archive.infolist():
                        self.assertIn(info.filename, safe_names)
                        self.assertFalse(stat.S_ISLNK(info.external_attr >> 16))
                        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                        self.assertEqual(info.flag_bits, 0)


class PythonProbeTests(unittest.TestCase):
    def observe(self, name):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "input.zip"
            archive.write_bytes(fixtures.fixtures()[name])
            return probe.probe(archive)

    def test_duplicate_entries_preserve_both_payloads_in_each_order(self):
        ordinary = b"ordinary text\n"
        marker = b"REVIEW-ME\n"
        for name, payloads in [
            ("duplicate-marker-first", [marker, ordinary]),
            ("duplicate-marker-last", [ordinary, marker]),
        ]:
            with self.subTest(fixture=name):
                observed = self.observe(name)
                self.assertEqual(observed["status"], "success")
                self.assertEqual(observed["entries"], [
                    {"name": "note.txt", "sha256": hashlib.sha256(data).hexdigest(),
                     "size": len(data), "marker": data == marker} for data in payloads])
                self.assertTrue(any(entry["marker"] for entry in observed["entries"]))

    def test_local_name_conflict_is_rejection_not_empty_success(self):
        observed = self.observe("local-central-name-conflict")
        self.assertEqual(observed["status"], "rejected")
        self.assertIn("BadZipFile", observed["error"])

    def test_omitted_local_record_is_not_visible_to_index_reader(self):
        observed = self.observe("local-entry-absent-from-index")
        self.assertEqual(observed["status"], "success")
        self.assertEqual([entry["name"] for entry in observed["entries"]], ["note.txt"])
        self.assertFalse(any(entry["marker"] for entry in observed["entries"]))

    def test_index_order_is_preserved(self):
        observed = self.observe("central-order-reversed")
        self.assertEqual(observed["status"], "success")
        self.assertEqual([entry["name"] for entry in observed["entries"]],
                         ["second.txt", "first.txt"])

    def test_entry_ceiling_rejects_with_partial_observations_preserved(self):
        data = fixtures.archive([(f"file{i}.txt", f"file{i}.txt", b"text\n")
                                 for i in range(21)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ceiling.zip"
            path.write_bytes(data)
            observed = probe.probe(path)
        self.assertEqual(observed["status"], "rejected")
        self.assertIn("entry ceiling", observed["error"])
        self.assertEqual(len(observed["entries"]), 20)

    def test_byte_ceiling_rejects_oversized_stored_payload(self):
        data = fixtures.archive([("large.txt", "large.txt", b"x" * 1048577)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ceiling.zip"
            path.write_bytes(data)
            observed = probe.probe(path)
        self.assertEqual(observed["status"], "rejected")
        self.assertIn("byte ceiling", observed["error"])


class AdapterAccountingTests(unittest.TestCase):
    def invoke(self, observation, code=0, stderr=""):
        stdout = json.dumps(observation)
        child = subprocess.CompletedProcess(["adapter"], code, stdout, stderr)
        with patch.object(run.subprocess, "run", return_value=child) as mocked:
            result = run.run_adapter(["adapter"])
        mocked.assert_called_once_with(["adapter"], capture_output=True, text=True,
                                       timeout=10, check=False)
        self.assertEqual(result["stdout"], stdout)
        self.assertEqual(result["stderr"], stderr)
        self.assertEqual(result["exit_code"], code)
        return result

    def test_success_and_warning_success_remain_distinct(self):
        observation = {"status": "success", "entries": [], "warnings": [], "error": None}
        self.assertEqual(self.invoke(observation)["classification"], "success")
        self.assertEqual(self.invoke(observation, stderr="warning\n")["classification"],
                         "success-with-warning")
        observation["warnings"] = ["warning"]
        self.assertEqual(self.invoke(observation)["classification"], "success-with-warning")

    def test_rejection_preserves_partial_observations(self):
        observation = {"status": "rejected", "entries": [
            {"name": "note.txt", "sha256": "a" * 64, "size": 1, "marker": False}],
            "warnings": [], "error": "invalid next entry"}
        result = self.invoke(observation, code=2)
        self.assertEqual(result["classification"], "rejected")
        self.assertEqual(result["observation"], observation)

    def test_harness_limit_is_separate_from_parser_rejection(self):
        observation = {"status": "rejected", "entries": [], "warnings": [],
                       "error": "IOException: Harness limit: more than 20 entries"}
        result = self.invoke(observation, code=2)
        self.assertEqual(result["classification"], "limit-exceeded")
        self.assertEqual(result["observation"], observation)

    def test_exit_status_and_observation_must_agree(self):
        for code, status in [(0, "rejected"), (2, "success"), (1, "success")]:
            with self.subTest(code=code, status=status):
                result = self.invoke({"status": status, "entries": [],
                                      "warnings": [], "error": None}, code=code)
                self.assertEqual(result["classification"], "adapter-error")

    def test_invalid_json_preserves_raw_error_output(self):
        child = subprocess.CompletedProcess(["adapter"], 1, "not json\n", "crash\n")
        with patch.object(run.subprocess, "run", return_value=child):
            result = run.run_adapter(["adapter"])
        self.assertEqual(result["classification"], "adapter-error")
        self.assertIsNone(result["observation"])
        self.assertEqual(result["stdout"], "not json\n")
        self.assertEqual(result["stderr"], "crash\n")

    def test_json_without_an_observation_schema_is_adapter_error(self):
        for value in [None, [], "success", {"status": "success"},
                      {"status": "success", "entries": "not a list"},
                      {"status": "success", "entries": [{}]}]:
            with self.subTest(value=value):
                self.assertEqual(self.invoke(value)["classification"], "adapter-error")

    def test_timeout_keeps_partial_output_and_cannot_be_success(self):
        error = subprocess.TimeoutExpired(["adapter"], 10,
                                          output=b"partial\xff", stderr=b"warning\n")
        with patch.object(run.subprocess, "run", side_effect=error):
            result = run.run_adapter(["adapter"])
        self.assertEqual(result["classification"], "timeout")
        self.assertIsNone(result["exit_code"])
        self.assertIsNone(result["observation"])
        self.assertEqual(result["stdout"], "partial\ufffd")
        self.assertEqual(result["stderr"], "warning\n")


class ControlGateTests(unittest.TestCase):
    def control(self):
        return {"runs": {name: {"classification": "success", "observation": {
            "entries": [{"name": "note.txt", "size": 14, "marker": False,
                         "sha256": hashlib.sha256(b"ordinary text\n").hexdigest()}]}}
            for name in ["python-zipinfo", "java-zipfile", "java-stream"]}}

    def test_exact_control_payload_passes(self):
        self.assertTrue(run.control_passes(self.control()))

    def test_three_empty_successes_do_not_pass(self):
        control = self.control()
        for result in control["runs"].values():
            result["observation"]["entries"] = []
        self.assertFalse(run.control_passes(control))

    def test_one_wrong_payload_hash_does_not_pass(self):
        control = self.control()
        control["runs"]["java-stream"]["observation"]["entries"][0]["sha256"] = "0" * 64
        self.assertFalse(run.control_passes(control))


class JavaProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("java") and (LAB / "ZipProbe.class").is_file():
            return
        if Path("/.dockerenv").exists() or os.environ.get("LAB_REQUIRE_JAVA_TESTS") == "1":
            raise AssertionError("Container tests require java and compiled ZipProbe.class")
        raise unittest.SkipTest("Java or compiled ZipProbe.class absent; use the lab container")

    def observe(self, mode, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.zip"
            path.write_bytes(data)
            return run.run_adapter(["java", "-XX:ActiveProcessorCount=1", "-Xmx128m",
                                    "-cp", str(LAB), "ZipProbe", mode, str(path)])

    def test_duplicate_entry_hashes_and_markers_preserve_order(self):
        for mode in ["zipfile", "stream"]:
            for fixture, payloads in [
                ("duplicate-marker-first", [b"REVIEW-ME\n", b"ordinary text\n"]),
                ("duplicate-marker-last", [b"ordinary text\n", b"REVIEW-ME\n"]),
            ]:
                with self.subTest(mode=mode, fixture=fixture):
                    result = self.observe(mode, fixtures.fixtures()[fixture])
                    self.assertEqual(result["classification"], "success", result)
                    self.assertEqual(result["observation"]["entries"], [
                        {"name": "note.txt", "sha256": hashlib.sha256(data).hexdigest(),
                         "size": len(data), "marker": data == b"REVIEW-ME\n"}
                        for data in payloads])

    def test_omitted_index_entry_is_visible_only_to_stream(self):
        data = fixtures.fixtures()["local-entry-absent-from-index"]
        for mode, names, marked in [("zipfile", ["note.txt"], False),
                                    ("stream", ["note.txt", "extra.txt"], True)]:
            with self.subTest(mode=mode):
                result = self.observe(mode, data)
                self.assertEqual(result["classification"], "success", result)
                entries = result["observation"]["entries"]
                self.assertEqual([entry["name"] for entry in entries], names)
                self.assertEqual(any(entry["marker"] for entry in entries), marked)

    def test_byte_ceiling_accepts_exact_limit_and_rejects_one_more(self):
        for mode in ["zipfile", "stream"]:
            for size in [1048576, 1048577]:
                with self.subTest(mode=mode, size=size):
                    data = fixtures.archive([("large.txt", "large.txt", b"x" * size)])
                    result = self.observe(mode, data)
                    expected = "success" if size == 1048576 else "limit-exceeded"
                    self.assertEqual(result["classification"], expected, result)
                    if expected == "success":
                        self.assertEqual(result["observation"]["entries"][0]["size"], size)

    def test_entry_ceiling_accepts_twenty_and_rejects_twenty_one(self):
        for mode in ["zipfile", "stream"]:
            for count in [20, 21]:
                with self.subTest(mode=mode, count=count):
                    data = fixtures.archive([(f"file{i}.txt", f"file{i}.txt", b"text\n")
                                             for i in range(count)])
                    result = self.observe(mode, data)
                    expected = "success" if count == 20 else "limit-exceeded"
                    self.assertEqual(result["classification"], expected, result)
                    self.assertEqual(len(result["observation"]["entries"]), 20)


if __name__ == "__main__":
    unittest.main()
