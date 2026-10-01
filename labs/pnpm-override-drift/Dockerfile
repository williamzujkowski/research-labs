# Reference platform linux/amd64. Build fetches integrity-locked packages; runtime is offline.
FROM node:22-bookworm-slim@sha256:4d676821dff059fd00d277ee4261ef34ea712317fed0737c03941481b5760c96
WORKDIR /lab
COPY tool/package.json tool/package-lock.json ./tool/
RUN cd tool && npm ci --ignore-scripts --no-audit --no-fund && npm cache clean --force
COPY fixtures ./fixtures
# Populate a content-addressed store from the two lockfiles that between them name every
# package version used (fflate 0.7.3 and 0.7.5). `pnpm fetch` checks lockfile integrity hashes.
# Re-resolution and dedupe also need registry metadata. That is captured here, at build
# time, into /opt/pnpm-cache; run.mjs records each cached document's `modified` field.
RUN P="node /lab/tool/node_modules/pnpm/bin/pnpm.cjs" && O="--ignore-scripts --store-dir=/opt/pnpm-store --cache-dir=/opt/pnpm-cache" && \
    for f in faithful no-header header-only; do \
      d=$(mktemp -d) && cp fixtures/package.json "$d/" && cp "fixtures/$f.pnpm-lock.yaml" "$d/pnpm-lock.yaml" && \
      (cd "$d" && $P fetch $O && $P install --lockfile-only $O && cp "/lab/fixtures/$f.pnpm-lock.yaml" pnpm-lock.yaml && ($P dedupe --check $O || true)) && rm -rf "$d"; \
    done && chmod -R a+rX /opt/pnpm-store /opt/pnpm-cache
COPY run.mjs run.test.mjs ./
RUN chmod -R a+rX /lab
USER 65532:65532
ENV HOME=/tmp
CMD ["node", "run.mjs"]
