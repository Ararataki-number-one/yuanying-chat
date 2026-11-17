'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const scripts = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const expected = Buffer.from(scripts.bytes, 'base64');
let checks = 0;
const check = (message, value) => { assert(value, message); checks++; };
function page() {
  const state = {document: {}, location: {href: scripts.source}, Uint8Array,
    btoa: value => Buffer.from(value, 'binary').toString('base64'), calls: []};
  state.window = state;
  state.fetch = async url => {
    state.calls.push(url);
    return {ok: true, blob: async () => new Blob([expected], {type: 'application/pdf'})};
  };
  return vm.createContext(state);
}
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  const state = page();
  check('prepare retains exact source document', vm.runInContext(scripts.prepare, state).started === true);
  await settle();
  const info = vm.runInContext(scripts.metadata, state);
  check('actual Blob metadata', info.ready && info.size === expected.length && info.mime === 'application/pdf');
  check('only the exact Blob URL is fetched', state.calls.length === 1 && state.calls[0] === scripts.target);
  const parts = [];
  for (const script of scripts.chunks) {
    check('each actual chunk starts', vm.runInContext(script, state).started === true);
    await settle();
    const block = vm.runInContext(scripts.chunkRead, state);
    check('actual arrayBuffer/base64 chunk available', block.ready && typeof block.chunk === 'string');
    parts.push(Buffer.from(block.chunk, 'base64'));
    check('consumed chunk cannot be read twice', vm.runInContext(scripts.chunkRead, state).ready === false);
  }
  check('whole binary document is unchanged', Buffer.concat(parts).equals(expected));
  state.document = {};
  check('same-URL replacement document rejected', vm.runInContext(scripts.metadata, state).error === true);
  check('same-URL replacement cannot start another chunk', vm.runInContext(scripts.chunks[0], state).error === true);
  const moved = page(); moved.location.href = 'https://example.com/other';
  check('changed URL rejected before fetch', vm.runInContext(scripts.prepare, moved).error === true && moved.calls.length === 0);
  const absent = page();
  check('missing job cannot become valid', vm.runInContext(scripts.metadata, absent).error === true);
  console.log(JSON.stringify({status: 'passed', checks, actualBrowserExecution: false,
    scope: 'Actual production-generated JavaScript in Node VM with standard Blob/ArrayBuffer and controlled fetch/document/location boundaries.'}));
})().catch(error => { console.error(error); process.exitCode = 1; });
