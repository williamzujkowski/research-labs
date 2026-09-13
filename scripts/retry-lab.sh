#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "${1:-run}" in run|test) action=${1:-run} ;; *) echo 'Usage: scripts/retry-lab.sh [run|test]' >&2; exit 2 ;; esac
docker build --platform linux/amd64 -f labs/retry-recovery/Dockerfile -t research-labs-retry:local . >&2
image_id=$(docker image inspect research-labs-retry:local --format '{{.Id}}')
revision=$(git rev-parse HEAD)
if test -n "$(git status --porcelain)"; then dirty=true; else dirty=false; fi
if test "$action" = test; then
    set -- python -m unittest discover -s tests/retry_recovery -v
else
    set -- python labs/retry-recovery/simulate.py
fi
docker run --rm --platform linux/amd64 --network none --read-only \
    --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges \
    --cpus 1 --memory 512m --memory-swap 512m --pids-limit 32 \
    --ulimit nofile=64:64 --ulimit core=0:0 --ulimit cpu=1800:1800 \
    -e "LAB_IMAGE_ID=$image_id" -e "LAB_REVISION=$revision" -e "LAB_DIRTY=$dirty" \
    "$image_id" "$@"
