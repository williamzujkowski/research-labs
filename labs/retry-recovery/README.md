# Retry recovery simulation

A small event simulator compares useful original-request completions against
retry attempts after a temporary slowdown. It models one FIFO server; it does
not benchmark a real service or reproduce the OSDI artifact.

From the repository root (Docker, Git, POSIX shell; reference linux/amd64):

```sh
./scripts/retry-lab.sh test
mkdir -p results/retry
./scripts/retry-lab.sh run > results/retry/observations.json
python3 labs/retry-recovery/export.py results/retry/observations.json results/retry/csv
```

Only the build fetches a digest-pinned Python base; runtime has no network or host
mounts, runs as UID 65532 with a read-only root and no capabilities, and is capped
at one CPU and 512MiB. Stdout carries observations to the caller. Unit tests
need no services. No dependencies beyond the standard library. An editor may
work in the checkout; a privileged/devcontainer Docker socket is unnecessary.
The host Python command only exports trusted local JSON to CSV; it runs no simulation.

[PLAN.md](PLAN.md) and [config.json](config.json) were committed before the first
matrix run. All 54 combinations are mandatory, including low-load and no-fault
controls. Every run preserves original terminal latency/status, pending ages,
server work remaining at cutoff, all admission/timeout/completion counters,
arrival-schedule hash, and its full CSV timeline. Exported timeline numbers match
zero-based run order in JSON. `summary.csv` provides the mapping and comparisons.
Runtime metadata and exact config travel with observations. Ignore wall duration,
image ID and revision when comparing semantic results from separate builds.

Model details: successful response at exactly the timeout/deadline wins that tie.
A failed attempt leaves its server work queued or running. Retry delays are full
jitter in [0,min(1,0.1*2^(attempt_number-1))]; at most three attempts total. Budget
mode admits at most a burst of four retries plus two tokens/second, shared by the
whole simulated client process. Denial terminates that original. New arrivals
bypass the retry bucket; they still share server FIFO admission. Queue capacity
is 256 waiting attempts plus one in service. Work that starts during the slow
phase keeps its slow service duration even if the trigger ends meanwhile.

The ten-window recovery criterion is intentionally frozen and may be too strict
for noisy Poisson arrivals. A censored recovery time alone is **not evidence of
metastability**; examine the no-fault control and the CSV trajectory. Empty
baseline also yields censoring. The finite horizon cannot prove permanence.
No universal policy recommendation, causal claim about a deployed system, or
paper-result replication follows from these runs. No parameter sweep may be
silently discarded to improve the story. A different model is a new experiment.

## Source provenance

Reviewed 2026-09-13, before proposed publication; no code or figures copied:

- Huang et al., [Metastable Failures in the Wild](https://www.usenix.org/conference/osdi22/presentation/huang-lexiang),
  OSDI 2022, pp. 73–90; [paper](https://www.usenix.org/system/files/osdi22-huang-lexiang.pdf).
  Background on sustaining degradation after a temporary trigger. The authors'
  [public explanation](https://www.usenix.org/publications/loginonline/metastable-failures-wild)
  explicitly describes sustaining effects resisting recovery. This lab does not
  execute their artifact or reproduce its experiments.
- Marc Brooker, [Timeouts, retries, and backoff with jitter](https://d1.awsstatic.com/builderslibrary/pdfs/timeouts-retries-and-backoff-with-jitter.pdf),
  Amazon Builders' Library, existing prior art for local token-bucket retry
  limits and jitter. Our hard denial and fixed-refill bucket are stated model
  choices, not a claim to match an AWS SDK's complete retry behavior.
- [Website proposal 588](https://github.com/williamzujkowski/williamzujkowski.github.io/issues/588)
  and its 2026-09-13 review select this original retry question; Svalinn's separate
  multi-resource overload-control question is explicitly deferred.

Original implementation is covered by this repository's MIT license. The
sources retain their own copyrights; a citation grants no artifact license.
