"""Python ZipInfo-based adapter; preserves duplicate entries and partial failures."""
import hashlib
import json
import sys
import warnings
import zipfile
from fixtures import MARKER


def probe(path):
    result = {"status": "success", "entries": [], "error": None, "warnings": []}
    total = 0
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if len(result["entries"]) >= 20:
                        raise ValueError("Harness limit: entry ceiling exceeded")
                    with archive.open(info) as stream:
                        data = stream.read(1048577 - total)
                    total += len(data)
                    if total > 1048576:
                        raise ValueError("Harness limit: byte ceiling exceeded")
                    result["entries"].append({"name": info.filename,
                        "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                        "marker": MARKER in data})
        except (zipfile.BadZipFile, ValueError, OSError, RuntimeError, NotImplementedError) as exc:
            result.update(status="rejected", error=f"{type(exc).__name__}: {exc}")
        result["warnings"] = [str(item.message) for item in seen]
    return result


if __name__ == "__main__":
    result = probe(sys.argv[1])
    print(json.dumps(result))
    sys.exit(0 if result["status"] == "success" else 2)
