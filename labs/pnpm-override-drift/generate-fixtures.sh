#!/bin/sh
# How the three committed lockfile fixtures were produced (2026-10-01, pnpm 10.33.0,
# Node 22.22.3, public npm registry). Needs network; NOT run by the lab or CI.
# Output differs if registry metadata changes; the committed fixtures are the record.
set -eu
P="npx -y pnpm@10.33.0"
work=$(mktemp -d)
cp "$(dirname "$0")/fixtures/package.json" "$work/package.json"
cd "$work"
# 1. Faithful: pnpm resolves with the override applied.
$P install --lockfile-only --ignore-scripts
cp pnpm-lock.yaml faithful.pnpm-lock.yaml
# 2. No-header: starting from the faithful lockfile, resolve once with the override
#    removed from the manifest, then restore the manifest. This SIMULATES the shape of
#    the Dependabot lockfiles in williamzujkowski.github.io PRs #564 (bot commit d0160c5),
#    #635, #638 and #662; it does not run or reproduce Dependabot's updater.
cp package.json package.keep
node -e 'const f=require("fs");const p=JSON.parse(f.readFileSync("package.json"));delete p.pnpm;f.writeFileSync("package.json",JSON.stringify(p,null,2)+"\n")'
$P install --lockfile-only --ignore-scripts
cp pnpm-lock.yaml no-header.pnpm-lock.yaml
mv package.keep package.json
# 3. Header-only: a hand repair that restores the overrides block and nothing else.
awk '{print} /^  excludeLinksFromLockfile:/{print "";print "overrides:";print "  satori>fflate: 0.7.5"}' \
  no-header.pnpm-lock.yaml > header-only.pnpm-lock.yaml
echo "fixtures written to $work"
