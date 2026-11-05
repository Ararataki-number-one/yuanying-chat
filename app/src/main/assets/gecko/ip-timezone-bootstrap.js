/* DIAGNOSTIC-ONLY: bounded enum observations, never an admission condition. */
(() => {
  'use strict';
  const STAGES=new Set(['bootstrap-loaded','create-enter','create-rejected','create-ready','lookup-received','lookup-rejected','lookup-start','fetch-start','fetch-response','fetch-rejected','deadline','finish-null','finish-observed','before-request','before-redirect','authorization','native-lookup-received','bootstrap-bound','proxy-event','proxy-authorization','header-event','header-authorization','header-listener']);
  const RESULTS=new Set(['none','ready','rejected','missing-port','runtime-url','features','registration','exception','shape-or-busy','pending','accepted','absent','invalid','closed','cancelled','observed']);
  const ERRORS=new Set(['none','AbortError','NetworkError','TypeError','SecurityError','TimeoutError','NotAllowedError','InvalidStateError','other']);
  const SCRIPTS=['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js'];
  const events=[];let omitted=0,invalid=0;
  const urlClass=value=>{if(value==='https://ipwho.is/?fields=success,ip,timezone.id')return 'geo-exact';try{return new URL(value).hostname==='ipwho.is'?'geo-host-variant':'other';}catch(_){return 'other';}};
  const runtimeManifest=()=>{try{const m=browser.runtime.getManifest(),scripts=m?.background?.scripts;return {available:true,version:m?.version==='2.1.2.104'?'2.1.2.104':'other',id:m?.browser_specific_settings?.gecko?.id==='browser@pocketchat.local'?'browser@pocketchat.local':'other',scriptCount:Array.isArray(scripts)?Math.min(10000,scripts.length):-1,scripts:Array.isArray(scripts)?scripts.slice(0,8).map(s=>SCRIPTS.includes(s)?s:'other'):[]};}catch(_){return {available:false,version:'unavailable',id:'unavailable',scriptCount:-1,scripts:[]};}};
  const principal=value=>{
    if(value===undefined||value===null||value==='')return 'absent';
    if(typeof value!=='string')return 'invalid';
    try{const u=new URL(value),own=new URL(browser.runtime.getURL(''));return !u.username&&!u.password&&u.protocol===own.protocol&&u.host===own.host?'own':'foreign';}catch(_){return 'invalid';}
  };
  const record=(stage,details=null,result='none',error=null)=>{
    try{
      if(!STAGES.has(stage)||!RESULTS.has(result)){invalid=Math.min(10000,invalid+1);return;}
      const name=error===null?'none':ERRORS.has(error?.name)?error.name:'other';
      const row={sequence:events.length+1,stage,urlClass:urlClass(details?.url),exactGeo:details?.url==='https://ipwho.is/?fields=success,ip,timezone.id',get:details?.method==='GET',origin:details===null?'unseen':principal(details.originUrl),document:details===null?'unseen':principal(details.documentUrl),requestIdPresent:typeof details?.requestId==='string'&&details.requestId.length>0&&details.requestId.length<=128,result,errorName:name};
      if(events.some(old=>Object.keys(row).every(key=>key==='sequence'||old[key]===row[key]))){omitted=Math.min(10000,omitted+1);return;}
      if(events.length>=32){omitted=Math.min(10000,omitted+1);return;}events.push(Object.freeze(row));
    }catch(_){invalid=Math.min(10000,invalid+1);}
  };
  globalThis.PocketIpTimeZoneDiagnostic=Object.freeze({record,snapshot(nonce){
    if(typeof nonce!=='string'||!(/^[0-9a-f]{32}$/).test(nonce))return null;
    return {schema:1,diagnosticOnly:true,releaseAcceptance:false,requestNonce:nonce,runtimeManifest:runtimeManifest(),helperPresence:{bootstrap:typeof globalThis.PocketIpTimeZoneBootstrap,headers:typeof globalThis.PocketGeckoRequestHeaders,identity:typeof globalThis.PocketRequestIdentityBackground,timezone:typeof globalThis.PocketNativeTimezoneBridge},events:events.map(row=>({...row})),omitted,invalid,bootstrapObject:typeof globalThis.PocketIpTimeZoneBootstrap==='object',bootstrapCreate:typeof globalThis.PocketIpTimeZoneBootstrap?.create==='function',headersObject:typeof globalThis.PocketGeckoRequestHeaders==='object'};
  }});
  record('bootstrap-loaded');
})();

