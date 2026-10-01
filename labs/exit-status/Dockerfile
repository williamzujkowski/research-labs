# Reference platform is linux/amd64. Resolve new digests deliberately and rerun evidence.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Resolve packages from the Debian snapshot this base image records, so a rebuild
# installs the same curl and gnupg instead of whatever is current that day.
RUN printf '%s\n' \
      'Types: deb' \
      'URIs: http://snapshot.debian.org/archive/debian/20260824T000000Z' \
      'Suites: trixie trixie-updates' \
      'Components: main' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp' \
      '' \
      'Types: deb' \
      'URIs: http://snapshot.debian.org/archive/debian-security/20260824T000000Z' \
      'Suites: trixie-security' \
      'Components: main' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp' \
      > /etc/apt/sources.list.d/debian.sources \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends curl gnupg \
 && rm -rf /var/lib/apt/lists/*
# Upstream Pi-hole dispatcher, fetched by commit and checked by hash. Not redistributed
# in this repository (EUPL-1.2). Its three sourced helpers are replaced by empty stubs:
# the lab exercises only the argument dispatch, never a Pi-hole installation.
RUN mkdir -p /opt/pihole /opt/pihole-upstream \
 && curl -fsSL -o /opt/pihole-upstream/pihole-v6.0 \
      https://raw.githubusercontent.com/pi-hole/pi-hole/2d81552f9f16fb5e12df31069078b43f0e826c3b/pihole \
 && curl -fsSL -o /opt/pihole-upstream/pihole-v6.4.3 \
      https://raw.githubusercontent.com/pi-hole/pi-hole/f47b8ede5a8e38f9c703202d324a074dbdba4ca9/pihole \
 && printf '%s  %s\n' \
      e4a6338ec7f725435342a7e95f820d5817de2ecc21075b6ab3faebc869f8c5c7 /opt/pihole-upstream/pihole-v6.0 \
      a6ca13ae4de96df06b5a72def9525cfb3a4ad56aa34212f07f483e38fc6ad2b4 /opt/pihole-upstream/pihole-v6.4.3 \
    | sha256sum -c - \
 && : > /opt/pihole/COL_TABLE && : > /opt/pihole/utils.sh && : > /opt/pihole/api.sh
WORKDIR /app
COPY labs/exit-status /app/labs/exit-status
COPY tests/exit_status /app/tests/exit_status
RUN chmod -R a+rX /app /opt/pihole /opt/pihole-upstream
USER 65532:65532
CMD ["python", "labs/exit-status/run.py"]
