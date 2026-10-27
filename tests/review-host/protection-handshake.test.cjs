'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Exercises the actual extension queue and token echo. Gecko and the Java
// receiver require Android coverage; a host API double cannot certify them.
const source = fs.readFileSync(path.join(__dirname, '../../app/src/main/assets/gecko/background.js'), 'utf8');
function harness({held = false, unavailable = false, mismatch = false} = {}) {
  let receive, state = false;
  const sent = [], writes = [], reads = [], pending = [];
  const control = {async set({value}) {
    writes.push(value);
    if (held) await new Promise(resolve => pending.push(resolve));
    state = value;
  }, async get() {
    const value = mismatch ? !state : state;
    reads.push(value);
    return {value};
  }};
  const browser = {
    proxy: {onRequest: {addListener() {}}},
    runtime: {sendNativeMessage: async () => '{"type":"direct"}',
      connectNative: () => ({postMessage: value => sent.push(value), onMessage: {addListener(handler) { receive = handler; }}})},
    storage: {local: {get: async () => ({}), set: async () => {}}},
    cookies: {onChanged: {addListener() {}}, getAll: async () => [], set: async () => {}},
    privacy: unavailable ? {} : {websites: {resistFingerprinting: control}},
  };
  const context = vm.createContext({browser});
  vm.runInContext(source, context, {filename: 'background.js'});
  return {sent, writes, reads, pending, send: message => receive(message),
    initialized: () => vm.runInContext('cookieReady', context)};
}
async function flush() { for (let i = 0; i < 16; i++) await Promise.resolve(); }

test('overlapping A-B-A settings discard the replaced pending write and confirm only the current request', async () => {
  const bridge = harness({held: true});
  await bridge.initialized();
  const first = bridge.send({kind: 'prepare', level: 1, token: 101, generation: 1});
  await flush();
  const second = bridge.send({kind: 'protection', level: 2, token: 102, generation: 2});
  const third = bridge.send({kind: 'protection', level: 1, token: 103, generation: 3});
  await flush();
  assert.deepEqual(bridge.writes, [false]);
  assert.deepEqual(bridge.reads, []);
  const superseded = bridge.sent.filter(message => message.kind === 'protectionReady');
  assert.equal(superseded.length, 1);
  assert.equal(superseded[0].token, 102);
  assert.equal(superseded[0].generation, 2);
  assert.equal(superseded[0].level, 2);
  assert.equal(superseded[0].acknowledged, false);
  assert.equal(superseded[0].reason, 'superseded');
  for (let i = 0; i < 2; i++) {
    assert.equal(bridge.pending.length, 1);
    bridge.pending.shift()();
    await flush();
  }
  await Promise.all([first, second, third]);
  assert.deepEqual(bridge.writes, [false, false]);
  assert.deepEqual(bridge.reads, [false, false]);
  assert.equal(bridge.pending.length, 0);
  const acknowledgments = bridge.sent.filter(message => message.kind === 'protectionReady')
    .sort((a, b) => a.token - b.token);
  assert.deepEqual(acknowledgments.map(message => message.token), [101, 102, 103]);
  assert.deepEqual(acknowledgments.map(message => message.generation), [1, 2, 3]);
  assert.deepEqual(acknowledgments.map(message => message.level), [1, 2, 1]);
  assert.deepEqual(acknowledgments.map(message => message.acknowledged), [false, false, true]);
  // The already-running old operation retains the serial lock until its real
  // set/get settles, but its stale readback cannot confirm the newer request.
  assert.equal(acknowledgments[0].reason, 'setting-timeout');
  assert.equal(acknowledgments[1].reason, 'superseded');
  assert.equal(acknowledgments[2].reason, '');
  assert.equal(acknowledgments[2].fingerprinting, false);
});

test('serial current A-B-A settings retain all tokens and receive matching readbacks', async () => {
  const bridge = harness();
  await bridge.initialized();
  await bridge.send({kind: 'prepare', level: 1, token: 401, generation: 1});
  await bridge.send({kind: 'protection', level: 2, token: 402, generation: 2});
  await bridge.send({kind: 'protection', level: 1, token: 403, generation: 3});
  assert.deepEqual(bridge.writes, [false, true, false]);
  assert.deepEqual(bridge.reads, [false, true, false]);
  const acknowledgments = bridge.sent.filter(message => message.kind === 'protectionReady');
  assert.deepEqual(acknowledgments.map(message => message.token), [401, 402, 403]);
  assert.deepEqual(acknowledgments.map(message => message.generation), [1, 2, 3]);
  assert.deepEqual(acknowledgments.map(message => message.level), [1, 2, 1]);
  assert.deepEqual(acknowledgments.map(message => message.fingerprinting), [false, true, false]);
  assert.ok(acknowledgments.every(message => message.acknowledged));
  assert.ok(acknowledgments.every(message => message.reason === ''));
});

test('missing native control never becomes an acknowledged setting', async () => {
  const bridge = harness({unavailable: true});
  await bridge.initialized();
  await bridge.send({kind: 'protection', level: 2, token: 201, generation: 1});
  const replies = bridge.sent.filter(message => message.kind === 'protectionReady');
  assert.equal(replies.length, 1);
  const reply = replies[0];
  assert.equal(reply.token, 201);
  assert.equal(reply.generation, 1);
  assert.equal(reply.level, 2);
  assert.equal(reply.acknowledged, false);
  assert.equal(reply.fingerprinting, false);
  assert.equal(reply.reason, 'setting-unavailable');
  assert.deepEqual(bridge.writes, []);
  assert.deepEqual(bridge.reads, []);
});

test('a differing readback is reported without an acknowledgement', async () => {
  const bridge = harness({mismatch: true});
  await bridge.initialized();
  await bridge.send({kind: 'protection', level: 2, token: 301, generation: 1});
  const replies = bridge.sent.filter(message => message.kind === 'protectionReady');
  assert.equal(replies.length, 1);
  const reply = replies[0];
  assert.equal(reply.token, 301);
  assert.equal(reply.generation, 1);
  assert.equal(reply.level, 2);
  assert.equal(reply.acknowledged, false);
  assert.equal(reply.fingerprinting, false);
  assert.equal(reply.reason, 'setting-mismatch');
  assert.deepEqual(bridge.writes, [true]);
  assert.deepEqual(bridge.reads, [false]);
});

test('a missing generation is rejected before any native setting operation', async () => {
  const bridge = harness();
  await bridge.initialized();
  await bridge.send({kind: 'protection', level: 2, token: 501});
  const replies = bridge.sent.filter(message => message.kind === 'protectionReady');
  assert.equal(replies.length, 1);
  const reply = replies[0];
  assert.equal(reply.token, 501);
  assert.equal(reply.generation, 0);
  assert.equal(reply.level, 2);
  assert.equal(reply.acknowledged, false);
  assert.equal(reply.fingerprinting, false);
  assert.equal(reply.reason, 'invalid-setting-request');
  assert.deepEqual(bridge.writes, []);
  assert.deepEqual(bridge.reads, []);
});
