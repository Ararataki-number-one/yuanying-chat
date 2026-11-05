#!/usr/bin/env python3
"""Session selection and authority boundaries; not native Android execution proof."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'app/src/main/assets/gecko'


class NativeTimezoneSessionApiContract(unittest.TestCase):
    def test_schema_requires_native_session_binding(self):
        schema = json.loads((ASSETS / 'native-timezone-schema.json').read_text())[0]
        self.assertEqual(schema['namespace'], 'pocketNativeTimezone')
        self.assertEqual([row['name'] for row in schema['functions']],
                         ['applySession', 'readSession'])
        for row in schema['functions']:
            self.assertEqual(row['parameters'][0]['name'], 'sessionId')
        receipt = schema['types'][0]['properties']
        for key in ('sessionId', 'contextId', 'requestToken', 'nativeSettingReadback'):
            self.assertIn(key, receipt)

    def test_unique_native_window_and_lifetime_boundaries(self):
        script = r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const state = {windows: [], writes: 0, lookups: 0, lookupFailure: '', afterSet: null};
const serviceType = Symbol('native-window-mediator');
const components = {interfaces: {nsIWindowMediator: serviceType}, classes: {
  '@mozilla.org/appshell/window-mediator;1': {getService(type) {
    assert.equal(type, serviceType);
    if (state.lookupFailure === 'service') throw new Error('service unavailable');
    return {getEnumerator(value) {
      assert.equal(value, null); state.lookups++;
      if (state.lookupFailure === 'enumerate') throw new Error('enumeration unavailable');
      let index = 0;
      return {hasMoreElements() {return index < state.windows.length;},
        getNext() {return state.windows[index++];}};
    }};
  }}
}};
const sandbox = vm.createContext({Cc: components.classes, Ci: components.interfaces, Intl,
  ChromeUtils: {importESModule: () => ({ExtensionCommon: {ExtensionAPI: class {}}, ExtensionUtils: {ExtensionError: Error}})}});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox);
function api(extension = {}, envType = 'addon_parent') {
  return new sandbox.pocketNativeTimezone().getAPI({envType, extension: {
    id: 'browser@pocketchat.local', isPrivileged: true, ...extension}}).pocketNativeTimezone;
}
function nativeWindow(name, id) {
  let selected = '';
  const top = {id};
  Object.defineProperty(top, 'timezoneOverride', {
    enumerable: true, get() {return selected;}, set(value) {
      selected = value; state.writes++; if (state.afterSet) state.afterSet();
    }});
  return {name, closed: false, browser: {browsingContext: {top}},
    document: {documentElement: {getAttribute: key => key === 'windowtype' ? 'navigator:geckoview' : ''}}};
}
const sid = '0123456789abcdef0123456789abcdef';
const other = 'abcdef0123456789abcdef0123456789';
let target = nativeWindow(sid, 1024), unrelated = nativeWindow(other, 2048);
state.windows = [unrelated, target];
const control = api();
const applied = await control.applySession(sid, 'Asia/Shanghai', 'apply.1');
assert.equal(applied.status, 'applied');
assert.equal(applied.sessionId, sid);
assert.equal(applied.contextId, '1024');
assert.equal(applied.requestToken, 'apply.1');
assert.equal(applied.requestedZoneId, 'Asia/Shanghai');
assert.equal(applied.nativeZoneId, 'Asia/Shanghai');
assert.equal(applied.nativeSettingReadback, true);
assert.equal(applied.workerCoverageVerified, false);
assert.equal(applied.serviceWorkerCoverageVerified, false);
assert.equal(unrelated.browser.browsingContext.top.timezoneOverride, '');
assert.equal(state.writes, 1);
const read = await control.readSession(sid, 'read.1');
assert.equal(read.status, 'read');
assert.equal(read.sessionId, sid);
assert.equal(read.nativeZoneId, 'Asia/Shanghai');
assert.equal(state.writes, 1);
let cases = 2;
async function noMutation(action, pattern) {
  const writes = state.writes;
  await assert.rejects(action, pattern);
  assert.equal(state.writes, writes, 'rejected request must not mutate any native context'); cases++;
}
await noMutation(control.applySession(other + 'missing', 'Asia/Shanghai', 'missing.1'), /session-unavailable/);
await noMutation(control.applySession(sid, 'Mars/Olympus', 'invalid.1'), /invalid-timezone-id/);
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'bad token'), /invalid-timezone-request-token/);
await noMutation(control.applySession('bad session', 'Asia/Shanghai', 'invalid.2'), /invalid-timezone-session/);
state.windows = [target, nativeWindow(sid, 4096)];
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'duplicate.1'), /session-ambiguous/);
state.windows = [target]; target.closed = true;
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'closed.1'), /session-unavailable/);
target.closed = false;
const savedDocument = target.document;
target.document = {documentElement: {getAttribute: () => 'navigator:browser'}};
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'type.1'), /session-unavailable/);
target.document = savedDocument;
state.lookupFailure = 'service';
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'service.1'), /enumeration-unavailable/);
state.lookupFailure = 'enumerate';
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'enumerate.1'), /enumeration-unavailable/);
state.lookupFailure = '';
state.windows = [target, ...Array.from({length: 128}, (_, i) => nativeWindow('other' + i, i + 10000))];
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'bound.1'), /enumeration-bound/);
state.windows = [target];
const savedBrowser = target.browser;
target.browser = {browsingContext: {top: {id: 1024}}};
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'property.1'), /property-unavailable/);
target.browser = {browsingContext: {top: {id: 0, timezoneOverride: ''}}};
await noMutation(control.applySession(sid, 'Asia/Shanghai', 'id.1'), /property-unavailable/);
target.browser = savedBrowser;
assert.throws(() => api({id: 'external@example.com'}), /app-bundled/); cases++;
assert.throws(() => api({isPrivileged: false}), /app-bundled/); cases++;
assert.throws(() => api({}, 'content_parent'), /app-bundled/); cases++;
const lookupsBeforeInvalidZone = state.lookups;
await noMutation(control.applySession(sid, 'Not A Zone', 'invalid.3'), /invalid-timezone-id/);
assert.equal(state.lookups, lookupsBeforeInvalidZone);
state.afterSet = () => {target.closed = true;};
await assert.rejects(control.applySession(sid, 'Asia/Tokyo', 'race.1'), /session-replaced/); cases++;
state.afterSet = null; target.closed = false;
state.afterSet = () => {target.browser = {browsingContext: {top: {id: 8192, timezoneOverride: ''}}};};
await assert.rejects(control.applySession(sid, 'Asia/Tokyo', 'race.2'), /session-replaced/); cases++;
state.afterSet = null; target.browser = savedBrowser;
const reset = await control.applySession(sid, '', 'reset.1');
assert.equal(reset.requestedZoneId, ''); assert.equal(reset.nativeZoneId, ''); cases++;
console.log(JSON.stringify({checks: cases, actualAndroidExecution: false,
  workerCoverageVerified: false, scope: 'application-native-bridge authority and session selection model'}));
'''
        run = subprocess.run(['node', '--input-type=module', '-', str(ASSETS / 'native-timezone-api.js')],
                             input=script, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertGreaterEqual(result['checks'], 20)
        self.assertIs(result['actualAndroidExecution'], False)
        self.assertIs(result['workerCoverageVerified'], False)


if __name__ == '__main__':
    unittest.main()
