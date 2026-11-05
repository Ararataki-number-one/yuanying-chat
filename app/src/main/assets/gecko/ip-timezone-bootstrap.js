/* Private native IP-timezone bootstrap; no webpage or JavaScript clock changes. */
(() => {
  'use strict';
  const SOURCE='https://ipwho.is/?fields=success,ip,timezone.id';
  const MAX_BYTES=8192,DEADLINE_MS=8000;
  // A timeout withdraws authorization immediately. Keep the transport slot
  // until its actual fetch/read settles, including across native reconnects.
  let transportJob=null;
  const hex=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
  const nativeId=value=>Number.isInteger(value)&&value>0&&value<=2147483647;
  const keys=(value,expected)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===expected;
  const create=port=>{
    if(!port||typeof port!=='object')return null;
    let own,event,redirectEvent,closed=false,pending=null;
    try{
      const url=new URL(browser.runtime.getURL(''));
      if(url.protocol!=='moz-extension:'||!url.hostname||url.username||url.password)return null;
      // URL.origin is "null" for custom schemes. Compare the actual authority.
      own=url.protocol+'//'+url.host;event=browser.webRequest?.onBeforeRequest;redirectEvent=browser.webRequest?.onBeforeRedirect;
      if(typeof event?.addListener!=='function'||typeof event?.removeListener!=='function'||typeof fetch!=='function'||typeof AbortController!=='function'||typeof TextDecoder!=='function')return null;
    }catch(_){return null;}
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
      if(job.finished)return;job.finished=true;if(pending===job)pending=null;clearTimeout(job.timer);
      if(value===null){try{job.controller.abort();}catch(_){}try{Promise.resolve(job.reader?.cancel()).catch(()=>{});}catch(_){}}
      job.resolve(value);
    };
    const beforeRequest=details=>{
      const job=pending;if(!job||!current(job))return;
      if(job.requestId!==null&&details?.requestId!==job.requestId)return;
      if(!request(details)){if(job.requestId!==null&&details?.requestId===job.requestId)finish(job,null);return;}
      // Proxy selection may precede this event. Accept that same claimed id
      // once, while a second event is a restart rather than a reusable grant.
      if(job.beforeSeen){finish(job,null);return;}
      job.requestId=details.requestId;job.beforeSeen=true;
    };
    const beforeRedirect=details=>{const job=pending;if(job&&details?.requestId===job.requestId)finish(job,null);};
    try{
      event.addListener(beforeRequest,{urls:['https://ipwho.is/*']});
      if(typeof redirectEvent?.addListener==='function'&&typeof redirectEvent?.removeListener==='function')redirectEvent.addListener(beforeRedirect,{urls:['https://ipwho.is/*']});
    }catch(_){try{event.removeListener(beforeRequest);}catch(_){}try{redirectEvent?.removeListener(beforeRedirect);}catch(_){}return null;}
    const authorization=details=>{
      const job=pending;
      if(!job||!current(job)||!request(details))return null;
      if(job.requestId===null)job.requestId=details.requestId;
      return details.requestId===job.requestId?job.authorization:null;
    };
    return Object.freeze({
      lookup(message){
        if(closed||pending!==null||transportJob!==null||!keys(message,'id,kind,requestToken,routeStamp,source')||message.kind!=='timezoneIpLookup'||!nativeId(message.id)||!hex(message.requestToken)||!hex(message.routeStamp)||message.source!==SOURCE)return Promise.resolve(null);
        return new Promise(resolve=>{
          const job={id:message.id,requestToken:message.requestToken,authorization:Object.freeze({requestToken:message.requestToken,routeStamp:message.routeStamp}),requestId:null,beforeSeen:false,controller:new AbortController(),reader:null,timer:null,finished:false,resolve};pending=transportJob=job;
          job.timer=setTimeout(()=>finish(job,null),DEADLINE_MS);
          (async()=>{
            try{
              const response=await fetch(SOURCE,{method:'GET',credentials:'omit',cache:'no-store',referrer:'',referrerPolicy:'no-referrer',redirect:'error',signal:job.controller.signal});
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
            }catch(_){finish(job,null);}finally{try{job.reader?.releaseLock();}catch(_){}if(transportJob===job)transportJob=null;}
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
