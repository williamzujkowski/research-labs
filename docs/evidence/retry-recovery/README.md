# Fixed retry simulation evidence — 2026-09-13

Parameters were frozen in commit `9b85ad8` before matrix execution. The model,
method and sources are in `labs/retry-recovery/`. No paper artifact was run.

This directory retains deterministic gzip copies of the first dirty-worktree
matrix and the subsequent clean-commit run. Decompress with `gzip -dc`; every
record contains exact config/hash, revision, dirty flag, immutable local image
ID, Python/platform, all 54 scenarios, raw counters, terminal latencies/status,
pending ages and embedded CSV timelines. This is a synthetic simulation, not
performance measurements from a network service.

Commands from the repository root:

```sh
./scripts/retry-lab.sh test
./scripts/retry-lab.sh run > /tmp/retry.json
python3 labs/retry-recovery/export.py /tmp/retry.json /tmp/retry-csv
```

The initial Docker test failed because the host's restrictive file modes made
copied tests unreadable to the nonroot runtime. Adding a build-time readability
step fixed it; no runtime privileges were added. All 10 tests then passed.
That initial test failure produced no experiment matrix. Local Docker warned
about missing Buildx and successfully used its existing legacy builder.

## Observations and limits

All 54 predeclared combinations completed below the attempt/resource caps.
Every seed/rate's arrival-schedule hash matches across policies and fault modes.
Do not discard the following negative controls:

- At 4/sec, all no-fault policies have identical successes per seed:682,715,691.
  Yet **none qualifies under the frozen ten-window recovery criterion**. Poisson
  variation makes this criterion too strict even for a healthy control.
- At 18/sec, jitter loses goodput even without the injected slowdown in seeds 11
  and 29. Those runs cannot isolate the injected fault as the cause.
- At 12/sec with fault, no-retry successes are 1707,1715,1681; jitter 686,719,695;
  budget 1435,1572,1470 for seeds 11,29,47 respectively. In this particular model,
  retry budgeting limits amplification relative to unbudgeted jitter but does
  not beat no retries on total original success count. All pending and failed
  originals remain in the raw denominator.

These totals cover the entire 180-second horizon, not just post-trigger work.
Inspect CSV post-trigger arrival cohorts and queue trajectories before arguing
about recovery or fairness. Recovery censoring alone does not establish a
sustaining feedback loop or metastability, especially when controls fail it.
No policy winner, deployed-service finding, Svalinn replication, or publication
approval is claimed. Keep this as an artifact; a post needs a defensible question
and must explain why this frozen recovery metric fails its controls. Further
experiments require a separately recorded plan, not silent tuning of this one.

Clean code revision: `c2b2a349aa9ae6eb1a311876d7d3a08a39a7ad28`, dirty=false.
The clean run reproduced every semantic record in the first run exactly.
All 54 runs satisfy original-request and server-attempt conservation equations.

Independent release review added an explicit matrix-completion exit gate, UTC
start timestamps, and a hard 1,800-second runtime timeout. Eleven container
tests now cover incomplete-matrix/cap rejection and permit complete scientifically
censored controls. The final clean run is retained separately below; prior
observations remain available rather than being overwritten.

Final run: `final-run.json.gz`, code revision `50e8cd0d04bee4d2a05b1bfb2cb189f776dec338`,
started `2026-09-13T06:15:18.496763+00:00`, dirty=false, execution_complete=true.
All 54 semantic run records match both previous matrices exactly. Runtime was
3.676 seconds; recovery censoring was retained without failing execution.

Independent method/security review recomputed all 54 scenarios, shared arrival hashes,
180 windows, request/attempt conservation and identical semantic matrices; all 11
container tests passed. The 1,800-second hard bound covers execution after the
Docker build, not initial image acquisition.
