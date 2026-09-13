# Fixed retry simulation evidence — 2026-09-13

Parameters were frozen in commit 9b 85ad 8 before matrix execution. The model,
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
python 3 labs/retry-recovery/export.py /tmp/retry.json /tmp/retry-csv
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
