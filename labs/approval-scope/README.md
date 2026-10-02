# Approval scope: what one install command runs

A coding-agent permission rule such as `Bash(npm install *)` matches the command text.
This lab records what that one command then starts and writes: lifecycle scripts from the
project and from a dependency, files inside and outside the project, and a git hook that
runs later under a second, separately approved command (`git commit`).

```sh
./scripts/approval-lab.sh test               # parser tests, controls, one positive arm
mkdir -p results
./scripts/approval-lab.sh run > results/approval-plain.json
./scripts/approval-lab.sh sandbox > results/approval-sandbox.json
```

No model, agent or harness runs here. The permission-rule semantics come from the vendor's
documentation; the lab measures only the process and file behaviour of the commands.

## Fixture

`fixture/app` is a synthetic project. Its `postinstall` runs `canary.js`; its `prepare`
runs `install-hook.js`, which writes `.git/hooks/pre-commit` (the pattern hook managers such
as simple-git-hooks use). `fixture/canary-dep` is a synthetic dependency, packed into the
app's `vendor/` at image build, whose `postinstall` also runs `canary.js`. Every payload only
writes the fixed string `canary:<label>` to two places: `<project>/.canary/<label>` and
`$CANARY_OUTSIDE_DIR/<label>`, a directory beside the project standing in for "anywhere
else". Payloads catch their own errors and print the outcome, so a denied write is recorded
rather than aborting the install. Lockfiles are generated at build with `--ignore-scripts`.

## Arms

Each arm copies the fixture into a fresh git repository, runs one install under
`strace -f`, then runs `git commit --allow-empty` under `strace -f`, unsandboxed.

| Arm | Command |
| --- | --- |
| controls | `npm install --ignore-scripts`, `npm ci --ignore-scripts`, `pnpm install --frozen-lockfile --ignore-scripts` |
| npm | `npm install`, `npm ci`, `npm install --foreground-scripts` |
| pnpm | `pnpm install --frozen-lockfile`; again with `onlyBuiltDependencies: [canary-dep]` |
| sandbox mode | `npm install --ignore-scripts` (control), `npm install`, `pnpm install --frozen-lockfile`, each wrapped in `srt` |

Controls run first. `run.mjs` stops with exit 3 if a control fails to exit 0, is not traced,
starts no process at all, or shows any lifecycle script or marker. Offline flags
(`--offline`, `--no-audit`, `--no-fund`, a local pnpm store) keep the run hermetic.

Recorded per arm: exit status; every successful `execve`; the `sh -c` commands the package
manager started (its lifecycle scripts); which of those the command's own output names;
attempted file mutations (open for write, create, mkdir, rename, unlink, chmod, link) grouped
by location with their errno; marker files; whether a pre-commit hook exists; whether
`git commit` ran it. Plain mode also records `npm query` over an `--ignore-scripts` install
(the look-before-you-approve inventory) and what `srt` does when it cannot build its sandbox.

## The sandbox arms

`srt` is [`@anthropic-ai/sandbox-runtime`](https://github.com/anthropics/sandbox-runtime)
0.0.78, the package Claude Code's documentation says its Bash sandbox is built on. The settings
mirror the documented Claude Code defaults: writes allowed to the project and a temp directory,
no allowed network domains. This is `srt` run directly, not Claude Code: Claude Code computes
its own configuration (more protected paths, for one) and adds a permission layer on top.

bubblewrap needs unprivileged user namespaces, which Docker's default seccomp and AppArmor
profiles refuse. Sandbox mode therefore runs the container with `seccomp=unconfined` and
`apparmor=unconfined`; it stays nonroot, capability-free, offline and read-only. `srt` also
cannot mount a fresh `/proc` inside an unprivileged container, so the settings enable its
documented `enableWeakerNestedSandbox` mode, which binds the existing `/proc` instead. The
vendor describes that mode as considerably weaker; the filesystem write rules this lab
measures are the same bind-mount mechanism in both modes, but process isolation is not, and
this lab says nothing about it.

## Limits

One synthetic project, one dependency, one hook pattern, npm 10.9.8 and pnpm 10.33.0 on
Node 22 and git 2.39.5, linux/amd64. Network effects are out of scope (the container has no
network). `strace` resolves no relative paths; mutations on relative paths are reported as
such and not attributed to a location. A real hook manager or build script may fail loudly
where these payloads catch their errors. No agent, model or Claude Code binary is exercised,
so nothing here measures what a permission prompt displays.
