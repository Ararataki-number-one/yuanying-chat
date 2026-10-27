/* Only the explicitly registered diagnostic URLs receive this temporary policy. */
(() => {
  'use strict';
  const protocolPath='/pocketchat-identity/v1/';
  const active=new Map(), linkedFrames=new Map(), knownBases=new Set();
  const paths=new Set(['document','worker.js','observe','result','capabilities','frame']);
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
    const primary=active.get(nonce),child=linkedFrames.get(nonce);
    const registered=child?.base===base?child:primary;
    const linked=registered?.purpose!=='frame'||registered.parent===primary&&primary?.purpose==='identity'&&primary.crossOriginFrame===true&&primary.frameBase===base&&primary.until>Date.now();
    const operation=url.pathname.slice(protocolPath.length);
    const purposeAllowed=registered&&(registered.purpose==='capabilities'?operation==='capabilities':registered.purpose==='frame'?operation==='frame':['document','worker.js','observe','result'].includes(operation));
    const frameFlag=url.searchParams.has('frame');
    const valid=registered&&linked&&purposeAllowed&&registered.base===base&&registered.until>Date.now()
      &&url.searchParams.getAll('nonce').length===1
      &&Array.from(url.searchParams.keys()).every(key=>key==='nonce'||key==='source'||key==='frame')
      &&(!url.searchParams.has('source')||url.pathname===protocolPath+'observe'&&url.searchParams.getAll('source').length===1&&url.searchParams.get('source')==='worker')
      &&(!frameFlag||operation==='document'&&registered.purpose==='identity'&&registered.crossOriginFrame===true&&url.searchParams.getAll('frame').length===1&&url.searchParams.get('frame')==='1')
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
    if(registration.purpose!=='identity')return {ok:false,nonce,error:'diagnostic-purpose-mismatch'};
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
  async function capabilities(nonce,base) {
    const registration=active.get(nonce);
    if(!registration||registration.base!==base||registration.until<=Date.now())return {ok:false,nonce,error:'diagnostic-scope-expired'};
    if(registration.purpose!=='capabilities')return {ok:false,nonce,error:'diagnostic-purpose-mismatch'};
    if(registration.inFlight)return {ok:false,nonce,error:'capabilities-already-in-flight'};
    const controller=new AbortController();registration.controller=controller;registration.inFlight=true;
    let timedOut=false,httpStatus=0,size=0;
    const timer=setTimeout(()=>{timedOut=true;controller.abort();},Math.min(3000,registration.until-Date.now()));
    try {
      const response=await fetch(base+'capabilities?nonce='+nonce,{credentials:'omit',referrerPolicy:'no-referrer',redirect:'error',cache:'no-store',signal:controller.signal});
      httpStatus=response.status;
      if(!Number.isInteger(httpStatus)||httpStatus<100||httpStatus>599)throw Error('service-response-status');
      const reader=response.body?.getReader();if(!reader)throw Error('bounded-stream-unavailable');
      const chunks=[];
      try {
        for(;;){
          const item=await reader.read();if(item.done)break;
          if(!(item.value instanceof Uint8Array)||!Number.isSafeInteger(item.value.byteLength)||item.value.byteLength<0||size+item.value.byteLength>16384){await reader.cancel();throw Error('service-response-too-large');}
          size+=item.value.byteLength;chunks.push(item.value);
        }
      } finally {try{reader.releaseLock();}catch(_){}}
      if(controller.signal.aborted||active.get(nonce)!==registration||registration.until<=Date.now())throw Error('diagnostic-scope-cancelled');
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
      let service;
      try{service=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch(_){throw Error('service-json-invalid');}
      if(!service||typeof service!=='object'||Array.isArray(service))throw Error('service-json-invalid');
      return {ok:true,nonce,source:'extension-background-control',httpStatus,responseBytes:size,service};
    } catch (error) {
      const known=new Set(['service-response-status','bounded-stream-unavailable','service-response-too-large','diagnostic-scope-cancelled','service-json-invalid']);
      const reason=controller.signal.aborted?(timedOut?'service-timeout':'service-cancelled'):known.has(error?.message)?error.message:'service-connection-or-certificate-unavailable';
      return {ok:false,nonce,source:'extension-background-control',httpStatus,responseBytes:size,error:reason};
    } finally {clearTimeout(timer);if(registration.controller===controller){registration.controller=null;registration.inFlight=false;}}
  }
  function discardPrimary(nonce){active.get(nonce)?.controller?.abort();active.delete(nonce);linkedFrames.get(nonce)?.controller?.abort();linkedFrames.delete(nonce);}
  function prune(){
    for(const [key,value] of active)if(value.until<=Date.now())discardPrimary(key);
    for(const [key,value] of linkedFrames)if(value.until<=Date.now()||active.get(key)!==value.parent)linkedFrames.delete(key);
  }
  globalThis.PocketRequestIdentityBackground=Object.freeze({
    handle(configuration) {
      const nonce=configuration?.nonce;
      if(typeof nonce!=='string'||!/^[0-9a-f]{32}$/.test(nonce))return {ok:false,error:'invalid-nonce'};
      if(configuration.action==='cancel'){
        if(configuration.endpoint===undefined){discardPrimary(nonce);return {ok:true,nonce};}
        const base=endpoint(configuration.endpoint);if(!base)return {ok:false,nonce,error:'invalid-endpoint'};
        const primary=active.get(nonce),child=linkedFrames.get(nonce);
        if(primary?.base===base){discardPrimary(nonce);return {ok:true,nonce};}
        if(child?.base===base){child.controller?.abort();linkedFrames.delete(nonce);return {ok:true,nonce};}
        return primary||child?{ok:false,nonce,error:'scope-endpoint-mismatch'}:{ok:true,nonce};
      }
      const base=endpoint(configuration.endpoint);
      if(!base)return {ok:false,nonce,error:'invalid-endpoint'};
      if(configuration.action==='evidence')return evidence(nonce,base);
      if(configuration.action==='capabilities')return capabilities(nonce,base);
      if(configuration.action!=='register')return {ok:false,nonce,error:'invalid-action'};
      const purpose=configuration.purpose===undefined?'identity':configuration.purpose;
      const crossOriginFrame=configuration.crossOriginFrame===true;
      if(!['identity','capabilities','frame'].includes(purpose)||configuration.crossOriginFrame!==undefined&&typeof configuration.crossOriginFrame!=='boolean'||crossOriginFrame&&purpose!=='identity')return {ok:false,nonce,error:'invalid-purpose'};
      const frameBase=crossOriginFrame?endpoint(configuration.frameEndpoint):'';
      if(crossOriginFrame&&(!frameBase||configuration.frameEndpoint!==frameBase||new URL(frameBase).origin===new URL(base).origin))return {ok:false,nonce,error:'invalid-frame-endpoint'};
      if(!crossOriginFrame&&configuration.frameEndpoint!==undefined&&configuration.frameEndpoint!=='')return {ok:false,nonce,error:'invalid-frame-endpoint'};
      prune();
      if(purpose==='frame'){
        const primary=active.get(nonce),parentBase=endpoint(configuration.parentEndpoint),existing=linkedFrames.get(nonce);
        if(!primary||primary.purpose!=='identity'||primary.crossOriginFrame!==true||primary.frameBase!==base||!parentBase||configuration.parentEndpoint!==parentBase||primary.base!==parentBase||primary.until<=Date.now())return {ok:false,nonce,error:'frame-parent-unconfirmed'};
        if(existing&&(existing.base!==base||existing.parent!==primary))return {ok:false,nonce,error:'nonce-frame-rebind'};
        if(!existing&&active.size+linkedFrames.size>=2)return {ok:false,nonce,error:'diagnostic-scope-limit'};
        if(!knownBases.has(base)&&knownBases.size>=4)return {ok:false,nonce,error:'endpoint-limit-reopen-environment'};
        if(!install(base))return {ok:false,nonce,error:'credential-filter-unavailable'};
        knownBases.add(base);if(!existing)linkedFrames.set(nonce,{base,purpose,parent:primary,until:primary.until});
        return {ok:true,nonce,credentialFilter:true,redirectsBlocked:true,purpose,crossOriginFrame:false};
      }
      if(active.has(nonce)&&active.get(nonce).base!==base)return {ok:false,nonce,error:'nonce-endpoint-rebind'};
      if(active.has(nonce)&&(active.get(nonce).purpose!==purpose||active.get(nonce).crossOriginFrame!==crossOriginFrame||active.get(nonce).frameBase!==frameBase))return {ok:false,nonce,error:'nonce-purpose-rebind'};
      if(!knownBases.has(base)&&knownBases.size>=4)return {ok:false,nonce,error:'endpoint-limit-reopen-environment'};
      if(active.size+linkedFrames.size>=2&&!active.has(nonce))return {ok:false,nonce,error:'diagnostic-scope-limit'};
      if(!install(base))return {ok:false,nonce,error:'credential-filter-unavailable'};
      knownBases.add(base);if(!active.has(nonce))active.set(nonce,{base,purpose,crossOriginFrame,frameBase,until:Date.now()+30000});
      return {ok:true,nonce,credentialFilter:true,redirectsBlocked:true,purpose,crossOriginFrame};
    },
    clear(){for(const value of active.values())value.controller?.abort();for(const value of linkedFrames.values())value.controller?.abort();active.clear();linkedFrames.clear();}
  });
})();
