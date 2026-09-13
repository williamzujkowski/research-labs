// Original instrumentation of the authors' published schedule, not a CRDT implementation.
import * as Y from 'yjs';
import { createHash } from 'node:crypto';
export const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

export class Trace {
  constructor(name) {
    this.name = name;
    this.docs = new Map([1, 2, 3].map(id => {
      const doc = new Y.Doc();
      // Deliberate fixed fresh IDs reproduce the historical paper's ordering.
      doc.clientID = id;
      return [id, doc];
    }));
    this.seen = new Map([1, 2, 3].map(id => [id, new Set()]));
    this.operations = [];
    this.events = [];
  }
  values(id) { return this.docs.get(id).getArray().toArray(); }
  insert(id, index, value) {
    if (this.operations.length >= 10000) throw new Error('operation ceiling');
    if (!Number.isInteger(index) || index < 0 || index > this.values(id).length) throw new Error('invalid index');
    if (typeof value !== 'string' || value.length > 1000) throw new Error('invalid inert token');
    const doc = this.docs.get(id);
    const before = Y.encodeStateVector(doc);
    const op = {id: `op${this.operations.length + 1}`, replica: id, index, value,
      dependencies: [...this.seen.get(id)].sort()};
    doc.getArray().insert(index, [value]);
    const bytes = Y.encodeStateAsUpdateV2(doc, before);
    op.update = {base64: Buffer.from(bytes).toString('base64'), bytes: bytes.length, sha256: sha256(bytes)};
    this.operations.push(op);
    this.seen.get(id).add(op.id);
    this.events.push({type: 'insert', operation: op.id, replica: id, state: this.values(id)});
  }
  deliver(operationId, to) {
    const op = this.operations.find(candidate => candidate.id === operationId);
    if (!op || !this.docs.has(to)) throw new Error('unknown delivery');
    if (op.dependencies.some(id => !this.seen.get(to).has(id))) throw new Error('causal predecessor missing');
    Y.applyUpdateV2(this.docs.get(to), Buffer.from(op.update.base64, 'base64'));
    this.seen.get(to).add(op.id);
    this.events.push({type: 'deliver', operation: op.id, to, state: this.values(to)});
  }
  synchronize(order = [1, 2, 3]) {
    // Operations are generated in topological order. Deliver predecessors first,
    // even though Yjs itself can buffer updates received out of order.
    for (const to of order) for (const op of this.operations) {
      if (!this.seen.get(to).has(op.id)) this.deliver(op.id, to);
    }
  }
  finish(runValues, score = false) {
    const final = [...this.docs].map(([id, doc]) => ({replica: id, values: this.values(id),
      text: this.values(id).join(''), seen: [...this.seen.get(id)].sort(),
      encoded_state_bytes: Y.encodeStateAsUpdateV2(doc).length}));
    const converged = final.every(r => JSON.stringify(r.values) === JSON.stringify(final[0].values));
    const result = {name: this.name, operations: this.operations, events: this.events, final,
      measures: {replica_equality: converged, all_operations_delivered: final.every(r => r.seen.length === this.operations.length),
        specified_run_contiguous: contiguous(final[0].values, runValues),
        syntax: score ? parseScore(final[0].text) : {applicable: false, reason: 'letter/control trace, not a score'}}};
    for (const doc of this.docs.values()) doc.destroy();
    return result;
  }
}

export function contiguous(values, run) {
  // Fixtures use unique complete array elements; this is a local run check, not
  // the paper's formal maximal-non-interleaving definition.
  const start = values.indexOf(run[0]);
  return start >= 0 && run.every((value, index) => values[start + index] === value);
}

export function parseScore(text) {
  // Inert invented row grammar. No eval, real language parser or audio playback.
  // A header selects a lane until the next header; rows are bd, sd, c2 or d2.
  let lane = null;
  const assignments = [];
  const lines = text.endsWith('\n') ? text.slice(0, -1).split('\n') : [];
  if (!lines.length) return {applicable: true, valid: false, assignments, reason: 'missing newline or empty score'};
  for (const line of lines) {
    if (/^(drums|bass):$/.test(line)) lane = line.slice(0, -1);
    else if (/^(bd|sd|c2|d2)$/.test(line) && lane !== null) assignments.push({lane, event: line});
    else return {applicable: true, valid: false, assignments, reason: 'unknown row or event without lane'};
  }
  return {applicable: true, valid: true, assignments};
}

export function backward(name, tokens = ['a', 'b', 'x'], score = false, order = [1, 2, 3]) {
  const [prefix, body, concurrent] = tokens;
  const trace = new Trace(name);
  trace.insert(3, 0, body);
  trace.deliver('op1', 1);
  trace.insert(1, 0, prefix);
  trace.insert(2, 0, concurrent);
  const localBeforeMerge = [1, 2, 3].map(id => ({replica: id, values: trace.values(id)}));
  trace.synchronize(order);
  return {...trace.finish([prefix, body], score), local_before_merge: localBeforeMerge};
}

export function sequential() {
  const trace = new Trace('sequential-control');
  trace.insert(3, 0, 'b');
  trace.synchronize();
  trace.insert(1, 0, 'a');
  trace.synchronize();
  trace.insert(2, 2, 'x');
  trace.synchronize();
  return trace.finish(['a', 'b']);
}

export function disjoint() {
  const trace = new Trace('disjoint-control');
  trace.insert(3, 0, '|');
  trace.synchronize();
  trace.insert(1, 0, 'a');
  trace.insert(2, 1, 'x');
  trace.synchronize();
  return trace.finish(['a', '|', 'x']);
}

export function runAll() {
  return [backward('appendix-a-a9'), sequential(), disjoint(),
    backward('inert-score-lanes', ['drums:\n', 'bd\n', 'bass:\nc2\n'], true)];
}

export function evidenceProblems(traces) {
  const problems = [];
  const expectedNames = ['appendix-a-a9', 'sequential-control', 'disjoint-control', 'inert-score-lanes'];
  if (JSON.stringify(traces.map(trace => trace.name)) !== JSON.stringify(expectedNames)) problems.push('missing or reordered corpus');
  for (const trace of traces) {
    if (!trace.measures.replica_equality || !trace.measures.all_operations_delivered) problems.push(`${trace.name}: incomplete or divergent result`);
    const expected = {'sequential-control': ['a', 'b', 'x'], 'disjoint-control': ['a', '|', 'x']}[trace.name];
    if (expected && (trace.final.length !== 3 || trace.final.some(replica => JSON.stringify(replica.values) !== JSON.stringify(expected)))) {
      problems.push(`${trace.name}: control output differs from expected array`);
    }
  }
  return problems;
}
