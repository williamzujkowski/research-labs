# Reference platform linux/amd64. Build fetches a pinned image, pinned Debian packages and
# integrity-locked npm packages; every experiment runs offline.
FROM node:22-bookworm-slim@sha256:4d676821dff059fd00d277ee4261ef34ea712317fed0737c03941481b5760c96
RUN apt-get update && apt-get install -y --no-install-recommends \
      strace=6.1-0.1 git=1:2.39.5-0+deb12u3 bubblewrap=0.8.0-2+deb12u1 \
      socat=1.7.4.4-2 ripgrep=13.0.0-4+b2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /lab
COPY tool/package.json tool/package-lock.json ./tool/
RUN cd tool && npm ci --ignore-scripts --no-audit --no-fund && npm cache clean --force
COPY fixture ./fixture
# Build the fixture template: pack the synthetic dependency into the app's vendor/ and
# generate both lockfiles. Every step here passes --ignore-scripts; no canary runs at build.
RUN set -eu; T=/lab/template; mkdir -p "$T/vendor"; cp -r fixture/app/. "$T/"; \
    cp fixture/app/canary.js fixture/canary-dep/canary.js; \
    (cd fixture/canary-dep && npm pack --ignore-scripts --pack-destination "$T/vendor" >/dev/null); \
    rm fixture/canary-dep/canary.js; \
    cd "$T" && npm install --package-lock-only --ignore-scripts --no-audit --no-fund \
      && HOME=/tmp node /lab/tool/node_modules/pnpm/bin/pnpm.cjs install --lockfile-only --ignore-scripts \
         --store-dir=/tmp/pnpm-store \
      && rm -rf /tmp/pnpm-store /root/.npm
COPY run.mjs run.test.mjs ./
RUN chmod -R a+rX /lab
USER 65532:65532
ENV HOME=/tmp/home
CMD ["node", "run.mjs"]
