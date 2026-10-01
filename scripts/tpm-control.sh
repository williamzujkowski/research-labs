#!/bin/sh
# Control-only feasibility check for a proposed TPM event-log lab. Build fetches a
# digest-pinned Debian base and pinned packages; runtime has no network or host mounts.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
docker build --platform linux/amd64 -f labs/tpm-event-log/Dockerfile -t research-labs-tpm:local . >&2
image_id=$(docker image inspect research-labs-tpm:local --format '{{.Id}}')
echo "image $image_id" >&2
docker run --rm --platform linux/amd64 --network none --read-only \
    --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges \
    --cpus 1 --memory 512m --memory-swap 512m --pids-limit 64 \
    --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
    "$image_id" timeout --signal=KILL 120 /app/control.sh
