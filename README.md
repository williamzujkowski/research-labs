# Research labs

Small, reproducible experiments behind [William Zujkowski's field reports](https://williamzujkowski.github.io/).
Each lab asks a bounded question, retains its inputs and raw observations, and states what it cannot establish.

The first lab compares ZIP readers using six tiny, original, harmless archives.
It is a paper-inspired API experiment, not a full ZipDiff replication or a security scanner.

## Available labs

| Lab | Question | Run instructions |
| --- | --- | --- |
| ZIP readers | Do indexed and streaming APIs observe the same entries? | [ZIP pilot](labs/zip-differentials/README.md) |
| Collaborative score | Can equal replicas keep valid text but change lane assignment? | [Historical Yjs traces](labs/music-traces/README.md) |

## Try the ZIP lab

Install Git and Docker Engine or Docker Desktop with Linux-container support. From a POSIX shell
(on Windows, use WSL):

```sh
git clone https://github.com/williamzujkowski/research-labs.git
cd research-labs
mkdir -p results
./scripts/lab.sh test
./scripts/lab.sh run > results/zip.json
```

The first build downloads two digest-pinned base images; allow roughly 2 GB of free disk space.
After the images are cached, the build needs no package downloads. Experiment execution is offline.
The reference platform is **linux/amd64**. ARM hosts need Docker's amd64 emulation; this has
not been validated here. A container fixes user-space dependencies, not the host kernel or CPU.
No Python, Java, pip, or package manager installation is needed on the host.

`test` runs the regression suite in the same container. `run` writes a JSON evidence record to
stdout; build logs go to stderr. Keep the exit status: nonzero means infrastructure failure,
timeout, harness limit, or failed control. Expected parser rejection of a variant is a recorded
observation and does not itself fail the experiment. CI executes both commands and retains the
raw run as an artifact, including failed runs when a report exists.

The wrapper uses an immutable built image ID, a non-root user, a read-only root filesystem,
no networking, no host mounts, no capabilities, and bounded memory, processes and temporary
storage. It passes no credentials and never extracts archive entries to disk or executes them.
This setup is for the fixed inert corpus only; it is not a VM or a sandbox for arbitrary
hostile archives. See [method and interpretation](labs/zip-differentials/README.md).

## What is retained

- Deterministic fixture generator and checked SHA-256 inventory.
- Ordered entry names, sizes, content hashes and benign-marker decisions before any overwrite.
- Adapter stdout/stderr, exit status, partial observations and distinct error classifications.
- Python/JDK versions, architecture, kernel, source hashes, source revision/dirty state and image ID.
- [Reviewed reference observations](docs/zip-reference.md), including negative results and failed setup attempts.

Timestamps and host details differ between runs. Compare fixture hashes and parsed observations,
not whole-file JSON hashes. Base images are pinned for repeatability, not promised to stay
security-current. Updating a digest requires rerunning the controls and retaining new evidence.

## Contributing another lab

Start with a question and an issue. Document sources, licenses, fixtures, resource limits,
controls, stop conditions and potential falsification. Keep code here and link blog articles
to an immutable commit or release. Do not add a lab solely to populate a directory.

[AGENTS.md](AGENTS.md) provides the same project guidance for any coding harness.
Original code and documentation are MIT licensed; upstream runtimes retain their own licenses.
