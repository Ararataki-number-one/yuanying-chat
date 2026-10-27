'use strict';
const blocked = {type:'socks', host:'127.0.0.1', port:9, proxyDNS:true, failoverTimeout:1};
// One runtime belongs to exactly one existing Android environment process.
// All requests, including workers, consult that environment's existing guard.
browser.proxy.onRequest.addListener(async request => {
  try {
    const route = JSON.parse(await browser.runtime.sendNativeMessage('pocketroute', {kind:'route', url:request.url}));
    // Gecko's explicit null removes the closed default proxy for this request.
    // A "direct" ProxyInfo instead inherits that default when it is present.
    if (route && route.type === 'direct') return null;
    return route && typeof route.type === 'string' ? route : blocked;
  } catch (_) { return blocked; }
}, {urls:['<all_urls>']});
// Firefox's ordinary cookie DB omits session cookies. Keep the current browser
// session across Android process eviction without changing server expiry/deletion.
// This journal stays in this environment's private extension storage.
const journalKey='sessionCookiesV1';
let restoring=true, cookieCommit=Promise.resolve(), cookieRunning=false, cookiePending=false;
const identity=c=>JSON.stringify([c.name,c.domain,c.path,c.firstPartyDomain??'',c.partitionKey??null]);
const checkpoint=()=>{
  if(restoring)return cookieCommit;
  // Even a native read joining an active checkpoint needs a subsequent getAll:
  // its bulk clear may not have emitted any cookie change events.
  cookiePending=true;
  if(!cookieRunning){
    cookieRunning=true;
    cookieCommit=Promise.resolve().then(async()=>{
      try {
        do {
          cookiePending=false;
          try {
            const cookies=await browser.cookies.getAll({storeId:'firefox-default'});
            if(cookiePending)continue; // Replace an obsolete read with the latest request.
            await browser.storage.local.set({[journalKey]:cookies.filter(c=>c.session)});
          } catch(error) {
            if(!cookiePending)throw error; // A newer request may still obtain a fresh, complete snapshot.
          }
        } while(cookiePending);
      } finally {
        // Clear inside this worker, before its promise settles. A request in a
        // later microtask must start a worker rather than join a completed one.
        cookieRunning=false;
      }
    });
  }
  return cookieCommit;
};
browser.cookies.onChanged.addListener(change=>{
  if(change.cookie.storeId==='firefox-default')checkpoint().catch(()=>{
    // The event API cannot await this failure. Keep the original rejected
    // cookieCommit for barriers; a later checkpoint starts a fresh attempt.
    console.warn('Session cookie checkpoint failed; a fresh checkpoint is required.');
  });
});
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
// A timed-out API operation keeps the serial lock until the actual operation
// settles. Releasing it with Promise.race would let a late old set overwrite a
// newer confirmed setting. Only one replaceable pending request is retained.
let protectionRunning=false,protectionPending=null,latestProtection=null,currentProtectionRequest=null,confirmedProtection=null,watchingProtection=false;
let host=null,reconnectAttempts=0,reconnectTask=null;
const postHost=(port,message)=>{if(port!==host)return false;try{port.postMessage(message);return true;}catch(_){return false;}};
const finishProtection=(job,acknowledged,fingerprinting,reason)=>{
  if(job.finished)return;
  job.finished=true;
  if(job===latestProtection&&job.reference===currentProtectionRequest)confirmedProtection=acknowledged?job:null;
  postHost(job.port,{kind:'protectionReady',level:job.level,token:job.token,generation:job.generation,fingerprinting,acknowledged,reason});
  job.resolve({acknowledged,fingerprinting});
};
const watchProtection=control=>{
  if(watchingProtection||!control.onChange?.addListener)return;
  watchingProtection=true;
  control.onChange.addListener(observed=>{
    const job=confirmedProtection;
    if(!job||job!==latestProtection||job.reference!==currentProtectionRequest||job.port!==host||typeof observed?.value!=='boolean'||observed.value===(job.level>=2))return;
    confirmedProtection=null;
    postHost(job.port,{kind:'protectionChanged',level:job.level,token:job.token,generation:job.generation,reason:'setting-changed'});
  });
};
const drainProtection=async()=>{
  if(protectionRunning)return;
  protectionRunning=true;
  try{
    while(protectionPending){
      const job=protectionPending;protectionPending=null;
      if(job.port!==host||job!==latestProtection||job.reference!==currentProtectionRequest||Date.now()>job.deadline){finishProtection(job,false,false,'setting-timeout');continue;}
      let fingerprinting=false,acknowledged=false,reason='setting-unavailable';
      try{
        const control=browser.privacy?.websites?.resistFingerprinting;
        if(control){
          watchProtection(control);
          await control.set({value:job.level>=2});
          const observed=await control.get({});
          fingerprinting=observed.value===true;acknowledged=observed.value===(job.level>=2);
          reason=acknowledged?'':'setting-mismatch';
        }
      }catch(_){reason='setting-error';}
      const fresh=job.port===host&&job===latestProtection&&job.reference===currentProtectionRequest&&Date.now()<=job.deadline;
      finishProtection(job,acknowledged&&fresh,fingerprinting,fresh?reason:'setting-timeout');
    }
  }finally{protectionRunning=false;}
};
// Claim the desired generation before any await, including Cookie recovery.
// An older prepare continuation must never enqueue a stale set after a newer
// user-selected mode has already received a successful readback.
const claimProtection=(message,port)=>{
  const level=message.level,token=message.token,generation=message.generation;
  if(!Number.isInteger(level)||level<0||level>2||!Number.isSafeInteger(token)||token<1||!Number.isSafeInteger(generation)||generation<1)return {reason:'invalid-setting-request'};
  const old=currentProtectionRequest;
  if(old?.port===port&&(generation<old.generation||token<=old.token))return {reason:'superseded'};
  const wait=Number.isFinite(message.timeoutMs)?Math.max(1000,Math.min(10000,message.timeoutMs)):8000;
  const reference=Object.freeze({level,token,generation,port,deadline:Date.now()+wait});
  currentProtectionRequest=reference;confirmedProtection=null;return {reference};
};
const rejectProtection=(message,port,reason)=>postHost(port,{kind:'protectionReady',level:message.level??1,token:message.token,generation:message.generation??0,fingerprinting:false,acknowledged:false,reason});
const protect=reference=>{
  if(reference!==currentProtectionRequest||reference.port!==host)return Promise.resolve({acknowledged:false,fingerprinting:false});
  return new Promise(resolve=>{
    const job={...reference,reference,resolve,finished:false};
    latestProtection=job;confirmedProtection=null;
    if(protectionPending)finishProtection(protectionPending,false,false,'superseded');
    protectionPending=job;drainProtection();
  });
};
const handleHostMessage=async(message,port)=>{
  if(port!==host||!message||typeof message!=='object')return;
  if(message.kind==='prepare'){
    const claim=claimProtection(message,port);
    try{
      await cookieReady;
      // Cookie restoration and native RFP are independent barriers. Native
      // opens a session only after both; a hung setting cannot hide cookie-ready.
      if(!postHost(port,{kind:'cookiePrepared'}))return;
      const result=claim.reference?await protect(claim.reference):{acknowledged:false};
      if(!claim.reference)rejectProtection(message,port,claim.reason);
      postHost(port,{kind:'ready'});
      if(port===host&&result.acknowledged)reconnectAttempts=0;
    }catch(_){postHost(port,{kind:'cookieRecoveryError'});}return;
  }
  if(message.kind==='protection'){
    const claim=claimProtection(message,port);
    if(!claim.reference){rejectProtection(message,port,claim.reason);return;}
    const result=await protect(claim.reference);
    if(port===host&&result.acknowledged)reconnectAttempts=0;
    return;
  }
  if(message.kind==='requestIdentityScope'&&Number.isInteger(message.id)){
    let result;
    try{result=await globalThis.PocketRequestIdentityBackground?.handle(message.configuration)??{ok:false,error:'scope-helper-unavailable'};}
    catch(_){result={ok:false,error:'scope-registration-failed'};}
    postHost(port,{kind:'requestIdentityScopeResult',id:message.id,result:JSON.stringify(result)});return;
  }
  if(message.kind !== 'cookies' || !Number.isInteger(message.id))return;
  try {
    // Native bulk clear does not emit cookies.onChanged for every deletion.
    // Refresh from the real cookie store before reporting a completed read,
    // so its deleted session cookies cannot return from the older journal.
    await cookieReady;await checkpoint();
    const cookies = await browser.cookies.getAll({url:message.url, storeId:'firefox-default'});
    postHost(port,{kind:'cookies', id:message.id, value:cookies.map(cookie=>cookie.name+'='+cookie.value).join('; ')});
  } catch (_) {postHost(port,{kind:'cookies', id:message.id, error:true});}
};
const reconnectHost=()=>{
  if(reconnectTask!==null||reconnectAttempts>=3)return;
  const delay=500*(2**reconnectAttempts++);
  reconnectTask=setTimeout(()=>{reconnectTask=null;connectHost();},delay);
};
const connectHost=()=>{
  let port;
  try{port=browser.runtime.connectNative('pocketroute');}catch(_){reconnectHost();return;}
  host=port;
  port.onMessage.addListener(message=>handleHostMessage(message,port));
  port.onDisconnect?.addListener(()=>{
    if(port!==host)return;
    host=null;latestProtection=currentProtectionRequest=confirmedProtection=null;
    try{globalThis.PocketRequestIdentityBackground?.clear();}catch(_){}
    if(protectionPending?.port===port){finishProtection(protectionPending,false,false,'bridge-disconnected');protectionPending=null;}
    reconnectHost();
  });
};
connectHost();
