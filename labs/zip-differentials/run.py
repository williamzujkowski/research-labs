"""Run the fixed benign corpus. No external input or archive extraction interface."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from fixtures import fixtures, inventory

ROOT = Path(__file__).resolve().parent


def run_adapter(command):
    try:
        child = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except subprocess.TimeoutExpired as exc:
        return {"classification": "timeout", "exit_code": None,
                "stdout": (exc.stdout or b"").decode(errors="replace"),
                "stderr": (exc.stderr or b"").decode(errors="replace"), "observation": None}
    raw = {"exit_code": child.returncode, "stdout": child.stdout, "stderr": child.stderr}
    try:
        observed = json.loads(child.stdout)
    except json.JSONDecodeError:
        return dict(raw, classification="adapter-error", observation=None)
    if (not isinstance(observed, dict)
            or observed.get("status") not in {"success", "rejected"}
            or not isinstance(observed.get("entries"), list)
            or any(not isinstance(entry, dict)
                   or not isinstance(entry.get("name"), str)
                   or not isinstance(entry.get("sha256"), str)
                   or len(entry["sha256"]) != 64
                   or not isinstance(entry.get("size"), int)
                   or entry["size"] < 0
                   or not isinstance(entry.get("marker"), bool)
                   for entry in observed.get("entries", []))):
        return dict(raw, classification="adapter-error", observation=observed)
    if "Harness limit:" in str(observed.get("error", "")):
        classification = "limit-exceeded"
    elif child.returncode == 2 and observed.get("status") == "rejected":
        classification = "rejected"
    elif child.returncode == 0 and observed.get("status") == "success":
        classification = "success-with-warning" if child.stderr or observed.get("warnings") else "success"
    else:
        classification = "adapter-error"
    return dict(raw, classification=classification, observation=observed)


def control_passes(control):
    expected_entry = {"name": "note.txt", "size": 14,
                      "sha256": hashlib.sha256(b"ordinary text\n").hexdigest(),
                      "marker": False}
    return len(control["runs"]) == 3 and all(
        run["classification"] == "success"
        and run["observation"]["entries"] == [expected_entry]
        for run in control["runs"].values())


def main():
    expected = json.loads((ROOT / "fixtures.json").read_text())
    if inventory() != expected:
        raise SystemExit("Fixture inventory changed; review and regenerate fixtures.json explicitly")
    report = {
        "schema_version": 1,
        "scope": "fixed benign ZIP API pilot; not antivirus, exploitation, or full paper replication",
        "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "environment": {"python": sys.version, "java": subprocess.run(
            ["java", "-version"], capture_output=True, text=True, check=True).stderr,
            "platform": platform.platform(), "machine": platform.machine(),
            "image_id": os.environ.get("LAB_IMAGE_ID", "unrecorded-local-run"),
            "source_revision": os.environ.get("LAB_REVISION", "unrecorded-local-run"),
            "source_dirty": os.environ.get("LAB_DIRTY", "unknown"),
            "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(ROOT.iterdir()) if p.suffix in {".py", ".java", ".json"}}},
        "limits": {"timeout_seconds_per_adapter": 10, "entry_ceiling": 20,
                   "decoded_byte_ceiling_per_adapter": 1048576},
        "fixtures": [],
    }
    for name, data in fixtures().items():
        with tempfile.TemporaryDirectory(prefix="zip-pilot-") as directory:
            path = Path(directory) / "input.zip"
            path.write_bytes(data)
            commands = {
                "python-zipinfo": [sys.executable, str(ROOT / "probe.py"), str(path)],
                "java-zipfile": ["java", "-XX:ActiveProcessorCount=1", "-Xmx128m", "-cp", str(ROOT), "ZipProbe", "zipfile", str(path)],
                "java-stream": ["java", "-XX:ActiveProcessorCount=1", "-Xmx128m", "-cp", str(ROOT), "ZipProbe", "stream", str(path)],
            }
            runs = {adapter: run_adapter(command) for adapter, command in commands.items()}
            # Comparison uses complete accepted observations; rejection is not an empty archive.
            accepted = {key: run["observation"]["entries"] for key, run in runs.items()
                        if run["classification"] in {"success", "success-with-warning"}}
            report["fixtures"].append({"name": name, **expected[name], "runs": runs,
                "accepted_entry_sequence_disagreement": len({json.dumps(value, sort_keys=True)
                    for value in accepted.values()}) > 1,
                "accepted_marker_decisions": {key: any(e["marker"] for e in entries)
                    for key, entries in accepted.items()}})
    print(json.dumps(report, indent=2))
    failures = [run for fixture in report["fixtures"] for run in fixture["runs"].values()
                if run["classification"] in {"timeout", "adapter-error", "limit-exceeded"}]
    control = report["fixtures"][0]
    if failures or not control_passes(control):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
