'use strict';
// An intentionally fixed, closed laboratory route. No user proxy configuration
// or login-page scripts. Failure has no DIRECT alternative.
browser.proxy.onRequest.addListener(details => {
  if (details.url.startsWith('http://127.0.0.1:8765/')) {
    browser.runtime.sendNativeMessage('probe', {
      kind: 'route', tabId: details.tabId, cookieStoreId: details.cookieStoreId,
      path: new URL(details.url).pathname
    }).catch(() => {});
  }
  return {type: 'socks', host: '127.0.0.1', port: 1080, proxyDNS: true, failoverTimeout: 1};
}, {urls: ['<all_urls>']});
browser.runtime.sendNativeMessage('probe', {kind: 'ready'}).catch(() => {});
