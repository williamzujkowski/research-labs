#!/bin/sh
# Acquisition uses network; the fixed in-memory experiment does not.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "${1:-run}" in run|test) action=${1:-run} ;; *) echo 'Usage: scripts/music-lab.sh [run|test]' >&2; exit 2 ;; esac
docker build --platform linux/amd64 -t research-labs-music:local labs/music-traces >&2
image_id=$(docker image inspect research-labs-music:local --format '{{.Id}}')
revision=$(git rev-parse HEAD 2>/dev/null || echo uncommitted)
if test -n "$(git status --porcelain)"; then dirty=true; else dirty=false; fi
if test "$action" = test; then set -- node --max-old-space-size=384 --test trace.test.mjs; else set -- node --max-old-space-size=384 run.mjs; fi
docker run --rm --platform linux/amd64 --network none --read-only \
  --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges \
  --cpus 2 --memory 512m --memory-swap 512m --pids-limit 64 \
  --ulimit nofile=256:256 --ulimit core=0:0 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
  -e "LAB_IMAGE_ID=$image_id" -e "LAB_REVISION=$revision" -e "LAB_DIRTY=$dirty" \
  "$image_id" timeout --signal=KILL 900 "$@"
