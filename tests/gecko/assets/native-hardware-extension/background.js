'use strict';
let host = null, serial = Promise.resolve(), attempts = 0;
const known = new Set(['probe-native-hardware-api-only', 'invalid-hardware-request-token',
  'native-hardware-pref-unavailable', 'native-hardware-readback-unavailable', 'invalid-hardware-cap',
  'native-hardware-setting-failed', 'native-rfp-policy-changed', 'native-hardware-readback-mismatch',
  'native-hardware-api-unavailable']);
const post = (port, packet) => { if (port === host) try { port.postMessage(packet); } catch (_) {} };
async function execute(port, value) {
  if (port !== host || !value || typeof value !== 'object' ||
      !['hardwareProbeRead', 'hardwareProbeSet', 'hardwareProbeReset'].includes(value.kind)) return;
  try {
    if (typeof value.requestToken !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(value.requestToken)) {
      throw new Error('invalid-hardware-request-token');
    }
    if (!browser.pocketNativeHardware) throw new Error('native-hardware-api-unavailable');
    const api = browser.pocketNativeHardware;
    const result = value.kind === 'hardwareProbeRead' ? await api.read(value.requestToken) :
      value.kind === 'hardwareProbeSet' ? await api.setCap(value.cap, value.requestToken) :
      await api.reset(value.requestToken);
    post(port, {kind: 'hardwareProbeResult', ...result});
  } catch (error) {
    post(port, {kind: 'hardwareProbeResult', schema: 1, status: 'failed',
      requestToken: typeof value.requestToken === 'string' ? value.requestToken : '',
      nativePreferenceReadback: false, scope: 'runtime-native-pref', workerCoverageVerified: false,
      fingerprintProtectionVerified: false, reason: known.has(error?.message) ? error.message : 'native-hardware-call-failed'});
  }
}
function connect() {
  if (host || ++attempts > 8) return;
  try {
    const port = browser.runtime.connectNative('pockethardwareprobe'); host = port;
    port.onMessage.addListener(value => { serial = serial.then(() => execute(port, value), () => execute(port, value)); });
    port.onDisconnect.addListener(() => { if (host === port) { host = null; setTimeout(connect, 200); } });
    post(port, {kind: 'hardwareProbeReady', apiAvailable: !!browser.pocketNativeHardware});
  } catch (_) { host = null; setTimeout(connect, 200); }
}
connect();
browser.runtime.onMessage.addListener((value, sender) => {
  if (value?.kind !== 'hardwareProbeDocumentReady' || sender.id !== browser.runtime.id || !sender.tab) return undefined;
  post(host, {kind: 'hardwareProbeDocumentReady', tabId: sender.tab.id,
    url: typeof sender.url === 'string' ? sender.url : ''});
  return undefined;
});
