#!/bin/sh
# Build fetches pinned bases, snapshot packages and hash-checked upstream scripts.
# Runtime has no network (the HTTP fixture listens on the container's loopback only).
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "${1:-run}" in run|test) action=${1:-run} ;; *) echo 'Usage: scripts/exit-status-lab.sh [run|test]' >&2; exit 2 ;; esac
docker build --platform linux/amd64 -f labs/exit-status/Dockerfile -t research-labs-exit-status:local . >&2
image_id=$(docker image inspect research-labs-exit-status:local --format '{{.Id}}')
revision=$(git rev-parse HEAD 2>/dev/null || echo uncommitted)
if test -n "$(git status --porcelain)"; then dirty=true; else dirty=false; fi
if test "$action" = test; then
    set -- python -m unittest discover -s tests/exit_status -v
else
    set -- python labs/exit-status/run.py
fi
docker run --rm --platform linux/amd64 --network none --read-only \
    --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges \
    --cpus 1 --memory 256m --memory-swap 256m --pids-limit 64 \
    --ulimit nofile=256:256 --ulimit core=0:0 \
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
    -e "LAB_IMAGE_ID=$image_id" -e "LAB_REVISION=$revision" -e "LAB_DIRTY=$dirty" \
    "$image_id" timeout --signal=KILL 300 "$@"
