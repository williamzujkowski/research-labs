# Exit status: commands that fail while reporting success

Published ops and security instructions can fail without saying so: the command
exits 0, the reader sees success, and the thing it was meant to do did not happen.
This lab runs four such shapes, each beside a corrected form that reports the
failure, and records the exit status and every file left behind.

The shapes come from corrections to William Zujkowski's own blog
([PR 658](https://github.com/williamzujkowski/williamzujkowski.github.io/pull/658),
merged 2026-09-24) plus one uncorrected case found in the same audit. The lab
asks only whether the shell can see the failure. It does not test the tools
those instructions were about (Suricata, Vaultwarden, Wazuh) or any network service.

From the repository root (Docker, Git, POSIX shell; reference linux/amd64):

```sh
./scripts/exit-status-lab.sh test
mkdir -p results
./scripts/exit-status-lab.sh run > results/exit-status.json
```

`run` prints one JSON document: tool versions, image ID, revision, and for each case
the script, exit status, stdout, stderr and the size and SHA-256 of each file left
in its working directory. Exit 0 means every case matched its stated expectation;
exit 3 means at least one did not, and the JSON still records what happened.

## Cases

| Group | Published shape | Observed | Control | Observed |
| --- | --- | --- | --- | --- |
| pipeline | `set -e; false \| tee out.log; echo REACHED` | exit 0, `REACHED` | `set -eo pipefail` | exit 1 |
| gpg | `gpg ... --symmetric seeds.txt > backup.gpg` | exit 0, `backup.gpg` 0 bytes, ciphertext in `seeds.txt.gpg` | `--output backup.gpg`, then decrypt and compare | exit 0, round trip matches |
| curl | `curl -sO <403 URL>` | exit 0, XML error saved as `docker-compose.yml` | `curl -fsSO` | exit 22, no file |
| pihole | `pihole -a adlist add <url>` on v6.0 and v6.4.3 | exit 0, output identical to `--help` | (none: v6 has no CLI equivalent) | |

The table summarizes expectations; the JSON is the record. A harness case
(`exit 7`) checks that the runner can observe a nonzero status at all, and the
unit tests check that the expectation checker can fail.

## Method and limits

- **pipeline.** `false` and a `sh -c` that prints an error and exits 1 stand in
  for a failing `suricata-update`. The result concerns bash 5.2 pipeline status,
  not Suricata.
- **gpg.** The published command was interactive; the lab adds `--batch
  --pinentry-mode loopback --passphrase-file` so it can run unattended. That
  changes how the passphrase arrives, not where gpg writes its output.
- **curl.** A stdlib HTTP server on the container's loopback answers `/denied/*`
  with 403 and a synthetic S3-style `AccessDenied` XML body, and `/ok/*` with
  200 and a small YAML file. No external host is contacted at run time.
- **pihole.** The build fetches upstream's `pihole` dispatcher at two commits
  ([v6.0 `2d81552`](https://github.com/pi-hole/pi-hole/blob/2d81552f9f16fb5e12df31069078b43f0e826c3b/pihole),
  [v6.4.3 `f47b8ed`](https://github.com/pi-hole/pi-hole/blob/f47b8ede5a8e38f9c703202d324a074dbdba4ca9/pihole))
  and checks their SHA-256. The three helper files it sources are replaced by
  empty stubs, so only the argument dispatch runs; v6.4.3 consequently prints a
  `loadVersionFile: command not found` line to stderr. Nothing is installed and
  no Pi-hole service exists. The script is not redistributed here (EUPL-1.2).
- **Not run.** The Docker `DOCKER-USER` case needs `NET_ADMIN` and a Docker
  daemon inside the experiment, which this unprivileged, networkless container
  deliberately lacks. It remains a documented source finding, not an observation
  of this lab.

The runtime container has no network, a read-only root filesystem, no
capabilities, UID 65532, one CPU, 256 MiB, 64 PIDs, a 16 MiB `noexec` `/tmp`, and
a 300-second hard timeout. The build fetches a digest-pinned Python base, curl and
gnupg from the Debian snapshot the base records (`20260824T000000Z`), and the two
hash-checked Pi-hole scripts. Ciphertext differs every run; compare sizes, exit
statuses and file presence, not whole-file JSON hashes.

These are behaviours of specific tool versions in one container. They say nothing
about how often such commands appear in published instructions.

Original code is MIT licensed under this repository's license.
