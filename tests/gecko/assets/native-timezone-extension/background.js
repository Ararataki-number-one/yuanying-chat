'use strict';

let nativeHost = null;
let serial = Promise.resolve();
const post = (port, value) => {
  if (port !== nativeHost) return;
  try { port.postMessage(value); } catch (_) {}
};
const failure = (port, value, reason) => post(port, {
  kind: 'timezoneProbeResult', schema: 1, status: 'failed',
  requestToken: typeof value.requestToken === 'string' ? value.requestToken : '',
  requestedZoneId: typeof value.zoneId === 'string' ? value.zoneId : '',
  nativeSettingReadback: false, scope: 'top-browsing-context',
  workerCoverageVerified: false, serviceWorkerCoverageVerified: false, reason
});
async function execute(port, value) {
  if (port !== nativeHost || !value || typeof value !== 'object') return;
  if (!['timezoneProbeApply', 'timezoneProbeRead'].includes(value.kind)) return;
  if (typeof value.requestToken !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(value.requestToken)) {
    failure(port, value, 'invalid-timezone-request-token'); return;
  }
  try {
    const tabs = await browser.tabs.query({});
    if (port !== nativeHost) return;
    if (tabs.length !== 1) throw new Error('probe-requires-one-tab');
    if (!browser.pocketNativeTimezone) throw new Error('native-timezone-api-unavailable');
    const result = value.kind === 'timezoneProbeApply'
      ? await browser.pocketNativeTimezone.apply(tabs[0].id, value.zoneId, value.requestToken)
      : await browser.pocketNativeTimezone.read(tabs[0].id, value.requestToken);
    post(port, {kind: 'timezoneProbeResult', ...result});
  } catch (error) {
    const known = new Set(['probe-requires-one-tab', 'native-timezone-api-unavailable',
      'app-bundled-timezone-api-only', 'invalid-timezone-request-token', 'invalid-timezone-tab',
      'timezone-tab-unavailable', 'native-timezone-property-unavailable', 'invalid-timezone-id',
      'native-timezone-readback-unavailable']);
    failure(port, value, known.has(error?.message) ? error.message : 'native-timezone-call-failed');
  }
}
try {
  const port = browser.runtime.connectNative('pockettimezoneprobe');
  nativeHost = port;
  port.onMessage.addListener(value => {
    serial = serial.then(() => execute(port, value), () => execute(port, value));
  });
  port.onDisconnect.addListener(() => { if (nativeHost === port) nativeHost = null; });
  post(port, {kind: 'timezoneProbeReady', apiAvailable: !!browser.pocketNativeTimezone});
} catch (_) {}
browser.runtime.onMessage.addListener((value, sender) => {
  if (value?.kind !== 'timezoneProbeDocumentReady' || sender.id !== browser.runtime.id || !sender.tab) return undefined;
  post(nativeHost, {kind: 'timezoneProbeDocumentReady', tabId: sender.tab.id,
    url: typeof sender.url === 'string' ? sender.url : ''});
  return undefined;
});
