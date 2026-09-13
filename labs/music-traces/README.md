# Inert collaborative score traces

This small lab reproduces a historical Yjs insertion-order example and asks a
separate application question: can replicas agree on a syntactically valid score
while an event moves under a different lane header? It uses a toy row grammar,
not Strudel, MIDI, an audio engine or a production collaborative editor.

From the repository root, with Docker and Git installed:

```sh
./scripts/music-lab.sh test
mkdir -p results
./scripts/music-lab.sh run > results/music.json
```

The first build downloads a digest-pinned Linux amd64 Node image and integrity-
locked npm packages. `npm ci` disables install scripts. The runtime uses no
network, host mounts or Docker socket; it runs nonroot with a read-only root,
capabilities removed, 512 MiB memory, 2 CPUs, 64 PIDs and a 900-second hard kill.
It contains four fixed traces, three insertions each, no random seeds and no
execution of the resulting score. These are tiny synthetic inputs, not a sandbox
for hostile JavaScript. Docker shares the host kernel. An amd64 host is the tested
platform; an ARM Docker host needs amd64 emulation, which this lab has not tested.
A development container is unnecessary for the two commands above.

## What is measured

| Trace | Purpose |
| --- | --- |
| `appendix-a-a9` | Reproduce Yjs 13.6.8's three-replica backward insertion schedule. |
| `sequential-control` | Communicate every edit before the next; preserve `ab` in `abx`. |
| `disjoint-control` | Concurrently insert at opposite ends of an already shared separator. |
| `inert-score-lanes` | Apply the historical schedule to complete score rows and inspect lane assignment. |

The API is `Y.Array` with string elements, matching the published example. An
array element can contain more than one character or row; this does not measure
character-by-character `Y.Text` editing. Fixed client IDs 1, 2 and 3 are assigned
to fresh in-memory documents to reproduce the paper's ordering. This is deliberate
test setup, not advice to hard-code production replica IDs.

Each insertion records all causally known operation IDs, the generated update's
base64 bytes, length and SHA-256. Each delivery checks those predecessors before
applying the update and logs its receiver and resulting array. Final arrays,
strings, operation sets and encoded-state sizes are retained for all replicas.
The receiver traversal order test is a small additional schedule check, not an
exhaustive delivery permutation study. Timings are contextual, not a benchmark.

Three independent measurements prevent an attractive but wrong conclusion:

- Replica equality compares the arrays after every generated operation reaches
  every replica. Passing these finite traces is not a proof of convergence.
- Run contiguity asks whether two specified unique array elements remain adjacent
  and in order. It is not the paper's formal maximal-non-interleaving predicate.
- Syntax checks an invented, inert grammar: a `drums:` or `bass:` header selects
  the lane for subsequent `bd`, `sd`, `c2` or `d2` rows. Every row ends in a newline.
  Empty lanes are allowed; events must follow a header. This grammar deliberately
  permits an event in either lane, so assignment is distinct from validity.

The score trace has three IDs but two editing sessions: ID 3 adds `bd`, then
ID 1 receives it and prepends `drums:`; ID 2 independently inserts a bass section.
Before merging, ID 1 assigns `bd` to drums. The observed merged rows are:

```text
drums:
bass:
c2
bd
```

All replicas agree and this toy grammar accepts the result. The `bd` row now
belongs to bass, while the header and event insertion run is split. This supports
an application design question about explicit event-to-lane identity versus
implicit adjacency. It does not establish audible effects, user intent, a Strudel
bug, or the efficacy of a proposed fix. The original “broken drum pattern” title
would overstate the evidence: syntax remains valid in this fixture.

## Sources, versions and limits

The source finding is Appendix A-A9 of Weidner and Kleppmann,
[*The Art of the Fugue*, arXiv v3](https://arxiv.org/html/2305.00583v3#A1.SS1.SSS9),
revised October 21, 2025. The
[author artifact](https://github.com/mweidner037/fugue/tree/31e74fea67f23add13a5d10f781c0d78edcd14da/yjs-interleave)
is pinned to commit `31e74fea67f23add13a5d10f781c0d78edcd14da`.
`source-manifest.json` retains the inspected source URLs and SHA-256 values.

The original harness here calls Yjs 13.6.8 with lib0 0.2.87 and isomorphic.js 0.2.5
(the transitive versions in the pinned artifact's root lockfile). Our own npm
lockfile includes their exact URLs and integrity digests. The Node runtime is
22.23.2, not the artifact's historical Node 18.15.0. This reproduces a historical
library trace in a pinned modern runtime, not the entire original environment or
any statement about current Yjs. An initial development run used lib0 0.2.117;
that also produced the expected strings, but retained evidence and final tests
use 0.2.87. An initial container test exposed restrictive source-file permissions;
the Docker build now explicitly grants read/traverse access before switching user.

The artifact's MIT license covers `yjs-interleave`, but explicitly excludes
`b4-editing-trace.js` and the `fugue/` directory. Neither excluded code, benchmark
data nor any algorithm implementation is vendored here. The inspected upstream
license is retained in `UPSTREAM-LICENSE.txt`; npm installs each dependency's own
license. The historical schedule is attributed even though instrumentation and
music example are original.

Fugue and FugueMax are different algorithms; this lab runs neither. It cannot
compare their results or establish their guarantees. The authors'
[2019 errata](https://martin.kleppmann.com/2019/03/25/papoc-interleaving-anomalies.html)
remain relevant prior-art context; the superseded algorithm is not implemented.
We stop after these four traces. No broad benchmark, random search, delete trace,
current-version survey or article-publication claim is included.

Related proposal: [website #589](https://github.com/williamzujkowski/williamzujkowski.github.io/issues/589).
