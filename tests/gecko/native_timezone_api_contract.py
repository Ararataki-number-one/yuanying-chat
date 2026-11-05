#!/usr/bin/env python3
"""Privileged timezone bridge boundary checks; never Android coverage evidence."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'tests/gecko/assets/native-timezone-extension'


class NativeTimezoneApiContract(unittest.TestCase):
    def test_manifest_is_app_bundled_and_does_not_enable_debugging(self):
        manifest = json.loads((ASSETS / 'manifest.json').read_text())
        self.assertEqual(manifest['browser_specific_settings']['gecko']['id'],
                         'timezone-probe@pocketchat.local')
        parent = manifest['experiment_apis']['pocketNativeTimezone']['parent']
        self.assertEqual(parent['scopes'], ['addon_parent'])
        self.assertEqual(parent['paths'], [['pocketNativeTimezone']])
        self.assertEqual(parent['script'], 'parent.js')
        self.assertNotIn('debugger', manifest['permissions'])
        self.assertNotIn('web_accessible_resources', manifest)

    def test_native_setting_boundaries(self):
        script = r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const sandbox = vm.createContext({
  ChromeUtils: {importESModule: () => ({ExtensionCommon: {ExtensionAPI: class {}}, ExtensionUtils: {ExtensionError: Error}})},
  Intl
});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox);
let selected = '', writes = 0;
const top = {id: 73};
Object.defineProperty(top, 'timezoneOverride', {
  get() { return selected; }, set(value) { writes++; selected = value; }, enumerable: true
});
const tab = {nativeTab: {}, browser: {browsingContext: {top}}};
function api(overrides = {}) {
  const extension = {id: 'timezone-probe@pocketchat.local', isPrivileged: true,
    tabManager: {get: value => value === 4 ? tab : null, canAccessTab: () => true}, ...overrides};
  return new sandbox.pocketNativeTimezone().getAPI({extension}).pocketNativeTimezone;
}
const control = api();
const applied = await control.apply(4, 'Asia/Shanghai', 'request-1');
assert.equal(applied.status, 'applied');
assert.equal(applied.requestedZoneId, 'Asia/Shanghai');
assert.equal(applied.nativeZoneId, 'Asia/Shanghai');
assert.equal(applied.contextId, '73');
assert.equal(applied.nativeSettingReadback, true);
assert.equal(applied.workerCoverageVerified, false);
assert.equal(applied.serviceWorkerCoverageVerified, false);
assert.equal(applied.scope, 'top-browsing-context');
assert.equal(writes, 1);
const read = await control.read(4, 'request-2');
assert.equal(read.status, 'read');
assert.equal(read.requestToken, 'request-2');
assert.equal(read.nativeZoneId, selected);
assert.equal(writes, 1);
await assert.rejects(control.apply(4, 'Mars/Olympus', 'request-3'));
assert.equal(writes, 1, 'invalid IANA zone must not mutate native state');
await assert.rejects(control.apply(4, 'Asia/Shanghai', 'bad token'));
assert.equal(writes, 1, 'invalid token must not mutate native state');
await assert.rejects(control.apply(99, 'Asia/Shanghai', 'request-4'));
assert.equal(writes, 1, 'missing tab must not mutate another native context');
await assert.rejects(api({tabManager: {get: () => tab, canAccessTab: () => false}})
  .apply(4, 'Asia/Shanghai', 'request-5'));
assert.equal(writes, 1, 'inaccessible tab must not mutate native context');
assert.throws(() => api({id: 'external-extension@example.com'}));
assert.throws(() => api({isPrivileged: false}));
const missing = api({tabManager: {get: () => ({nativeTab: {}, browser: {browsingContext: {top: {id: 74}}}}), canAccessTab: () => true}});
await assert.rejects(missing.apply(4, 'Asia/Shanghai', 'request-6'));
const reset = await control.apply(4, '', 'request-7');
assert.equal(reset.requestedZoneId, '');
assert.equal(reset.nativeZoneId, '');
assert.equal(writes, 2);
console.log(JSON.stringify({checks: 10, actualAndroidExecution: false,
  workerCoverageVerified: false, scope: 'privileged bridge boundary model only'}));
'''
        run = subprocess.run(['node', '--input-type=module', '-', str(ASSETS / 'parent.js')],
                             input=script, text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result['checks'], 10)
        self.assertIs(result['actualAndroidExecution'], False)
        self.assertIs(result['workerCoverageVerified'], False)


if __name__ == '__main__':
    unittest.main()
