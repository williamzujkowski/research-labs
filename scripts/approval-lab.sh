#!/bin/sh
# Build fetches a pinned image, pinned Debian packages and integrity-locked npm packages.
# Every experiment runs offline, nonroot, with capabilities dropped and a read-only root.
#   approval-lab.sh test      unit tests, then the plain arms end to end
#   approval-lab.sh run       plain arms (JSON on stdout)
#   approval-lab.sh sandbox   sandbox-runtime arms (JSON on stdout); see the README for
#                             why this mode relaxes the container's seccomp and AppArmor
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "${1:-run}" in run|test|sandbox) action=${1:-run} ;; *) echo 'Usage: scripts/approval-lab.sh [run|test|sandbox]' >&2; exit 2 ;; esac
docker build --platform linux/amd64 -t research-labs-approval:local labs/approval-scope >&2
image_id=$(docker image inspect research-labs-approval:local --format '{{.Id}}')
revision=$(git rev-parse HEAD 2>/dev/null || echo uncommitted)
if test -n "$(git status --porcelain)"; then dirty=true; else dirty=false; fi
relax=""
case "$action" in
  test) set -- node --test run.test.mjs ;;
  run) set -- node run.mjs ;;
  sandbox) set -- node run.mjs sandbox
    # bubblewrap needs to create user namespaces, which Docker's default seccomp and
    # AppArmor profiles refuse. The container stays nonroot, capability-free and offline.
    relax="--security-opt seccomp=unconfined --security-opt apparmor=unconfined" ;;
esac
# shellcheck disable=SC2086
docker run --rm --platform linux/amd64 --network none --read-only \
  --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges $relax \
  --cpus 2 --memory 1g --memory-swap 1g --pids-limit 256 \
  --ulimit nofile=1024:1024 --ulimit core=0:0 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  --tmpfs /work:rw,exec,nosuid,nodev,size=256m,mode=1777 \
  -e "LAB_IMAGE_ID=$image_id" -e "LAB_REVISION=$revision" -e "LAB_DIRTY=$dirty" \
  "$image_id" timeout --signal=KILL 600 "$@"
