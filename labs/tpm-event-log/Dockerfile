# Feasibility image: control-only check, not a finished lab.
# Base pinned by digest; Debian package versions pinned explicitly (resolved 2026-10-01).
FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
RUN apt-get update && apt-get install -y --no-install-recommends \
        swtpm=0.7.1-1.5 swtpm-tools=0.7.1-1.5 tpm2-tools=5.7-1 \
        libtss2-tcti-swtpm0t64=4.1.3-1.2 systemd=257.13-1~deb13u1 python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY labs/tpm-event-log/control.sh /app/control.sh
RUN chmod a+rx /app/control.sh
USER 65532:65532
CMD ["/app/control.sh"]
