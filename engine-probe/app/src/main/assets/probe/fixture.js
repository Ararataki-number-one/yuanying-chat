'use strict';
// Only our exact loopback fixture receives this script. Google / ChatGPT pages
// never receive it. The fixture contains synthetic tokens, never real accounts.
window.addEventListener('message', event => {
  if (event.source !== window || event.origin !== 'http://127.0.0.1:8765') return;
  if (event.data?.channel !== 'pocketchat-engine-fixture') return;
  browser.runtime.sendNativeMessage('probe', {kind: 'fixture', result: event.data.result}).catch(() => {});
});
