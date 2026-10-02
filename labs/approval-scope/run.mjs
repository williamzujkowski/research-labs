// What does one approved install command run? Each arm copies the fixture into a fresh git
// workspace, runs one install command under `strace -f`, then runs `git commit` (a second,
// separately approvable command) the same way. Records the processes started, the file
// mutations attempted and their results, and the marker files the canaries left.
// Offline. Writes one JSON evidence record to stdout.
//
//   node run.mjs            plain arms (no sandbox)
//   node run.mjs sandbox    the same installs wrapped in sandbox-runtime (srt)
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

const HERE = new URL('.', import.meta.url).pathname;
const TEMPLATE = process.env.LAB_TEMPLATE ?? join(HERE, 'template');
const PNPM = join(HERE, 'tool/node_modules/pnpm/bin/pnpm.cjs');
const SRT = join(HERE, 'tool/node_modules/@anthropic-ai/sandbox-runtime/dist/cli.js');
const WORK = process.env.LAB_WORK ?? '/work';
const GIT_ID = ['-c', 'user.email=lab@example.invalid', '-c', 'user.name=lab'];

// Commands as an agent would submit them. Offline flags keep the run hermetic; they are
// not part of what a permission rule such as `Bash(npm install *)` would need to match.
const NPM_FLAGS = ['--offline', '--no-audit', '--no-fund'];
const PNPM_FLAGS = ['--offline', '--store-dir=/tmp/pnpm-store'];
export const ARMS = {
  'npm-install-ignore-scripts': { tool: 'npm', args: ['install', '--ignore-scripts'], control: true },
  'npm-ci-ignore-scripts': { tool: 'npm', args: ['ci', '--ignore-scripts'], control: true },
  'pnpm-install-ignore-scripts': { tool: 'pnpm', args: ['install', '--frozen-lockfile', '--ignore-scripts'], control: true },
  'npm-install': { tool: 'npm', args: ['install'] },
  'npm-ci': { tool: 'npm', args: ['ci'] },
  'npm-install-foreground-scripts': { tool: 'npm', args: ['install', '--foreground-scripts'] },
  'pnpm-install': { tool: 'pnpm', args: ['install', '--frozen-lockfile'] },
  'pnpm-install-dep-allowed': { tool: 'pnpm', args: ['install', '--frozen-lockfile'], allowDepBuild: true },
};
export const SANDBOX_ARMS = ['npm-install-ignore-scripts', 'npm-install', 'pnpm-install'];

const TRACED = 'execve,open,openat,creat,mkdir,mkdirat,rename,renameat,renameat2,unlink,unlinkat,chmod,fchmodat,symlink,symlinkat,link,linkat';
const QUOTED = /"((?:[^"\\]|\\.)*)"/g;
const unq = (s) => s.replace(/\\(.)/g, (_, c) => ({ n: '\n', t: '\t', '"': '"', '\\': '\\' })[c] ?? c);

