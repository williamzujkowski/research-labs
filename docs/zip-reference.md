# ZIP pilot reference observations

Run date: 2026-09-13 UTC. This record accompanies the first fixed corpus; it is not a blog publication decision.
The full retained JSON is [zip-reference.json](evidence/zip-reference.json).

## Observations

The reference runtime is CPython 3.12.14 and Temurin OpenJDK 21.0.12+8-LTS on Linux amd64,
using the two base-image digests in the Dockerfile. The raw record identifies the exact source
revision, source hashes, built image ID, host kernel and timestamp.

| Input | CPython indexed | Java indexed | Java streaming | Meaning within this pilot |
| --- | --- | --- | --- | --- |
| control | Ordinary entry | Same | Same | Known expected bytes, not just agreement |
| duplicate-marker-first | Both records | Same | Same | No marker-decision disagreement |
| duplicate-marker-last | Both records | Same | Same | No marker-decision disagreement |
| central-order-reversed | Central order | Central order | Local order | Order differs; marker decision agrees |
| local-central-name-conflict | Rejected | `index.txt` | `local.txt` | Rejection retained; accepted names differ |
| local-entry-absent-from-index | Ordinary entry only | Same | Ordinary plus marker entry | Accepted marker decisions differ |

All 18 adapter executions complete: 17 successes and one parser rejection. Of six inputs,
three have differing accepted entry sequences, including an order-only case. Only the omitted
central-directory-entry fixture has differing accepted marker decisions. These denominators
describe six hand-selected fixtures and are not prevalence estimates.

The extra local record intentionally violates the format's record correspondence requirement.
The marker result demonstrates the exact wrapper/API composition, not malicious payload detection,
a vulnerable product, native filesystem extraction, or a previously unknown parser defect.
No generated archive is executed. Both duplicate controls are useful negative results.

## Reproduction and failed attempts

Commands from the repository root:

```sh
./scripts/lab.sh test
./scripts/lab.sh run > /tmp/zip-reference.json
```

The final container test run passed all 23 tests, including real Java duplicate-identity and
entry/byte boundary checks for both APIs; none were skipped.

The initial container build compiled successfully but the run failed with permission denied on
`run.py`: the source directory permissions inherited the local restrictive umask. The Dockerfile
now explicitly makes `/app` readable/traversable before switching to the non-root runtime user.
The subsequent run passed. This host lacks the optional Docker buildx plugin; Docker 29.8.0
used its legacy builder successfully and printed a deprecation warning. No host configuration
was changed to suppress it. CI exercises the standard hosted Docker build path separately.

JSON timestamps, source revision/dirty state and kernel identity can differ between runs.
Fixture hashes and parsed observations are the comparison surface. The retained reference has
its exact code revision and is not claimed to have a byte-identical host environment elsewhere.

## Review and decisions

- Independent source/Java adapter review (`zip_design_review`): verified duplicate entry identity,
  JSON escaping, entry/byte limits, and local-versus-central API semantics; required naming the
  experiment as three API paths across two implementations.
- Independent tests (`lab_tests`): caught malformed adapter JSON being treated as an observation.
  Corrected to `adapter-error` with raw stdout/stderr retained.
- Independent security/accuracy review (`lab_security_review`): approved the fixed inert corpus
  and constrained runtime subject to an exact expected-control gate and retained evidence.
  Added the gate so three agreeing empty or wrong outputs cannot pass. Corrected documentation
  to distinguish completed entries before failure from bytes of the failing entry.
- Root review: inspected source and actual observations; retained all negative results and the
  failed setup attempt; scoped claims to API enumeration and the benign marker check.

Nexus plan vote `job-vote-7cd495d1-dd17-4632-beb1-c5015df15095`, producer 8.49.3, completed with
**one approval and two rejections** (quick-mode supermajority, fail-closed; all three roles used
`gemini-3.1-pro-preview`; no simulated votes). It is not recorded as approval. The architect and
scope steward evaluated the work against the Nexus repository's mission, despite the proposal
identifying this dedicated research repository. The security reviewer approved the technical plan.
The scope reviewer also raised existing prior art; this pilot credits that work and claims neither
novelty nor a replacement fuzzer. [Raw vote](nexus-plan-vote.json).

This is the known [upstream repository-context defect](https://github.com/nexus-substrate/nexus-agents/issues/6107).
No favorable-result retry was made. We used the website's documented independent-review fallback,
with existing user authorization for the repository and implementation. Future blog publication
still needs its own source, argument and editorial reviews.
