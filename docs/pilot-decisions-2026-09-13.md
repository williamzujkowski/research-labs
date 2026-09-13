# Pilot decisions — September 13, 2026

The three prioritized feasibility passes are complete. Reproducibility is useful
independently of whether an experiment earns an article. None of the decisions
below extends a toy result to an untested product or silently retunes a failed control.

| Pilot | Evidence | Editorial disposition |
| --- | --- | --- |
| ZIP APIs | Six fixtures; 23 tests; local and CI observations match | Standalone article justified by a small content-identity regression case; website review schedules September28 after the existing September21 article |
| Music traces | Historical Yjs13.6.8 trace reproduced;13 tests; both controls pass; invented score stays valid while assignment changes | Retain artifact; standalone music article shelved after independent skeptical review |
| Retry simulation | 54 predeclared scenarios;11 tests; complete raw matrices retained; recovery criterion fails healthy controls | Retain artifact; no retry-recovery article scheduled from this evidence |

## Music: a useful artifact has not yet become a distinct article

An independent reviewer who did not author the music lab inspected its trace and
the portfolio's gate. The score replaces the historical `a`, `b`, `x` elements
with a drum header, event and bass section. The invented grammar permits the
resulting reassignment. That separates syntax from application meaning, but it
adds no real editor decision or tested alternative representation.

The existing June music article concerns isolated browser sessions. This lab
establishes no defect in those sessions, current Yjs, Y.Text, Strudel or audio.
Do not insert a warning that implies such a connection. Reopen the article only
for a named same-document editing requirement, realistic operation granularity,
one explicit event-to-lane invariant, and a bounded comparison against stable
identities with tradeoffs. The current historical trace remains available as-is.

[Music evidence](evidence/music-traces-2026-09-13/README.md);
[website proposal589](https://github.com/williamzujkowski/williamzujkowski.github.io/issues/589).

## Retries: the recovery metric does not distinguish the healthy control

The fixed 95%-of-baseline-for-ten-windows criterion fails low-load no-fault
controls. At the highest load, jitter also degrades without the injected fault
in two seeds. A censored recovery time therefore cannot establish metastability.
Independent review verified request/attempt conservation and all54 conditions;
this is a limitation of the chosen question/criterion, not hidden missing runs.

Any follow-up needs a new plan, recorded before execution, that validates its
recovery criterion against healthy traffic and distinguishes existing overload
from a fault-sustained state. Preserve these original matrices and their negative
controls. No automatic parameter search or new implementation is authorized by
this note alone; follow the active task's actual scope.

[Retry evidence](evidence/retry-recovery/README.md);
[website proposal588](https://github.com/williamzujkowski/williamzujkowski.github.io/issues/588).

## Review record

Root reviewed code, method, limits and provenance for both new labs. An
independent reviewer verified all54 retry scenarios and conservation equations.
The music author implemented root's UTC timestamp/exact-control gate findings;
the retry author implemented completion gates/UTC/hard wall limit. Root reran
music's13 container tests; the independent retry reviewer reran its11 tests.
All PR workflows passed before merge. Original plan/source/evidence commits
remain reachable through merge commits, including the retry parameters frozen
before execution. The root README now links each lab's actual run commands.

Deferred DNS cache, retention and IoT proposals remain outside these pilots. They
retain the website portfolio's earlier gates rather than gaining artificial
publication slots because these experiments completed.