// Parse `strace -f -o FILE` output into process starts and attempted file mutations.
// Lines split by `<unfinished ...>` are rejoined with their `<... resumed>` halves first.
export function parseTrace(text) {
  const pending = new Map();
  const lines = [];
  for (const raw of text.split('\n')) {
    const m = raw.match(/^(\d+)\s+(.*)$/);
    if (!m) continue;
    const [, pid, body] = m;
    if (body.endsWith('<unfinished ...>')) { pending.set(pid, body.replace(/\s*<unfinished \.\.\.>$/, '')); continue; }
    const resumed = body.match(/^<\.\.\. \w+ resumed>(.*)$/);
    if (resumed) { lines.push({ pid, body: (pending.get(pid) ?? '') + resumed[1] }); pending.delete(pid); continue; }
    lines.push({ pid, body });
  }
  const execs = [];
  const mutations = [];
  for (const { pid, body } of lines) {
    const call = body.match(/^(\w+)\((.*)\)\s+=\s+(-?\d+|\?)(?:\s+(\w+))?/);
    if (!call) continue;
    const [, name, args, ret, errno] = call;
    const ok = ret !== '-1';
    const strings = [...args.matchAll(QUOTED)].map((q) => unq(q[1]));
    if (name === 'execve') {
      if (!ok) continue;
      const argv = (args.match(/\[(.*?)\](?:,\s*0x|,\s*\[|$)/)?.[1] ?? '');
      execs.push({ pid: Number(pid), argv: [...argv.matchAll(QUOTED)].map((q) => unq(q[1])) });
      continue;
    }
    if (name === 'open' || name === 'openat' || name === 'creat') {
      if (name !== 'creat' && !/O_WRONLY|O_RDWR|O_CREAT/.test(args)) continue;
    }
    if (name === 'mkdir' || name === 'mkdirat') { if (errno === 'EEXIST') continue; }
    const paths = name.startsWith('rename') || name.startsWith('link') || name.startsWith('symlink')
      ? strings.slice(-1) : strings.slice(0, 1);
    for (const path of paths) mutations.push({ pid: Number(pid), call: name, path, ok, errno: ok ? null : errno ?? null });
  }
  return { execs, mutations };
}

// Where a mutated path sits relative to the workspace. Relative paths are kept separate:
// the tracer does not resolve them, so they are never silently counted as "inside".
export function classify(path, app, outside) {
  if (!path.startsWith('/')) return 'relative-path';
  const r = relative(app, path);
  if (path.startsWith(outside + '/') || path === outside) return 'outside-workspace-marker-dir';
  if (r.startsWith('..')) return 'elsewhere';
  if (r === '.git/hooks' || r.startsWith('.git/hooks/')) return 'workspace-.git/hooks';
  if (r === '.git' || r.startsWith('.git/')) return 'workspace-.git-other';
  if (r === 'node_modules' || r.startsWith('node_modules/')) return 'workspace-node_modules';
  if (r === '.canary' || r.startsWith('.canary/')) return 'workspace-.canary';
  return 'workspace-other';
}

// A lifecycle script is what a package manager hands to `sh -c`.
export const scriptCommands = (execs) => execs
  .filter((e) => /(^|\/)sh$/.test(e.argv[0] ?? '') && e.argv[1] === '-c').map((e) => e.argv[2]);

function run(cmd, args, opts) {
  const r = spawnSync(cmd, args, { encoding: 'utf8', timeout: 120_000, ...opts });
  return { exit: r.status, signal: r.signal, out: `${r.stdout ?? ''}${r.stderr ?? ''}` };
}

function summarize(traceText, app, outside) {
  const { execs, mutations } = parseTrace(traceText);
  const byClass = {};
  for (const m of mutations) {
    const k = classify(m.path, app, outside);
    byClass[k] ??= { ok: 0, denied: {} };
    if (m.ok) byClass[k].ok += 1; else byClass[k].denied[m.errno] = (byClass[k].denied[m.errno] ?? 0) + 1;
  }
  const notable = mutations.filter((m) => ['workspace-.git/hooks', 'workspace-.canary', 'outside-workspace-marker-dir']
    .includes(classify(m.path, app, outside)))
    .map((m) => ({ call: m.call, path: m.path.replace(app, '<workspace>').replace(outside, '<outside>'), ok: m.ok, errno: m.errno }));
  return {
    processesStarted: execs.length,
    programs: [...new Set(execs.map((e) => e.argv[0]))].sort(),
    lifecycleScripts: scriptCommands(execs),
    mutationsByLocation: byClass,
    notableMutations: notable,
  };
}

const listDir = (d) => (existsSync(d) ? readdirSync(d).sort() : []);

export function observe(name, { sandbox = false } = {}) {
  const arm = ARMS[name];
  const base = mkdtempSync(join(WORK, `${name}-`));
  const app = join(base, 'app');
  const outside = join(base, 'outside');
  const tmp = mkdtempSync(join('/tmp', `${name}-`));
  mkdirSync(outside);
  cpSync(TEMPLATE, app, { recursive: true });
  if (arm.allowDepBuild) writeFileSync(join(app, 'pnpm-workspace.yaml'), 'onlyBuiltDependencies:\n  - canary-dep\n');
  const env = { ...process.env, CANARY_OUTSIDE_DIR: outside, npm_config_cache: join(tmp, 'npm-cache'),
    npm_config_update_notifier: 'false', CI: 'true', HOME: join(tmp, 'home') };
  mkdirSync(env.HOME);
  run('git', ['init', '-q'], { cwd: app, env });
  run('git', [...GIT_ID, 'add', '-A'], { cwd: app, env });
  run('git', [...GIT_ID, 'commit', '-qm', 'fixture'], { cwd: app, env });

  const tool = arm.tool === 'npm' ? ['npm', ...arm.args, ...NPM_FLAGS] : [process.execPath, PNPM, ...arm.args, ...PNPM_FLAGS];
  const trace = join(tmp, 'install.trace');
  let cmd = 'strace';
  let args = ['-f', '-qq', '-s', '4096', '-e', `trace=${TRACED}`, '-e', 'signal=none', '-o', trace, ...tool];
  if (sandbox) {
    // Documented Claude Code defaults: write to the working directory and a temp directory;
    // no allowed network domains. enableWeakerNestedSandbox is srt's documented mode for
    // running inside Docker; it binds the host /proc instead of mounting a fresh one.
    const settings = join(tmp, 'srt.json');
    writeFileSync(settings, JSON.stringify({
      network: { allowedDomains: [], deniedDomains: [] },
      filesystem: { denyRead: [], allowWrite: [app, '/tmp'], denyWrite: [] },
      enableWeakerNestedSandbox: true,
    }));
    args = ['--settings', settings, '--', cmd, ...args];
    cmd = process.execPath;
    args = [SRT, ...args];
  }
  const install = run(cmd, args, { cwd: app, env });
  const installTrace = existsSync(trace) ? readFileSync(trace, 'utf8') : '';
  const afterInstall = {
    exit: install.exit,
    signal: install.signal,
    traceCaptured: installTrace.length > 0,
    ...summarize(installTrace, app, outside),
    output: {
      // Which of the scripts that actually ran does the command's own output name?
      scriptsShown: scriptCommands(parseTrace(installTrace).execs).filter((s) => install.out.includes(s)),
      pnpmIgnoredBuildsWarning: /Ignored build scripts/.test(install.out),
      tail: install.out.slice(-1500),
    },
    markersInside: listDir(join(app, '.canary')),
    markersOutside: listDir(outside),
    preCommitHookPresent: existsSync(join(app, '.git/hooks/pre-commit')),
  };

  // Second command: `git commit`, unsandboxed in every arm, as a separately approved step.
  const ctrace = join(tmp, 'commit.trace');
  const commit = run('strace', ['-f', '-qq', '-s', '4096', '-e', `trace=${TRACED}`, '-e', 'signal=none', '-o', ctrace,
    'git', ...GIT_ID, 'commit', '-q', '--allow-empty', '-m', 'probe'], { cwd: app, env });
  const commitTrace = existsSync(ctrace) ? readFileSync(ctrace, 'utf8') : '';
  const commitSummary = summarize(commitTrace, app, outside);
  const afterCommit = {
    exit: commit.exit,
    hookRan: commitSummary.programs.some((p) => p.endsWith('/pre-commit')),
    canaryExecs: parseTrace(commitTrace).execs.filter((e) => e.argv.includes('./canary.js')).length,
    markersInside: listDir(join(app, '.canary')),
    markersOutside: listDir(outside),
  };
  rmSync(base, { recursive: true, force: true });
  rmSync(tmp, { recursive: true, force: true });
  return { arm: name, sandbox, control: Boolean(arm.control), command: tool.slice(arm.tool === 'pnpm' ? 1 : 0).join(' ').replace(PNPM, 'pnpm'), install: afterInstall, commit: afterCommit };
}

// Look before approving: install with scripts off, then ask npm which packages in the
// resulting tree declare install-time scripts. Nothing in the tree runs.
export function inventory() {
  const base = mkdtempSync(join(WORK, 'inventory-'));
  const app = join(base, 'app');
  const tmp = mkdtempSync(join('/tmp', 'inventory-'));
  cpSync(TEMPLATE, app, { recursive: true });
  const env = { ...process.env, npm_config_cache: join(tmp, 'npm-cache'), npm_config_update_notifier: 'false', HOME: tmp };
  const install = run('npm', ['ci', '--ignore-scripts', ...NPM_FLAGS], { cwd: app, env });
  const q = run('npm', ['query', ':attr(scripts, [preinstall]), :attr(scripts, [install]), :attr(scripts, [postinstall]), :attr(scripts, [prepublish]), :attr(scripts, [preprepare]), :attr(scripts, [prepare]), :attr(scripts, [postprepare])'], { cwd: app, env });
  let found = null;
  try { found = JSON.parse(q.out).map((p) => ({ name: p.name, location: p.location, scripts: p.scripts })); } catch { /* exit recorded */ }
  const markers = listDir(join(app, '.canary'));
  rmSync(base, { recursive: true, force: true });
  rmSync(tmp, { recursive: true, force: true });
  return { installExit: install.exit, queryExit: q.exit, packagesWithInstallScripts: found, markersAfterInventory: markers };
}

const version = (cmd, args) => run(cmd, args, {}).out.trim().split('\n')[0];

export function environment() {
  return {
    node: process.version,
    npm: version('npm', ['--version']),
    pnpm: version(process.execPath, [PNPM, '--version']),
    git: version('git', ['--version']),
    strace: version('strace', ['-V']),
    bubblewrap: version('bwrap', ['--version']),
    sandboxRuntime: JSON.parse(readFileSync(join(HERE, 'tool/node_modules/@anthropic-ai/sandbox-runtime/package.json'), 'utf8')).version,
    image: process.env.LAB_IMAGE_ID ?? null,
    revision: process.env.LAB_REVISION ?? null,
    dirty: process.env.LAB_DIRTY ?? null,
  };
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const sandbox = process.argv[2] === 'sandbox';
  const names = sandbox ? SANDBOX_ARMS : Object.keys(ARMS);
  // Controls first: if a control shows any lifecycle script, stop before the matrix.
  const ordered = [...names.filter((n) => ARMS[n].control), ...names.filter((n) => !ARMS[n].control)];
  const observations = [];
  for (const n of ordered) {
    const o = observe(n, { sandbox });
    observations.push(o);
    // A control only counts if the install succeeded and was traced; one that ran nothing
    // at all would pass every "nothing ran" check vacuously.
    if (o.control && (o.install.exit !== 0 || !o.install.traceCaptured || o.install.processesStarted === 0
      || o.install.lifecycleScripts.length || o.install.markersInside.length || o.install.markersOutside.length)) {
      process.stdout.write(JSON.stringify({ error: 'control failed', observation: o }, null, 2) + '\n');
      process.exit(3);
    }
  }
  // In plain mode the container refuses user namespaces, so this records what sandbox-runtime
  // itself does when it cannot build its sandbox.
  const extra = sandbox ? {} : { sandboxUnavailable: observe('npm-install', { sandbox: true }), inventory: inventory() };
  const record = { lab: 'approval-scope', mode: sandbox ? 'sandbox' : 'plain', environment: environment(),
    observations, ...extra };
  process.stdout.write(JSON.stringify(record, null, 2) + '\n');
}
