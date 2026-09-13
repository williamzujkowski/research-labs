import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Y from 'yjs';
import { Trace, backward, sequential, disjoint, parseScore, contiguous, runAll, evidenceProblems } from './trace.mjs';

test('historical three-ID backward trace produces axb on every replica', () => {
  const trace = backward('historical');
  assert.deepEqual(trace.final.map(r => r.text), ['axb', 'axb', 'axb']);
  assert.equal(trace.measures.replica_equality, true);
  assert.equal(trace.measures.specified_run_contiguous, false);
  assert.deepEqual(trace.operations[1].dependencies, ['op1']);
  assert.deepEqual(trace.operations[2].dependencies, []);
});
test('receiver iteration order does not change this fixed trace', () => {
  assert.deepEqual(backward('reverse', undefined, false, [3, 2, 1]).final.map(r => r.text), ['axb', 'axb', 'axb']);
});
test('recorded raw updates replay to the same state in a fresh replica', () => {
  for (const trace of runAll()) {
    const doc = new Y.Doc();
    for (const op of trace.operations) Y.applyUpdateV2(doc, Buffer.from(op.update.base64, 'base64'));
    assert.deepEqual(doc.getArray().toArray(), trace.final[0].values);
    doc.destroy();
  }
});
test('invalid causal delivery fails before applying a dependent update', () => {
  const trace = new Trace('invalid');
  trace.insert(3, 0, 'b'); trace.deliver('op1', 1); trace.insert(1, 0, 'a');
  assert.throws(() => trace.deliver('op2', 2), /causal predecessor/);
  assert.deepEqual(trace.values(2), []);
  trace.synchronize(); trace.finish(['a', 'b']);
});
test('duplicate causal delivery is harmless in the tested schedule', () => {
  const trace = new Trace('duplicate');
  trace.insert(3, 0, 'b'); trace.deliver('op1', 1); trace.deliver('op1', 1);
  assert.deepEqual(trace.values(1), ['b']);
  trace.synchronize(); trace.finish(['b']);
});
test('sequential control preserves insertion run', () => {
  const trace = sequential();
  assert.deepEqual(trace.final.map(r => r.text), ['abx', 'abx', 'abx']);
  assert.equal(trace.measures.specified_run_contiguous, true);
});
test('concurrent disjoint control preserves both ends', () => {
  const trace = disjoint();
  assert.deepEqual(trace.final.map(r => r.text), ['a|x', 'a|x', 'a|x']);
  assert.equal(trace.measures.specified_run_contiguous, true);
});
test('score converges and remains valid while bd changes lane', () => {
  const trace = backward('score', ['drums:\n', 'bd\n', 'bass:\nc2\n'], true);
  assert.equal(trace.measures.replica_equality, true);
  assert.equal(trace.measures.specified_run_contiguous, false);
  assert.equal(trace.measures.syntax.valid, true);
  const before = parseScore(trace.local_before_merge[0].values.join(''));
  assert.deepEqual(before.assignments, [{lane: 'drums', event: 'bd'}]);
  assert.deepEqual(trace.measures.syntax.assignments, [{lane: 'bass', event: 'c2'}, {lane: 'bass', event: 'bd'}]);
});
test('score grammar rejects missing headers and executable-looking text', () => {
  for (const text of ['bd\n', 'drums:\nbd', 'drums:\nprocess.exit()\n', 'drums:\nunknown\n']) assert.equal(parseScore(text).valid, false);
});
test('contiguity check rejects separated or reversed unique runs', () => {
  assert.equal(contiguous(['a', 'x', 'b'], ['a', 'b']), false);
  assert.equal(contiguous(['b', 'a'], ['a', 'b']), false);
  assert.equal(contiguous(['x', 'a', 'b'], ['a', 'b']), true);
});
test('fixed corpus delivers all operations and stays far below ceiling', () => {
  for (const trace of runAll()) {
    assert.equal(trace.operations.length, 3);
    assert.equal(trace.measures.all_operations_delivered, true);
    for (const op of trace.operations) assert.ok(op.update.bytes < 1024);
  }
});

test('evidence gate rejects agreeing empty controls and omitted traces', () => {
  const traces = runAll();
  assert.deepEqual(evidenceProblems(traces), []);
  for (const replica of traces[1].final) replica.values = [];
  assert.ok(evidenceProblems(traces).some(problem => problem.includes('control output')));
  assert.ok(evidenceProblems(runAll().slice(1)).some(problem => problem.includes('missing')));
});
test('evidence gate preserves non-reproduction of historical interleaving', () => {
  const traces = runAll();
  for (const replica of traces[0].final) replica.values = ['a', 'b', 'x'];
  traces[0].measures.specified_run_contiguous = true;
  assert.deepEqual(evidenceProblems(traces), []);
});
