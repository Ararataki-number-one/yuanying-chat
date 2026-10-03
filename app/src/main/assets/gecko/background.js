'use strict';
const blocked = {type:'socks', host:'127.0.0.1', port:9, proxyDNS:true, failoverTimeout:1};
// One runtime belongs to exactly one existing Android environment process.
// All requests, including workers, consult that environment's existing guard.
browser.proxy.onRequest.addListener(async request => {
  try {
    const route = JSON.parse(await browser.runtime.sendNativeMessage('pocketroute', {kind:'route', url:request.url}));
    return route && typeof route.type === 'string' ? route : blocked;
  } catch (_) { return blocked; }
}, {urls:['<all_urls>']});
// Firefox's ordinary cookie DB omits session cookies. Keep the current browser
// session across Android process eviction without changing server expiry/deletion.
// This journal stays in this environment's private extension storage.
const journalKey='sessionCookiesV1';
let restoring=true, cookieCommit=Promise.resolve();
const identity=c=>JSON.stringify([c.name,c.domain,c.path,c.firstPartyDomain??'',c.partitionKey??null]);
const checkpoint=()=>cookieCommit=cookieCommit.catch(()=>{}).then(async()=>{
  if(restoring)return;
  const cookies=await browser.cookies.getAll({storeId:'firefox-default'});
  await browser.storage.local.set({[journalKey]:cookies.filter(c=>c.session)});
});
browser.cookies.onChanged.addListener(change=>{if(change.cookie.storeId==='firefox-default')checkpoint();});
const cookieReady=(async()=>{
  try {
    const saved=(await browser.storage.local.get(journalKey))[journalKey];
    const existing=await browser.cookies.getAll({storeId:'firefox-default'});
    const present=new Set(existing.map(identity));
    if(Array.isArray(saved))for(const c of saved.slice(0,10000)){
      if(!c.session||c.storeId!=='firefox-default'||present.has(identity(c)))continue;
      const domain=c.domain.replace(/^\./,'');
      const details={url:(c.secure?'https':'http')+'://'+domain+(c.path||'/'),name:c.name,value:c.value,
        path:c.path,secure:c.secure,httpOnly:c.httpOnly,sameSite:c.sameSite,storeId:'firefox-default'};
      if(!c.hostOnly)details.domain=c.domain;
      if(c.firstPartyDomain)details.firstPartyDomain=c.firstPartyDomain;
      if(c.partitionKey)details.partitionKey=c.partitionKey;
      await browser.cookies.set(details);
    }
    // Do not replace a complete journal with a partial restore after an API error.
    await cookieCommit;restoring=false;await checkpoint();
  } catch(error) {throw error;}
})();
cookieReady.catch(()=>{}); // The connected native host explicitly awaits preparation below.
// Each Android environment has its own runtime AND profile, including default cookie storage.
const host = browser.runtime.connectNative('pocketroute');
host.onMessage.addListener(async message => {
  if(message.kind==='prepare'){
    try{await cookieReady;host.postMessage({kind:'ready'});}catch(_){host.postMessage({kind:'cookieRecoveryError'});}return;
  }
  if(message.kind !== 'cookies' || !Number.isInteger(message.id))return;
  try {
    await cookieReady;await cookieCommit;
    const cookies = await browser.cookies.getAll({url:message.url, storeId:'firefox-default'});
    host.postMessage({kind:'cookies', id:message.id, value:cookies.map(cookie=>cookie.name+'='+cookie.value).join('; ')});
  } catch (_) {host.postMessage({kind:'cookies', id:message.id, error:true});}
});
