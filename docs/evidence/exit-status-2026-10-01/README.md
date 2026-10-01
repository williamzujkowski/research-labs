# Exit-status record — October 1, 2026

Executed 2026-10-01 (UTC) from clean implementation commit `70619f6`
(`LAB_DIRTY=false` in the record) with Docker 29.8.1 on Linux amd64. Commands from
the repository root:

```sh
./scripts/exit-status-lab.sh test > tests.txt 2>&1
./scripts/exit-status-lab.sh run > observations.json
```

Both exited 0. `observations.json` is the unedited run output. `tests.txt` is the
unedited combined build log and unittest output (unittest writes to stderr).

All 17 cases matched their stated expectations, including the harness case
(`exit 7` observed as 7). Tool versions in the record: bash 5.2.37, GnuPG 2.4.7,
curl 8.14.1, Python 3.12.14, and the two hash-checked Pi-hole dispatchers.

Observed, in summary:

- `set -e; false | tee out.log; echo REACHED` printed `REACHED` and exited 0;
  with `pipefail` it exited 1. Same split when the failing command first writes
  `fetch failed: 403` to the log.
- `gpg ... --symmetric seeds.txt > backup.gpg` exited 0, left `backup.gpg` at
  0 bytes and wrote 131 bytes of ciphertext to `seeds.txt.gpg`. Decrypting
  `backup.gpg` exited 2. With `--output backup.gpg` the file held 131 bytes and
  decrypted to the original.
- `curl -sO` on the loopback 403 exited 0 and saved the 111-byte XML error as
  `docker-compose.yml`. `curl -fsSO` exited 22 and left no file;
  `--fail-with-body` exited 22 and kept the body; `-fsSO` on a 200 exited 0.
- `pihole -a adlist add <url>` exited 0 on both v6.0 and v6.4.3 with stdout
  byte-identical to `pihole --help`.

Ciphertext hashes differ on every run. The Docker `DOCKER-USER` case was not run
(it requires `NET_ADMIN`); see the lab README.
