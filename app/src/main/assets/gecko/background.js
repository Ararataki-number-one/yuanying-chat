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
// Each Android environment has its own runtime AND profile, including default cookie storage.
const host = browser.runtime.connectNative('pocketroute');
host.onMessage.addListener(async message => {
  if(message.kind !== 'cookies' || !Number.isInteger(message.id))return;
  try {
    const cookies = await browser.cookies.getAll({url:message.url, storeId:'firefox-default'});
    host.postMessage({kind:'cookies', id:message.id, value:cookies.map(cookie=>cookie.name+'='+cookie.value).join('; ')});
  } catch (_) {host.postMessage({kind:'cookies', id:message.id, error:true});}
});
