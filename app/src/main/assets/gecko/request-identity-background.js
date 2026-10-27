/* Only the explicitly registered diagnostic URLs receive this temporary policy. */
(() => {
  'use strict';
  const protocolPath='/pocketchat-identity/v1/';
  const active=new Map(), knownBases=new Set();
  const paths=new Set(['document','worker.js','observe','result']);
  const sensitive=new Set(['cookie','authorization','proxy-authorization','referer','origin']);
  const installed=new Map();
  function endpoint(value) {
    try {
      const url=new URL(value);
      if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!==protocolPath)return null;
      return url.origin+protocolPath;
    } catch {return null;}
  }
  function classify(details) {
    let url;try{url=new URL(details.url);}catch{return null;}
    const base=url.origin+protocolPath;
    if(!url.pathname.startsWith(protocolPath)||!paths.has(url.pathname.slice(protocolPath.length)))return null;
    if(!knownBases.has(base))return installed.has('https://'+url.hostname+protocolPath+'*')?{valid:false}:null;
    const nonce=url.searchParams.get('nonce');
    const registered=active.get(nonce);
    const valid=registered&&registered.base===base&&registered.until>Date.now()
      &&url.searchParams.getAll('nonce').length===1
      &&Array.from(url.searchParams.keys()).every(key=>key==='nonce'||key==='source')
      &&(!url.searchParams.has('source')||url.pathname===protocolPath+'observe'&&url.searchParams.getAll('source').length===1&&url.searchParams.get('source')==='worker')
      &&details.method==='GET'&&!url.hash&&!url.username&&!url.password
      &&(url.pathname===protocolPath+'observe'?url.searchParams.get('source')==='worker':!url.searchParams.has('source'));
    // Known diagnostic bases remain closed after cancellation/expiry. An old
    // document must never regain credentialed access when its scope is gone.
    return {valid:!!valid};
  }
  const beforeRequest=details=>{const match=classify(details);return match&&!match.valid?{cancel:true}:{};};
  const beforeHeaders=details=>{
    const match=classify(details);if(!match)return {};
    if(!match.valid)return {cancel:true};
    return {requestHeaders:(details.requestHeaders||[]).filter(header=>!sensitive.has(String(header.name).toLowerCase()))};
  };
  const received=details=>{
    const match=classify(details);if(!match)return {};
    if(!match.valid||details.statusCode>=300&&details.statusCode<400)return {cancel:true};
    return {};
  };
  function install(base) {
    const pattern='https://'+new URL(base).hostname+protocolPath+'*';
    if(installed.has(pattern))return true;
    const hooks=[
      [browser.webRequest?.onBeforeRequest,details=>beforeRequest(details),['blocking']],
      [browser.webRequest?.onBeforeSendHeaders,details=>beforeHeaders(details),['blocking','requestHeaders']],
      [browser.webRequest?.onHeadersReceived,details=>received(details),['blocking','responseHeaders']]
    ];
    const added=[];
    try {
      for(const [event,listener,options] of hooks){
        if(!event||typeof event.addListener!=='function'||typeof event.removeListener!=='function')throw Error('filter-api-unavailable');
        event.addListener(listener,{urls:[pattern]},options);added.push([event,listener]);
      }
      installed.set(pattern,hooks);return true;
    } catch (_) {
      for(const [event,listener] of hooks)try{event?.removeListener(listener);}catch(_){}
      return false;
    }
  }
  async function evidence(nonce,base) {
    const registration=active.get(nonce);
    if(!registration||registration.base!==base||registration.until<=Date.now())return {ok:false,nonce,error:'diagnostic-scope-expired'};
    if(registration.inFlight)return {ok:false,nonce,error:'evidence-already-in-flight'};
    const controller=new AbortController();registration.controller=controller;registration.inFlight=true;
    const timer=setTimeout(()=>controller.abort(),Math.min(3000,registration.until-Date.now()));
    try {
      const response=await fetch(base+'result?nonce='+nonce,{credentials:'omit',referrerPolicy:'no-referrer',redirect:'error',cache:'no-store',signal:controller.signal});
      if(![200,202,403,409].includes(response.status))throw Error('detector-response-status');
      const reader=response.body?.getReader();if(!reader)throw Error('bounded-stream-unavailable');
      const chunks=[];let size=0;
      try {
        for(;;){const item=await reader.read();if(item.done)break;if(!item.value||!Number.isFinite(item.value.byteLength)||size+item.value.byteLength>32000){await reader.cancel();throw Error('detector-response-too-large');}size+=item.value.byteLength;chunks.push(item.value);}
      } finally {try{reader.releaseLock();}catch(_){}}
      if(controller.signal.aborted||active.get(nonce)!==registration||registration.until<=Date.now())throw Error('diagnostic-scope-cancelled');
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
      const server=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
      return {ok:true,nonce,source:'extension-background-control',httpStatus:response.status,server};
    } catch (error) {const known=new Set(['detector-response-status','bounded-stream-unavailable','detector-response-too-large','diagnostic-scope-cancelled']);return {ok:false,nonce,error:controller.signal.aborted?'evidence-cancelled':known.has(error?.message)?error.message:'independent-server-records-unavailable'};}
    finally {clearTimeout(timer);if(registration.controller===controller){registration.controller=null;registration.inFlight=false;}}
  }
  globalThis.PocketRequestIdentityBackground=Object.freeze({
    handle(configuration) {
      const nonce=configuration?.nonce;
      if(typeof nonce!=='string'||!/^[0-9a-f]{32}$/.test(nonce))return {ok:false,error:'invalid-nonce'};
      if(configuration.action==='cancel'){active.get(nonce)?.controller?.abort();active.delete(nonce);return {ok:true,nonce};}
      const base=endpoint(configuration.endpoint);
      if(!base)return {ok:false,nonce,error:'invalid-endpoint'};
      if(configuration.action==='evidence')return evidence(nonce,base);
      if(configuration.action!=='register')return {ok:false,nonce,error:'invalid-action'};
      if(active.has(nonce)&&active.get(nonce).base!==base)return {ok:false,nonce,error:'nonce-endpoint-rebind'};
      if(!knownBases.has(base)&&knownBases.size>=4)return {ok:false,nonce,error:'endpoint-limit-reopen-environment'};
      for(const [key,value] of active)if(value.until<=Date.now()){value.controller?.abort();active.delete(key);}
      if(active.size>=2&&!active.has(nonce))return {ok:false,nonce,error:'diagnostic-scope-limit'};
      if(!install(base))return {ok:false,nonce,error:'credential-filter-unavailable'};
      knownBases.add(base);if(!active.has(nonce))active.set(nonce,{base,until:Date.now()+30000});
      return {ok:true,nonce,credentialFilter:true,redirectsBlocked:true};
    },
    clear(){for(const value of active.values())value.controller?.abort();active.clear();}
  });
})();
