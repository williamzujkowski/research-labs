# Music trace feasibility record — September 13, 2026

Executed from clean implementation commit
`794c090` with Docker on Linux amd64. Commands from the repository root:

```sh
./scripts/music-lab.sh run > /tmp/music-reviewed-observations.json
./scripts/music-lab.sh test > /tmp/music-reviewed-tests.txt
npm audit --omit=dev --prefix labs/music-traces --json
```

`observations.json` is the unedited run output; `tests.tap` is the unedited test
output. Docker build messages were stderr. The audit ran against the same lockfile
before the implementation commit and reported no known package vulnerabilities;
that does not establish absence of vulnerabilities or scan the image's OS packages.

The pinned historical Yjs three-ID trace produced `axb` on all three replicas.
The sequential and disjoint controls produced `abx` and `a|x`, respectively, with
all original operations delivered. The toy music score converged and passed its
row grammar, yet its `bd` event moved from the drums lane to the bass lane. These
are four deterministic, three-operation observations, not universal guarantees.
Raw update bytes and causal-delivery records are included in the JSON.

Thirteen tests passed, including replay into a fresh document, causal-predecessor
rejection before mutation, duplicate-update delivery, both controls, separate score
syntax and lane-assignment checks, a different receiver traversal order, exact-control gating against agreeing empty
results, missing-corpus detection and preservation of historical non-reproduction.

Feasibility decision: the historical trace reproduces. The music example provides
an application-invariant question beyond syntax, but a production editor comparison,
remedy, listening experiment and publication review have not been done. Keep the
article proposal open. Avoid a title claiming two replicas or broken syntax; this
fixture uses three IDs, and its syntax remains valid. See the lab README for source
provenance, license exceptions, development corrections and further limits.

No paid services, live audio, user documents, random search or upstream benchmark
campaign was used. Implementation and the fixed run are bounded separately from
future editorial work. Root independently reviewed code, method and security. Its requested additions
(run UTC timestamp and exact expected control arrays) were implemented before
this retained run. Tests and consensus do not substitute for publication review.
