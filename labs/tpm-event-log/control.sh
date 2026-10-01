#!/bin/sh
# Control-only feasibility check: can the real systemd-pcrlock, pointed at a
# disposable swtpm and a synthetic userspace log, tell a consistent PCR 11 from
# an inconsistent one? Prints one JSON document on stdout; exits nonzero if a
# control does not behave as expected.
set -eu
PCREXTEND=/usr/lib/systemd/systemd-pcrextend
PCRLOCK=/usr/lib/systemd/systemd-pcrlock
PHASES="enter-initrd leave-initrd sysinit ready"
# No firmware log exists in a container. With an empty firmware log and no declared bank,
# pcrlock knows zero hash algorithms and its per-PCR comparison loop runs zero times
# (run 1 of this check: an absent userspace log still "matched"). Declare the bank.
export SYSTEMD_FORCE_MEASURE=1 SYSTEMD_MEASURE_LOG_FIRMWARE=/dev/null SYSTEMD_TPM2_HASH_ALGORITHMS=sha256

start_tpm() { # $1 = case dir; fresh TPM state per case
    mkdir -p "$1/state"
    swtpm socket --tpm2 --tpmstate dir="$1/state" \
        --server type=unixio,path="$1/tpm.sock" --ctrl type=unixio,path="$1/tpm.sock.ctrl" \
        --flags not-need-init,startup-clear --daemon --pid file="$1/swtpm.pid" >&2
    i=0; while [ ! -S "$1/tpm.sock" ] && [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done
    export TPM2TOOLS_TCTI="swtpm:path=$1/tpm.sock" SYSTEMD_TPM2_DEVICE="swtpm:path=$1/tpm.sock"
}
stop_tpm() { kill "$(cat "$1/swtpm.pid")" 2>/dev/null || true; }

measure_phases() { # $1 = userspace log path written by systemd-pcrextend
    for p in $PHASES; do SYSTEMD_MEASURE_LOG_USERSPACE="$1" "$PCREXTEND" --bank=sha256 "$p" >&2; done
}
pcrlock_log() { # $1 = userspace log the appraiser reads, $2 = output file
    rc=0; SYSTEMD_MEASURE_LOG_USERSPACE="$1" "$PCRLOCK" log --json=short >"$2" 2>"$2.stderr" || rc=$?
    echo "$rc" >"$2.rc"
}

W=/tmp/w; mkdir -p "$W"
# C1 healthy: phases extended and logged; appraiser reads that log.
start_tpm "$W/c1"; measure_phases "$W/c1/u.log"
tpm2_pcrread sha256:11 >"$W/c1/pcr11.txt"; pcrlock_log "$W/c1/u.log" "$W/c1/log.json"; stop_tpm "$W/c1"
# C2 negative: same extends, appraiser is handed an absent userspace log.
start_tpm "$W/c2"; measure_phases "$W/c2/u.log"
tpm2_pcrread sha256:11 >"$W/c2/pcr11.txt"; pcrlock_log "$W/c2/absent.log" "$W/c2/log.json"; stop_tpm "$W/c2"
# C3 negative: logged phases plus one PCR 11 extend that no log records.
start_tpm "$W/c3"; measure_phases "$W/c3/u.log"
tpm2_pcrextend 11:sha256=$(printf 'unlogged' | sha256sum | cut -d' ' -f1) >&2
tpm2_pcrread sha256:11 >"$W/c3/pcr11.txt"; pcrlock_log "$W/c3/u.log" "$W/c3/log.json"; stop_tpm "$W/c3"

exec python3 - "$W" <<'EOF'
import hashlib, json, re, sys, pathlib, subprocess
w = pathlib.Path(sys.argv[1])
expect = {"c1": True, "c2": False, "c3": False}
out = {"lab": "tpm-event-log/control", "versions": {}, "cases": {}}
for tool in ("swtpm", "tpm2_pcrread"):
    out["versions"][tool] = subprocess.run([tool, "--version"], capture_output=True, text=True).stdout.strip()
out["versions"]["systemd"] = subprocess.run(["/usr/lib/systemd/systemd-pcrlock", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
ok_all = True
for c, want in expect.items():
    d = w / c
    raw = (d / "log.json").read_text()
    doc = json.loads(raw) if raw.strip() else None
    pcr11 = next((p for p in (doc or {}).get("pcrs", []) if p.get("pcr") == 11), None)
    ulog = d / "u.log"
    # bootId is the host kernel's current boot ID (shared with the container); redact it.
    redact = lambda t: re.sub(r'"bootId":"[0-9a-f]{32}"', '"bootId":"REDACTED"', t)
    matches = None if pcr11 is None else pcr11.get("hashMatchesEventLog")
    # Independent replay (does not trust pcrlock): fold the log's sha256 digests from zero
    # and check each digest is sha256 of the logged word.
    replay = None; words_ok = None
    if ulog.exists():
        v = bytes(32); words_ok = True
        for rec in filter(None, ulog.read_text().split("\x1e")):
            r = json.loads(rec); dg = bytes.fromhex(r["digests"][0]["digest"])
            words_ok &= hashlib.sha256(r["content"]["string"].encode()).digest() == dg
            v = hashlib.sha256(v + dg).digest()
        replay = v.hex()
    tpm = (d / "pcr11.txt").read_text().split()[-1].lower().removeprefix("0x")
    ok = matches is want
    ok_all &= ok
    out["cases"][c] = {"expect_pcr11_match": want, "observed_pcr11": pcr11, "control_ok": ok, "independent_replay_of_written_log": replay, "replay_equals_tpm": replay == tpm, "log_digests_are_sha256_of_words": words_ok,
                       "pcrlock_rc": int((d / "log.json.rc").read_text()),
                       "pcrlock_stderr": (d / "log.json.stderr").read_text().splitlines(),
                       "tpm_pcr11": (d / "pcr11.txt").read_text().split(),
                       "userspace_log_records": ulog.read_text().count("\x1e") if ulog.exists() else None,
                       "userspace_log_raw": redact(ulog.read_text()) if ulog.exists() else None,
                       "pcrlock_json": json.loads(redact(raw)) if doc else None}
out["all_controls_ok"] = ok_all
print(json.dumps(out, indent=1))
sys.exit(0 if ok_all else 1)
EOF
