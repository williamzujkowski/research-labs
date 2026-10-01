#!/bin/sh
# Build fetches a pinned image and integrity-locked packages; the experiment runs offline.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "${1:-run}" in run|test) action=${1:-run} ;; *) echo 'Usage: scripts/pnpm-lab.sh [run|test]' >&2; exit 2 ;; esac
docker build --platform linux/amd64 -t research-labs-pnpm:local labs/pnpm-override-drift >&2
image_id=$(docker image inspect research-labs-pnpm:local --format '{{.Id}}')
revision=$(git rev-parse HEAD 2>/dev/null || echo uncommitted)
if test -n "$(git status --porcelain)"; then dirty=true; else dirty=false; fi
if test "$action" = test; then set -- node --test run.test.mjs; else set -- node run.mjs; fi
docker run --rm --platform linux/amd64 --network none --read-only \
  --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges \
  --cpus 2 --memory 512m --memory-swap 512m --pids-limit 128 \
  --ulimit nofile=1024:1024 --ulimit core=0:0 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777 \
  -e "LAB_IMAGE_ID=$image_id" -e "LAB_REVISION=$revision" -e "LAB_DIRTY=$dirty" \
  "$image_id" timeout --signal=KILL 600 "$@"
