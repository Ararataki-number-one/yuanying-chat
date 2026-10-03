'use strict';
const blocked = {type:'socks', host:'127.0.0.1', port:9, proxyDNS:true, failoverTimeout:1};
// One runtime belongs to exactly one existing Android environment process.
// All requests, including workers, consult that environment's existing guard.
browser.proxy.onRequest.addListener(async request => {
  try {
    const route = await browser.runtime.sendNativeMessage('pocketroute', {kind:'route', url:request.url});
    return route && typeof route.type === 'string' ? route : blocked;
  } catch (_) { return blocked; }
}, {urls:['<all_urls>']});
browser.runtime.sendNativeMessage('pocketroute', {kind:'ready'}).catch(() => {});
