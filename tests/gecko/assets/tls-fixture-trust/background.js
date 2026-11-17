'use strict';

// The only caller is the integration Activity's private native-messaging port.
// There are no content scripts, host permissions, HTTP requests or TLS retries.
const port = browser.runtime.connectNative('pockettlsfixturetrust');
let closed = false, serial = Promise.resolve();
const post = value => { if (!closed) port.postMessage(value); };
const failure = (request, error) => post({kind: 'failed', binding: request?.binding || null,
  reason: typeof error?.message === 'string' && /^fixture-trust-[a-z-]+$/.test(error.message)
    ? error.message : 'fixture-trust-native-api'});
port.onMessage.addListener(request => {
  serial = serial.then(async () => {
    if (closed) return;
    try {
      if (!request || Object.keys(request).sort().join() !== 'binding,kind' ||
          !['arm', 'read'].includes(request.kind) || !browser.pocketFixtureTrust) throw new Error('fixture-trust-request');
      if (request.kind === 'arm') {
        post({kind: 'armed', value: await browser.pocketFixtureTrust.arm(request.binding)});
        post({kind: 'ready', value: await browser.pocketFixtureTrust.waitImported(request.binding)});
      } else post({kind: 'ready', value: await browser.pocketFixtureTrust.read(request.binding)});
    } catch (error) { failure(request, error); }
  }, error => failure(request, error));
});
port.onDisconnect.addListener(() => { closed = true; browser.pocketFixtureTrust?.close().catch(() => {}); });
post({kind: 'connected', apiAvailable: !!browser.pocketFixtureTrust});
