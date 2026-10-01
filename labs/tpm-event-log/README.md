# TPM event-log controls (feasibility only)

**Status:** control-only feasibility check, 2026-10-01. Not a finished lab; no main
matrix has run and no article claim rests on it yet.

Question for a future lab: when user-space boot measurements live outside the firmware
event log, what does an appraiser conclude about the PCRs it cannot explain? Inspired by
Lacko and Švenda, *TPMSpy: Validation of Measured Boot Systems by Low-Level Tracing of TPM
Usage*, [arXiv:2609.05011v1](https://arxiv.org/abs/2609.05011v1) (submitted 2026-09-04),
§5.2. This is a paper-inspired toy exercise, not a replication: no VM, no firmware, no
interposer, and swtpm stands in for a TPM.

```sh
./scripts/tpm-control.sh > results/tpm-control.json
```

Inside one unprivileged, offline, read-only container (Debian trixie, pinned by digest;
swtpm 0.7.1, tpm2-tools 5.7, systemd 257.13), each case starts a fresh swtpm, runs the
real `systemd-pcrextend` for the four boot phases (`enter-initrd`, `leave-initrd`,
`sysinit`, `ready`) into PCR 11 with its user-space log redirected to a scratch file, and
asks the real `systemd-pcrlock log --json=short` whether PCR 11 matches the log.
`SYSTEMD_FORCE_MEASURE=1` bypasses the UKI check; the firmware log is `/dev/null`.

| Case | Setup | Expected `hashMatchesEventLog` |
| --- | --- | --- |
| c1 healthy | Phases extended and logged; appraiser reads that log | true |
| c2 negative | Same extends; appraiser is given an absent user-space log | false |
| c3 negative | Logged phases plus one unlogged PCR 11 extend | false |

The script also replays the written log independently (sha256 fold from zero) and checks
each digest is sha256 of its logged word, so the healthy control does not rest on pcrlock
alone. It exits nonzero if any control misbehaves. `bootId` (the host kernel's boot ID,
visible inside the container) is redacted from retained output.

## Evidence

[`docs/evidence/tpm-event-log-feasibility/`](../../docs/evidence/tpm-event-log-feasibility/):

- `run1-vacuous-c2.json`: **the first run failed its negative control.** c2 reported
  `hashMatchesEventLog: true` with no calculated or observed value. Cause, from the
  v257 source (`event_log_pcr_checks_out` loops over `el->n_algorithms`): with an empty
  firmware log and no declared bank, pcrlock knew zero hash algorithms, so the comparison
  ran zero times and passed vacuously. That is a harness artifact, because a real
  firmware log declares its banks. Fixed by `SYSTEMD_TPM2_HASH_ALGORITHMS=sha256`.
- `run2.json`, `run3.json`: all three controls behave; PCR 11 records identical across
  both runs. c1 calculated = observed =
  `38d2047d0545f701a253005037bd1d1662e5f59388885f9e9443f38e2f23531e`.

Observed but not yet interpreted: `pcrlock log` exited 0 in every case, including both
mismatches. It is a reporting command; nothing here says it should gate.

## Limits

No firmware log, no IMA, no PCR 15, no `predict`/`make-policy`, no sealing or unsealing.
Apt packages are version-pinned but not snapshot-pinned, so a rebuild after Debian
removes these versions will fail rather than drift.