/* Private native IP-timezone bootstrap; no webpage or JavaScript clock changes. */
(() => {
  'use strict';
  const ipProbe=(...args)=>{try{globalThis.PocketIpTimeZoneDiagnostic?.record(...args);}catch(_){}};
  const SOURCE='https://ipwho.is/?fields=success,ip,timezone.id';
  const MAX_BYTES=8192,DEADLINE_MS=8000;
  // A timeout withdraws authorization immediately. Keep the transport slot
  // until its actual fetch/read settles, including across native reconnects.
  let transportJob=null;
  const hex=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
  const nativeId=value=>Number.isInteger(value)&&value>0&&value<=2147483647;
  const keys=(value,expected)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===expected;
  const create=port=>{
    ipProbe('create-enter');
    if(!port||typeof port!=='object'){ipProbe('create-rejected',null,'missing-port');return null;}
    let own,event,redirectEvent,closed=false,pending=null;
    try{
      const url=new URL(browser.runtime.getURL(''));
      if(url.protocol!=='moz-extension:'||!url.hostname||url.username||url.password){ipProbe('create-rejected',null,'runtime-url');return null;}
      // URL.origin is "null" for custom schemes. Compare the actual authority.
      own=url.protocol+'//'+url.host;event=browser.webRequest?.onBeforeRequest;redirectEvent=browser.webRequest?.onBeforeRedirect;
      if(typeof event?.addListener!=='function'||typeof event?.removeListener!=='function'||typeof fetch!=='function'||typeof AbortController!=='function'||typeof TextDecoder!=='function'){ipProbe('create-rejected',null,'features');return null;}
    }catch(error){ipProbe('create-rejected',null,'exception',error);return null;}
    const principal=details=>{
      let observed=false;
      for(const key of ['originUrl','documentUrl']){
        const value=details[key];if(value===undefined||value===null||value==='')continue;
        if(typeof value!=='string')return false;
        try{const url=new URL(value);if(url.username||url.password||url.protocol+'//'+url.host!==own)return false;observed=true;}catch(_){return false;}
      }
      return observed;
    };
    const request=details=>details&&typeof details==='object'&&details.url===SOURCE&&details.method==='GET'
      &&typeof details.requestId==='string'&&details.requestId.length>0&&details.requestId.length<=128&&principal(details);
    const current=job=>!closed&&pending===job&&!job.finished;
    const finish=(job,value)=>{
      if(job.finished)return;ipProbe(value===null?'finish-null':'finish-observed',null,value===null?'rejected':'observed');job.finished=true;if(pending===job)pending=null;clearTimeout(job.timer);
      if(value===null){try{job.controller.abort();}catch(_){}try{Promise.resolve(job.reader?.cancel()).catch(()=>{});}catch(_){}}
      job.resolve(value);
    };
    const beforeRequest=details=>{
      ipProbe('before-request',details);
      const job=pending;if(!job||!current(job))return;
      if(job.requestId!==null&&details?.requestId!==job.requestId)return;
      if(!request(details)){if(job.requestId!==null&&details?.requestId===job.requestId)finish(job,null);return;}
      // Proxy selection may precede this event. Accept that same claimed id
      // once, while a second event is a restart rather than a reusable grant.
      if(job.beforeSeen){finish(job,null);return;}
      job.requestId=details.requestId;job.beforeSeen=true;
    };
    const beforeRedirect=details=>{ipProbe('before-redirect',details);const job=pending;if(job&&details?.requestId===job.requestId)finish(job,null);};
    try{
      event.addListener(beforeRequest,{urls:['https://ipwho.is/*']});
      if(typeof redirectEvent?.addListener==='function'&&typeof redirectEvent?.removeListener==='function')redirectEvent.addListener(beforeRedirect,{urls:['https://ipwho.is/*']});
    }catch(_){try{event.removeListener(beforeRequest);}catch(_){}try{redirectEvent?.removeListener(beforeRedirect);}catch(_){}ipProbe('create-rejected',null,'registration');return null;}
    ipProbe('create-ready',null,'ready');
    const authorization=details=>{
      ipProbe('authorization',details,pending?'pending':'absent');
      const job=pending;
      if(!job||!current(job)||!request(details))return null;
      if(job.requestId===null)job.requestId=details.requestId;
      return details.requestId===job.requestId?job.authorization:null;
    };
    return Object.freeze({
      lookup(message){
        ipProbe('lookup-received');
        if(closed||pending!==null||transportJob!==null||!keys(message,'id,kind,requestToken,routeStamp,source')||message.kind!=='timezoneIpLookup'||!nativeId(message.id)||!hex(message.requestToken)||!hex(message.routeStamp)||message.source!==SOURCE){ipProbe('lookup-rejected',null,'shape-or-busy');return Promise.resolve(null);}
        return new Promise(resolve=>{
          ipProbe('lookup-start',null,'pending');
          const job={id:message.id,requestToken:message.requestToken,authorization:Object.freeze({requestToken:message.requestToken,routeStamp:message.routeStamp}),requestId:null,beforeSeen:false,controller:new AbortController(),reader:null,timer:null,finished:false,resolve};pending=transportJob=job;
          job.timer=setTimeout(()=>{ipProbe('deadline');finish(job,null);},DEADLINE_MS);
          (async()=>{
            try{
              ipProbe('fetch-start');
              const response=await fetch(SOURCE,{method:'GET',credentials:'omit',cache:'no-store',referrer:'',referrerPolicy:'no-referrer',redirect:'error',signal:job.controller.signal});
              ipProbe('fetch-response',null,response?.ok===true?'accepted':'rejected');
              if(!current(job)||job.requestId===null||!job.beforeSeen||response?.ok!==true||response.url!==SOURCE||response.redirected!==false||typeof response.body?.getReader!=='function'){finish(job,null);return;}
              job.reader=response.body.getReader();const chunks=[];let bytes=0;
              for(;;){
                const part=await job.reader.read();if(!current(job))return;if(part.done)break;
                if(!(part.value instanceof Uint8Array)||part.value.byteLength===0||bytes+part.value.byteLength>MAX_BYTES){finish(job,null);return;}
                const copy=new Uint8Array(part.value);chunks.push(copy);bytes+=copy.byteLength;
              }
              if(!current(job)||bytes===0){finish(job,null);return;}
              const raw=new Uint8Array(bytes);let offset=0;for(const chunk of chunks){raw.set(chunk,offset);offset+=chunk.byteLength;}
              // Preserve duplicate JSON members, whitespace and a UTF-8 BOM.
              // The native policy, rather than this transport, validates JSON.
              const body=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);
              finish(job,JSON.stringify({schema:1,status:'observed',requestToken:job.authorization.requestToken,routeStamp:job.authorization.routeStamp,source:SOURCE,body}));
            }catch(error){ipProbe('fetch-rejected',null,'exception',error);finish(job,null);}finally{try{job.reader?.releaseLock();}catch(_){}if(transportJob===job)transportJob=null;}
          })();
        });
      },
      cancel(message){
        const job=pending;
        if(!job||!keys(message,'id,kind,requestToken')||message.kind!=='timezoneIpCancel'||!nativeId(message.id)||!hex(message.requestToken)||message.id!==job.id||message.requestToken!==job.requestToken)return false;
        finish(job,null);return true;
      },
      authorization,
      close(){
        if(closed)return;closed=true;if(pending)finish(pending,null);
        try{event.removeListener(beforeRequest);}catch(_){}try{redirectEvent?.removeListener(beforeRedirect);}catch(_){}
      }
    });
  };
  globalThis.PocketIpTimeZoneBootstrap=Object.freeze({create});
})();
