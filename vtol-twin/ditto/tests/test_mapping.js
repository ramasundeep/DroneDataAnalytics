// Unit tests for ditto/mapping/telemetry-incoming.js, run with: node ditto/tests/test_mapping.js
// Stubs the `Ditto` global that Ditto's Rhino engine provides, then evaluates the mapper as-is.
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'mapping', 'telemetry-incoming.js'), 'utf8');
const ctx = {
  Ditto: {
    buildDittoProtocolMsg: (ns, name, group, channel, criterion, action, p, headers, value) => ({
      topic: `${ns}/${name}/${group}/${channel}/${criterion}/${action}`, path: p, headers, value,
    }),
    arrayBufferToString: (buf) => Buffer.from(buf).toString('utf8'),
  },
};
vm.createContext(ctx);
vm.runInContext(src, ctx, { filename: 'telemetry-incoming.js' });
// results are re-serialised so objects created inside the VM context compare cleanly
const norm = (m) => (m === null ? null : JSON.parse(JSON.stringify(m)));
const map = (topic, payload, extra) =>
  norm(ctx.mapToDittoProtocolMsg(Object.assign({ 'mqtt.topic': topic }, extra || {}),
    typeof payload === 'string' ? payload : JSON.stringify(payload), null, 'application/json'));

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('  ok  ' + name); }

test('single-feature topic maps to a merge on /features/<feature>', () => {
  const m = map('vtol/VTOL-1/telemetry/engine', { ts: '2026-09-05T10:00:00Z', rpm: 5420, egtC: 612.4 });
  assert.strictEqual(m.topic, 'vtol.fleet/VTOL-1/things/twin/commands/merge');
  assert.strictEqual(m.path, '/features');
  assert.strictEqual(m.headers['content-type'], 'application/merge-patch+json');
  assert.strictEqual(m.headers['response-required'], false);
  assert.deepStrictEqual(m.value, { engine: { properties: { ts: '2026-09-05T10:00:00Z', rpm: 5420, egtC: 612.4 } } });
});

test('multi-feature topic fans out objects and stamps top-level ts into each feature', () => {
  const m = map('vtol/VTOL-1/telemetry', { ts: 'T1', power: { busVoltageV: 27.9 }, vibration: { rmsX: 0.4 }, note: 'ignored scalar' });
  assert.deepStrictEqual(Object.keys(m.value).sort(), ['power', 'vibration']);
  assert.strictEqual(m.value.power.properties.ts, 'T1');
  assert.strictEqual(m.value.vibration.properties.rmsX, 0.4);
});

test('a feature-level ts wins over the top-level ts', () => {
  const m = map('vtol/VTOL-1/telemetry', { ts: 'T1', power: { ts: 'T2', busVoltageV: 27.9 } });
  assert.strictEqual(m.value.power.properties.ts, 'T2');
});

test('thing name comes from the topic, not the payload', () => {
  const m = map('vtol/VTOL-2/telemetry/engine', { tail: 'VTOL-1', rpm: 1 });
  assert.strictEqual(m.topic.split('/')[1], 'VTOL-2');
  assert.strictEqual(m.value.engine.properties.tail, undefined);
});

test('falls back to payload.tail when the topic header is missing', () => {
  const m = norm(ctx.mapToDittoProtocolMsg({}, JSON.stringify({ tail: 'VTOL-1', feature: 'engine', rpm: 9 }), null, 'application/json'));
  assert.strictEqual(m.topic.split('/')[1], 'VTOL-1');
  assert.strictEqual(m.value.engine.properties.rpm, 9);
});

test('byte payloads are decoded when no text payload is given', () => {
  const bytes = Buffer.from(JSON.stringify({ rpm: 7 }));
  const m = norm(ctx.mapToDittoProtocolMsg({ 'mqtt.topic': 'vtol/VTOL-1/telemetry/engine' }, null, bytes, 'application/octet-stream'));
  assert.strictEqual(m.value.engine.properties.rpm, 7);
});

test('correlation-id is propagated when present', () => {
  const m = map('vtol/VTOL-1/telemetry/engine', { rpm: 1 }, { 'correlation-id': 'abc' });
  assert.strictEqual(m.headers['correlation-id'], 'abc');
});

test('drops: bad JSON, non-object, foreign topic, too-deep topic, multi-feature without objects', () => {
  assert.strictEqual(map('vtol/VTOL-1/telemetry/engine', '{not json'), null);
  assert.strictEqual(map('vtol/VTOL-1/telemetry/engine', '[1,2]'), null);
  assert.strictEqual(map('other/VTOL-1/telemetry/engine', { rpm: 1 }), null);
  assert.strictEqual(map('vtol/VTOL-1/telemetry/engine/rpm', { rpm: 1 }), null);
  assert.strictEqual(map('vtol/VTOL-1/telemetry', { ts: 'T1', rpm: 1 }), null);
  assert.strictEqual(map('vtol/VTOL-1/events', { rpm: 1 }), null);
});

test('mapper source is ES5-compatible for Rhino (no let/const/arrow/template literals)', () => {
  const stripped = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  assert.ok(!/\b(let|const)\s/.test(stripped), 'uses let/const');
  assert.ok(!/=>/.test(stripped), 'uses arrow functions');
  assert.ok(!/`/.test(stripped), 'uses template literals');
});

console.log(`${passed} mapper tests passed`);
