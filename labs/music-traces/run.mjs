import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runAll, sha256 } from './trace.mjs';
const require = createRequire(import.meta.url);
const start = performance.now();
const traces = runAll();
const result = {
  schema: 'music-traces-v1',
  environment: {node: process.version, yjs: require('yjs/package.json').version,
    platform: process.platform, architecture: process.arch,
    image_id: process.env.LAB_IMAGE_ID ?? null,
    revision: process.env.LAB_REVISION ?? null, dirty: process.env.LAB_DIRTY ?? null,
    package_lock_sha256: sha256(readFileSync(new URL('./package-lock.json', import.meta.url))),
    source_sha256: sha256(readFileSync(new URL('./trace.mjs', import.meta.url)))},
  bounds: {fixed_traces: 4, random_seeds: 0, max_operations_per_trace: 10000,
    container_memory_bytes: 536870912, container_timeout_seconds: 900},
  elapsed_ms: performance.now() - start,
  operation_count: traces.reduce((count, trace) => count + trace.operations.length, 0),
  traces,
};
console.log(JSON.stringify(result, null, 2));
if (traces.some(trace => !trace.measures.replica_equality || !trace.measures.all_operations_delivered)) process.exitCode = 1;
