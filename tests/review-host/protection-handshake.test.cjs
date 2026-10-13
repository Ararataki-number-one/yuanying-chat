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
  const sent = [], writes = [], pending = [];
  const control = {async set({value}) {
    writes.push(value);
    if (held) await new Promise(resolve => pending.push(resolve));
    state = value;
  }, async get() { return {value: mismatch ? !state : state}; }};
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
  return {sent, writes, pending, send: message => receive(message),
    initialized: () => vm.runInContext('cookieReady', context)};
}
async function flush() { for (let i = 0; i < 16; i++) await Promise.resolve(); }

test('A-B-A queued native settings retain request tokens and wait for readback', async () => {
  const bridge = harness({held: true});
  await bridge.initialized();
  const first = bridge.send({kind: 'prepare', level: 1, token: 101});
  await flush();
  const second = bridge.send({kind: 'protection', level: 2, token: 102});
  const third = bridge.send({kind: 'protection', level: 1, token: 103});
  await flush();
  assert.deepEqual(bridge.writes, [false]);
  assert.equal(bridge.sent.filter(message => message.kind === 'protectionReady').length, 0);
  for (let i = 0; i < 3; i++) {
    assert.equal(bridge.pending.length, 1);
    bridge.pending.shift()();
    await flush();
  }
  await Promise.all([first, second, third]);
  assert.deepEqual(bridge.writes, [false, true, false]);
  const acknowledgments = bridge.sent.filter(message => message.kind === 'protectionReady');
  assert.deepEqual(acknowledgments.map(message => message.token), [101, 102, 103]);
  assert.deepEqual(acknowledgments.map(message => message.level), [1, 2, 1]);
  assert.ok(acknowledgments.every(message => message.acknowledged));
  assert.equal(acknowledgments[2].fingerprinting, false);
});

test('missing native control never becomes an acknowledged setting', async () => {
  const bridge = harness({unavailable: true});
  await bridge.initialized();
  await bridge.send({kind: 'protection', level: 2, token: 201});
  const reply = bridge.sent.find(message => message.kind === 'protectionReady');
  assert.equal(reply.token, 201);
  assert.equal(reply.acknowledged, false);
  assert.equal(reply.fingerprinting, false);
});

test('a differing readback is reported without an acknowledgement', async () => {
  const bridge = harness({mismatch: true});
  await bridge.initialized();
  await bridge.send({kind: 'protection', level: 2, token: 301});
  const reply = bridge.sent.find(message => message.kind === 'protectionReady');
  assert.equal(reply.token, 301);
  assert.equal(reply.acknowledged, false);
});
