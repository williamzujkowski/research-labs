# pnpm override drift

A parent-scoped pnpm override (`"satori>fflate": "0.7.5"`) moves one dependency edge
off a version affected by [GHSA-px8p-9vwx-vf98](https://github.com/advisories/GHSA-px8p-9vwx-vf98).
This lab asks which cheap checks notice when a lockfile stops honouring that override.

```sh
./scripts/pnpm-lab.sh test
mkdir -p results
./scripts/pnpm-lab.sh run > results/pnpm.json
```

The build pulls a digest-pinned Node 22 image, installs pnpm 10.33.0 from an
integrity-locked `tool/package-lock.json` with install scripts disabled, then fills a
package store and a registry-metadata cache from the fixtures. The run uses no network,
host mounts or credentials, runs nonroot on a read-only root with capabilities dropped,
512 MiB memory, 128 PIDs, a 256 MiB tmpfs and a 600-second hard kill. Package install
scripts never run. No satori or fflate code is executed; the lab only resolves, links and
inspects. Tested on linux/amd64.

## Fixtures

One manifest (`satori` 0.33.4 plus the override) and three lockfiles:

| Lockfile | `overrides:` header | `satori` -> `fflate` | `@shuding/opentype.js` -> `fflate` |
| --- | --- | --- | --- |
| `faithful` | present | 0.7.5 | 0.7.5 |
| `no-header` | absent | 0.7.3 | 0.7.5 |
| `header-only` | present | 0.7.3 | 0.7.5 |

`satori` 0.33.4 declares `fflate` as exactly `0.7.3`; `@shuding/opentype.js`
1.4.0-beta.0 declares `^0.7.3`. [`generate-fixtures.sh`](generate-fixtures.sh) records
how each file was produced. `no-header` is a **simulation**: it reproduces the two edges
and the missing header seen in real Dependabot lockfiles in
[williamzujkowski.github.io](https://github.com/williamzujkowski/williamzujkowski.github.io)
(PRs #564 at bot commit `d0160c5`, #635, #638, #662). It does not run Dependabot and says
nothing about Dependabot's code path. `header-only` models a hand repair that restores the
header and nothing else.

## What is measured, per lockfile

- Three static checks on the text: header present; `fflate@0.7.5` present anywhere;
  the `satori` -> `fflate` edge equals the override.
- `pnpm install --frozen-lockfile`, and the `fflate` version actually linked under satori.
- `pnpm dedupe --check` and `pnpm install --lockfile-only` (does regeneration change it?).

Registry metadata is captured at image build; the record includes each cached document's
`modified` time. Re-resolution and dedupe results can differ after the registry changes.

## Limits

One manifest, one override shape, one pnpm version. `pnpm dedupe --check` is clean here
only because the toy tree has nothing else to dedupe; on a real tree it also reports
ordinary duplicates. Whether the vulnerable function is reachable is out of scope:
satori 0.33.4 imports `inflateSync` from fflate, and the advisory concerns `unzipSync`.
