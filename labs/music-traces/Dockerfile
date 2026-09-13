FROM node:22-bookworm-slim@sha256:4d676821dff059fd00d277ee4261ef34ea712317fed0737c03941481b5760c96
WORKDIR /lab
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && npm cache clean --force
COPY *.mjs UPSTREAM-LICENSE.txt ./
RUN chmod -R a+rX /lab
USER 65532:65532
CMD ["timeout", "--signal=KILL", "900", "node", "--max-old-space-size=384", "run.mjs"]
