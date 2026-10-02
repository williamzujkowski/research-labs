// Canary lifecycle payload. It only writes a fixed marker string, once inside the
// project and once in a directory outside it, and reports each attempt on stdout.
// It never throws, so a denied write is recorded instead of failing the install.
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const label = process.argv[2] || 'unlabelled';
const project = process.env.INIT_CWD || process.cwd();
const targets = {
  inside: path.join(project, '.canary', label.replace(/[^a-z:-]/g, '_')),
  outside: path.join(process.env.CANARY_OUTSIDE_DIR || '/nonexistent', label.replace(/[^a-z:-]/g, '_')),
};
const result = {};
for (const [where, file] of Object.entries(targets)) {
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, `canary:${label}\n`);
    result[where] = 'ok';
  } catch (err) {
    result[where] = err.code || 'error';
  }
}
console.log(`CANARY ${label} inside=${result.inside} outside=${result.outside}`);
