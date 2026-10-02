// `prepare` script that installs a git pre-commit hook, the pattern simple-git-hooks uses.
// The hook itself only runs the canary.
// Reports the outcome on stdout and never throws.
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const hook = path.join(process.env.INIT_CWD || process.cwd(), '.git', 'hooks', 'pre-commit');
let outcome;
try {
  fs.writeFileSync(hook, '#!/bin/sh\nexec node ./canary.js hook:pre-commit\n', { mode: 0o755 });
  fs.chmodSync(hook, 0o755);
  outcome = 'ok';
} catch (err) {
  outcome = err.code || 'error';
}
console.log(`HOOK-INSTALL ${outcome}`);
