/* A top-level controlled page is observed only after explicit native navigation. */
(() => {
  'use strict';
  function signal(value) {
    if(!value||typeof value!=='object'||typeof value.ua!=='string'||!value.ua||value.ua.length>2048
      ||typeof value.language!=='string'||!value.language||value.language.length>128
      ||!Array.isArray(value.languages)||!value.languages.length||value.languages.length>8
      ||value.languages.some(item=>typeof item!=='string'||!item||item.length>128))return null;
    return {ua:value.ua,language:value.language,languages:value.languages.slice()};
  }
  function frameApis(value) {
    if(!value||value.schema!==1||value.requested!==true||value.source!=='controlled-cross-origin-iframe'||value.probeVersion!==1||!value.probes||typeof value.probes!=='object')return null;
    const probes={};
    for(const name of ['canvas','audio','fonts','webgl']){
      if(name==='audio'||name==='fonts'){probes[name]={state:'uncovered',reason:'not-covered-by-controlled-frame-graphics'};continue;}
      const raw=value.probes[name];if(!raw||typeof raw!=='object'||!['available','restricted','failed','uncovered'].includes(raw.state)){probes[name]={state:'uncovered',reason:'invalid-or-missing-probe'};continue;}
      const clean=probes[name]={state:raw.state,reason:typeof raw.reason==='string'?raw.reason.slice(0,256):'reason-unavailable'};
      if(raw.hashAlgorithm==='sha256'&&typeof raw.hash==='string'&&/^[0-9a-f]{64}$/.test(raw.hash)){clean.hash=raw.hash;clean.hashAlgorithm='sha256';}if(raw.hashUnavailable===true)clean.hashUnavailable=true;
      if(raw.readbackHashAlgorithm==='sha256'&&typeof raw.readbackHash==='string'&&/^[0-9a-f]{64}$/.test(raw.readbackHash)){clean.readbackHash=raw.readbackHash;clean.readbackHashAlgorithm='sha256';}if(raw.readbackHashUnavailable===true)clean.readbackHashUnavailable=true;
      for(const key of ['pixels','readbackPixels','readbackBytes','maxTextureSize','maxRenderbufferSize','maxVertexAttribs','extensionCount'])if(typeof raw[key]==='number'&&Number.isFinite(raw[key])&&raw[key]>=0&&raw[key]<=1000000)clean[key]=raw[key];
      for(const key of ['version','shadingLanguageVersion','vendor','renderer','unmaskedRenderer'])if(typeof raw[key]==='string')clean[key]=raw[key].slice(0,256);
      if(Array.isArray(raw.extensions)&&raw.extensions.length<=7&&raw.extensions.every(item=>typeof item==='string'&&item.length<=128))clean.extensions=raw.extensions.slice();
      if(clean.state==='available'){
        const digest=typeof clean.hash==='string'||clean.hashUnavailable===true,complete=name==='canvas'?clean.pixels===4096&&digest:['version','shadingLanguageVersion','vendor','renderer'].every(key=>typeof clean[key]==='string'&&clean[key].length>0)&&['maxTextureSize','maxRenderbufferSize','maxVertexAttribs','extensionCount'].every(key=>typeof clean[key]==='number')&&Array.isArray(clean.extensions)&&clean.readbackPixels===256&&clean.readbackBytes===1024&&(typeof clean.readbackHash==='string'||clean.readbackHashUnavailable===true)&&digest;
        if(!complete){clean.state='uncovered';clean.reason='incomplete-available-observation';}
      }
    }
    return {schema:1,requested:true,source:'controlled-cross-origin-iframe',probeVersion:1,status:['canvas','webgl'].every(name=>probes[name].state!=='uncovered')?'completed':'partial',durationMs:typeof value.durationMs==='number'&&Number.isFinite(value.durationMs)&&value.durationMs>=0?Math.min(value.durationMs,60000):0,limits:{canvasPixels:4096,audioFrames:0,fontCandidates:0,totalBudgetMs:1200},probes,protectionVerified:false,coverage:'controlled-cross-origin-iframe graphics only; independently sampled, not hash-equality attestation'};
  }
  function frameResult(value,nonce,origin){
    const missing=reason=>({schema:1,status:'uncovered',nonce,origin,source:'controlled-cross-origin-iframe',reason,protectionVerified:false});
    if(!value||typeof value!=='object'||value.nonce!==nonce||value.origin!==origin||value.source!=='controlled-cross-origin-iframe')return missing('invalid-frame-observation');
    if(value.status==='uncovered')return missing(['frame-unavailable','frame-timeout','frame-not-configured','frame-observation-invalid','frame-cancelled'].includes(value.reason)?value.reason:'frame-unavailable');
    if(value.status!=='complete')return missing('invalid-frame-observation');
    const apiChecks=frameApis(value.apiChecks);return apiChecks?{schema:1,status:'complete',nonce,origin,source:'controlled-cross-origin-iframe',apiChecks,protectionVerified:false}:missing('invalid-frame-api-observation');
  }
  function run(configuration,stops) {
    const nonce=configuration?.nonce;
    const failed=reason=>({schema:1,nonce:typeof nonce==='string'?nonce:'',status:'failed',source:'controlled-top-level-document',error:reason});
    if(typeof nonce!=='string'||!/^[0-9a-f]{32}$/.test(nonce))return Promise.resolve(failed('invalid-nonce'));
    let base,target,frameOrigin;
    try {
      base=new URL(configuration.endpoint);target=new URL('document?nonce='+nonce,base);
      if(configuration.crossOriginFrame===true){
        if(typeof configuration.frameEndpoint!=='string'||configuration.frameEndpoint.length>2048)return Promise.resolve(failed('invalid-frame-endpoint'));
        let frame;try{frame=new URL(configuration.frameEndpoint);}catch{return Promise.resolve(failed('invalid-frame-endpoint'));}
        if(frame.protocol!=='https:'||frame.username||frame.password||frame.search||frame.hash||frame.pathname!=='/pocketchat-identity/v1/'||frame.origin===base.origin||frame.href!==configuration.frameEndpoint)return Promise.resolve(failed('invalid-frame-endpoint'));
        frameOrigin=frame.origin;target.searchParams.set('frame','1');
      }
      if(base.protocol!=='https:'||base.username||base.password||base.search||base.hash||base.pathname!=='/pocketchat-identity/v1/'
        ||window.top!==window||location.href!==target.href)return Promise.resolve(failed('wrong-document'));
    } catch {return Promise.resolve(failed('invalid-endpoint'));}
    return new Promise(resolve=>{
      let done=false;
      const finish=value=>{if(done)return;done=true;clearTimeout(timer);window.removeEventListener('message',receive);resolve(value);};
      const receive=event=>{
        if(event.source!==window||event.origin!==base.origin||event.isTrusted!==true)return;
        const value=event.data;
        if(!value||typeof value!=='object'||value.pocketRequestIdentity!==nonce||value.nonce!==nonce||value.schema!==1||value.protocol!=='pocketchat-request-identity-v1'||value.source!=='controlled-top-level-document')return;
        if(value.status==='failed'){const reasons=['worker-response-too-large','worker-response-stream-unavailable','worker-response-invalid-stream','worker-response-invalid-length','worker-response-invalid-utf8','worker-response-invalid-json','worker-response-http-failed','worker-response-protocol-mismatch','worker-response-timeout','worker-response-transport-failed','worker-unavailable','worker-timeout','worker-request-failed'];finish(failed(reasons.includes(value.error)?value.error:'controlled-page-or-worker-unavailable'));return;}
        if(value.status!=='complete')return;
        const document=signal(value.document),worker=signal(value.worker);
        if(!document||!worker){finish(failed('incomplete-javascript-observation'));return;}
        finish({schema:1,nonce,status:'complete',source:'controlled-top-level-document',document,worker,...(frameOrigin?{crossOriginFrame:frameResult(value.crossOriginFrame,nonce,frameOrigin)}:{})});
      };
      const timer=setTimeout(()=>finish(failed('controlled-page-observation-timeout')),6000);
      if(Array.isArray(stops))stops.push(()=>{if(done)return;try{window.postMessage({pocketRequestIdentityCancel:nonce},base.origin);}catch{}finish(failed('cancelled'));});
      window.addEventListener('message',receive);
      window.postMessage({pocketRequestIdentityCollect:nonce},base.origin);
    });
  }
  globalThis.PocketRequestIdentityAudit=Object.freeze({run});
})();
