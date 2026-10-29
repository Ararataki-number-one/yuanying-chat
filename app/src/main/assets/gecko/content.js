/* Trusted host bridge in the extension's isolated world; never exposed to page scripts. */
(() => {
  'use strict';
  // Installed at document_start, before a delayed page-state request can race
  // with an already active drag. Keep this separate from send-message intent.
  if (window === window.top && location.origin === 'https://chatgpt.com' && !window.__pocketReadingInteraction) {
    let revision=0,lifecycle=0,touches=0,lastMotion=-Infinity,live=true;
    const pointers=new Set(),clock=()=>performance.now();
    const moving=()=>pointers.size>0||touches>0||clock()-lastMotion<450;
    const note=()=>{revision++;lastMotion=clock();};
    const listen=(type,run)=>document.addEventListener(type,event=>{if(event.isTrusted)run(event);},{capture:true,passive:true});
    listen('pointerdown',event=>{pointers.add(event.pointerId);note();});
    listen('pointermove',event=>{if(pointers.has(event.pointerId))note();});
    for(const type of ['pointerup','pointercancel'])listen(type,event=>{if(pointers.delete(event.pointerId))note();});
    listen('touchstart',event=>{touches=event.touches.length;note();});
    listen('touchmove',event=>{touches=event.touches.length;note();});
    for(const type of ['touchend','touchcancel'])listen(type,event=>{touches=event.touches.length;note();});
    listen('wheel',note);
    listen('keydown',event=>{
      if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','PageUp','PageDown','Home','End',' ','Spacebar'].includes(event.key))return;
      const target=event.target instanceof Element?event.target:event.target?.parentElement;
      if(!target?.closest('textarea,input,[contenteditable]:not([contenteditable="false"]),[role="textbox"]'))note();
    });
    // Continue the user's interaction through momentum. A quiet, programmatic
    // scroll (including our own restoration) does not become a new gesture.
    listen('scroll',()=>{if(moving())note();});
    const leave=()=>{lifecycle++;pointers.clear();touches=0;lastMotion=-Infinity;};
    window.addEventListener('pagehide',()=>{live=false;leave();});
    window.addEventListener('pageshow',()=>{if(!live){live=true;lifecycle++;}});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')leave();});
    window.__pocketReadingInteraction=Object.freeze({revision:()=>revision,lifecycle:()=>lifecycle,
      available:()=>live&&document.visibilityState!=='hidden',interacting:moving});
  }
  // Only observe trusted editing. This state never fills, focuses or submits an
  // editor, and is independent of the website's send-message observation.
  if (window === window.top && location.origin === 'https://chatgpt.com' && !window.__pocketComposerInteraction) {
    let revision=0,lifecycle=0,live=true,composing=null;
    const editor=target=>{
      const element=target instanceof Element?target:target?.parentElement;
      return element?.closest('textarea,input,[contenteditable]:not([contenteditable="false"]),[role="textbox"]')||null;
    };
    for(const type of ['keydown','beforeinput','input','compositionstart','compositionupdate','compositionend'])
      document.addEventListener(type,event=>{
        if(!event.isTrusted)return;const input=editor(event.target);if(!input)return;
        if(type==='keydown'&&['Shift','Control','Alt','Meta','CapsLock','NumLock','ScrollLock'].includes(event.key))return;
        revision++;
        if(type==='compositionstart'||type==='compositionupdate')composing=input;
        // A final input may still report isComposing. A trusted end, or a
        // subsequent explicitly noncomposing input, releases the active span.
        else if(composing===input&&(type==='compositionend'||type==='input'&&event.isComposing===false))composing=null;
      },{capture:true,passive:true});
    window.addEventListener('pagehide',event=>{live=false;lifecycle++;if(event.isTrusted)composing=null;});
    window.addEventListener('pageshow',()=>{if(!live){live=true;lifecycle++;}});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')lifecycle++;});
    window.__pocketComposerInteraction=Object.freeze({snapshot:()=>({revision,lifecycle,
      composing:!!composing&&composing.isConnected,available:live&&document.visibilityState!=='hidden'})});
  }
  const port = browser.runtime.connectNative('pocketpage');
  const appearanceDocument = Array.from(crypto.getRandomValues(new Uint32Array(4)), value => value.toString(16).padStart(8, '0')).join('-');
  const appearanceIdentity = {appearanceProtocol: 1, appearanceDocument};
  let auditCancel=()=>{};
  const text=value=>typeof value==='string'?value.slice(0,2048):'';
  const cleanSignal=value=>{
    if(!value||typeof value!=='object')return {error:'No observation'};
    const clean={};
    for(const key of ['ua','appVersion','platform','language','zone','renderer','rtc','error'])if(typeof value[key]==='string')clean[key]=text(value[key]);
    for(const key of ['cpu','memory','offset'])if(value[key]===null||typeof value[key]==='number'&&Number.isFinite(value[key]))clean[key]=value[key];
    if(Array.isArray(value.languages)&&value.languages.length>0&&value.languages.length<=8&&value.languages.every(item=>typeof item==='string'&&item.length>0&&item.length<=2048))clean.languages=value.languages.map(text);
    for(const group of ['screen','viewport'])if(value[group]&&typeof value[group]==='object'){clean[group]={};for(const key of ['width','height','availWidth','availHeight','depth','pixelRatio','touch'])if(typeof value[group][key]==='number'&&Number.isFinite(value[group][key]))clean[group][key]=value[group][key];}
    return clean;
  };
  const apiNames=['canvas','audio','fonts','webgl'];
  const apiLimits={canvasPixels:4096,audioFrames:2048,fontCandidates:5,totalBudgetMs:1200};
  const contextLimits=source=>source==='dedicated-worker'?{canvasPixels:4096,audioFrames:0,fontCandidates:0,totalBudgetMs:1200}:{...apiLimits};
  const missingApiChecks=(reason,source='page-main-world')=>({schema:1,requested:true,source:'unavailable',expectedSource:source,probeVersion:1,status:'partial',durationMs:0,limits:contextLimits(source),probes:Object.fromEntries(apiNames.map(name=>[name,{state:'uncovered',reason}])),protectionVerified:false,coverage:'current-page-main-world-only; frame and Worker API operations not sampled'});
  const cleanApiChecks=(value,source='page-main-world')=>{
    if(!value||typeof value!=='object'||value.schema!==1||value.probeVersion!==1||value.requested!==true||value.source!==source||!value.probes||typeof value.probes!=='object')return missingApiChecks('page-api-observation-unavailable',source);
    const probes={};
    for(const name of apiNames){
      if(source==='dedicated-worker'&&(name==='audio'||name==='fonts')){probes[name]={state:'uncovered',reason:'not-applicable-in-worker'};continue;}
      const raw=value.probes[name];if(!raw||typeof raw!=='object'||!['available','restricted','failed','uncovered'].includes(raw.state)){probes[name]={state:'uncovered',reason:'invalid-or-missing-probe'};continue;}
      const clean=probes[name]={state:raw.state,reason:typeof raw.reason==='string'?raw.reason.slice(0,256):'reason-unavailable'};
      if(raw.hashAlgorithm==='sha256'&&typeof raw.hash==='string'&&/^[0-9a-f]{64}$/.test(raw.hash)){clean.hash=raw.hash;clean.hashAlgorithm='sha256';}
      if(raw.hashUnavailable===true)clean.hashUnavailable=true;
      if(source==='dedicated-worker'&&name==='webgl'){if(raw.readbackHashAlgorithm==='sha256'&&typeof raw.readbackHash==='string'&&/^[0-9a-f]{64}$/.test(raw.readbackHash)){clean.readbackHash=raw.readbackHash;clean.readbackHashAlgorithm='sha256';}if(raw.readbackHashUnavailable===true)clean.readbackHashUnavailable=true;}
      for(const key of ['pixels','frames','sampleRate','peak','candidateCount','maxTextureSize','maxRenderbufferSize','maxVertexAttribs','extensionCount','readbackPixels','readbackBytes'])if(typeof raw[key]==='number'&&Number.isFinite(raw[key])&&raw[key]>=0&&raw[key]<=1000000)clean[key]=raw[key];
      for(const key of ['version','shadingLanguageVersion','vendor','renderer','unmaskedRenderer'])if(typeof raw[key]==='string')clean[key]=raw[key].slice(0,256);
      if(Array.isArray(raw.extensions)&&raw.extensions.length<=7&&raw.extensions.every(item=>typeof item==='string'&&item.length<=128))clean.extensions=raw.extensions.slice();
      if(name==='fonts'&&Array.isArray(raw.samples)&&raw.samples.length<=5){clean.samples=[];for(const row of raw.samples){if(!row||typeof row.name!=='string'||row.name.length>128||!['monospaceWidth','sansSerifWidth'].every(key=>typeof row[key]==='number'&&Number.isFinite(row[key])&&row[key]>=0&&row[key]<=1000000)||row.faceCheck!==null&&typeof row.faceCheck!=='boolean')continue;clean.samples.push({name:row.name,faceCheck:row.faceCheck,monospaceWidth:row.monospaceWidth,sansSerifWidth:row.sansSerifWidth});}}
      if(clean.state==='available'){
        const digest=typeof clean.hash==='string'||clean.hashUnavailable===true;
        const complete=name==='canvas'?clean.pixels===4096&&digest:name==='audio'?clean.frames===2048&&clean.sampleRate===44100&&typeof clean.peak==='number'&&digest:name==='fonts'?clean.candidateCount===5&&clean.samples?.length===5&&digest:['version','shadingLanguageVersion','vendor','renderer'].every(key=>typeof clean[key]==='string'&&clean[key].length>0)&&['maxTextureSize','maxRenderbufferSize','maxVertexAttribs','extensionCount'].every(key=>typeof clean[key]==='number')&&Array.isArray(clean.extensions)&&digest&&(source!=='dedicated-worker'||clean.readbackPixels===256&&clean.readbackBytes===1024&&(typeof clean.readbackHash==='string'||clean.readbackHashUnavailable===true));
        if(!complete){clean.state='uncovered';clean.reason='incomplete-available-observation';}
      }
    }
    return {schema:1,requested:true,source,probeVersion:1,status:apiNames.every(name=>probes[name].state!=='uncovered')?'completed':'partial',durationMs:typeof value.durationMs==='number'&&Number.isFinite(value.durationMs)&&value.durationMs>=0?Math.min(value.durationMs,60000):0,limits:contextLimits(source),probes,protectionVerified:false,coverage:source==='page-main-world'?'current-page-main-world-only; frame and Worker API operations not sampled':source+'-only; independently sampled, not hash-equality attestation'};
  };
  const missingApiContexts=reason=>({schema:1,requested:true,frame:missingApiChecks(reason,'same-origin-srcdoc'),worker:missingApiChecks(reason,'dedicated-worker')});
  const cleanApiContexts=value=>{if(!value||value.schema!==1||value.requested!==true)return missingApiContexts('context-api-observation-unavailable');return {schema:1,requested:true,frame:cleanApiChecks(value.frame,'same-origin-srcdoc'),worker:cleanApiChecks(value.worker,'dedicated-worker')};};
  const cleanIp=value=>value&&typeof value.ip==='string'?{ip:value.ip.slice(0,128)}:{error:'No verifiable response'};
  const cleanHeaders=value=>{const result={headers:{}};if(value&&value.headers&&typeof value.headers==='object')for(const key of Object.keys(value.headers))if(/^(user-agent|accept-language)$/i.test(key)&&typeof value.headers[key]==='string')result.headers[key]=text(value.headers[key]);return result;};
  const publicSignal=()=>({ua:navigator.userAgent,appVersion:navigator.appVersion,platform:navigator.platform,language:navigator.language,languages:Array.from(navigator.languages||[]),cpu:navigator.hardwareConcurrency??null,memory:navigator.deviceMemory??null,offset:new Date().getTimezoneOffset(),zone:Intl.DateTimeFormat().resolvedOptions().timeZone||''});
  const audit=async message=>{
    auditCancel();const cfg=message.configuration;
    if(!cfg||typeof cfg.id!=='string'||cfg.id.length>128)return;
    const nonce=Array.from(crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16)).join('-');
    const stops=[];let cancelled=false;
    auditCancel=()=>{cancelled=true;stops.forEach(stop=>stop());window.dispatchEvent(new CustomEvent('pocket-audit-cancel',{detail:nonce}));};
    const mainJob=new Promise(resolve=>{
      let done=false;const script=document.createElement('script');
      const finish=value=>{if(done)return;done=true;clearTimeout(timer);window.removeEventListener('pocket-audit-observation',receive);script.setAttribute('data-pocket-audit','{}');if(value.error)window.dispatchEvent(new CustomEvent('pocket-audit-cancel',{detail:nonce}));script.remove();resolve(value);};
      const receive=event=>{if(typeof event.detail!=='string'||event.detail.length>60000)return;try{const value=JSON.parse(event.detail);if(value.nonce===nonce)finish({parent:cleanSignal(value.parent),frame:cleanSignal(value.frame),worker:cleanSignal(value.worker),...(cfg.apiChecks===true?{apiChecks:cleanApiChecks(value.apiChecks),apiContexts:cleanApiContexts(value.apiContexts)}:{}),provenance:value.provenance==='page-main-world'?'page-main-world':'',coverage:{frame:'same-origin-srcdoc',worker:'dedicated-blob',crossOriginFrame:false,sharedWorker:false,serviceWorker:false}});}catch{}};
      const timer=setTimeout(()=>finish({error:'Main-world script unavailable or blocked by CSP'}),4500);
      stops.push(()=>finish({error:'Cancelled'}));window.addEventListener('pocket-audit-observation',receive);
      script.src=browser.runtime.getURL('main-world-audit.js');script.setAttribute('data-pocket-audit',JSON.stringify({nonce,apiChecks:cfg.apiChecks===true}));
      script.onerror=()=>finish({error:'Main-world script blocked or unavailable'});
      (document.documentElement||document).appendChild(script);
    });
    const get=async url=>{
      const control=new AbortController();stops.push(()=>control.abort());const timer=setTimeout(()=>control.abort(),6500);
      try{const response=await fetch(url,{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',signal:control.signal});if(!response.ok)throw Error();if(!response.body||typeof response.body.getReader!=='function')throw Error();const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let bytes=0,body='';try{while(true){const part=await reader.read();if(part.done)break;if(!(part.value instanceof Uint8Array))throw Error();bytes+=part.value.byteLength;if(bytes>12000)throw Error();body+=decoder.decode(part.value,{stream:true});}body+=decoder.decode();return JSON.parse(body);}finally{await reader.cancel().catch(()=>{});reader.releaseLock();}}catch{return {error:'No verifiable response'};}finally{clearTimeout(timer);}
    };
    // Endpoint allowlist is static. Page events cannot request native evaluation or a URL.
    const networkJob=cfg.network===true?Promise.all([get('https://api.ipify.org/?format=json'),get('https://api6.ipify.org/?format=json'),get('https://httpbin.org/headers')]):Promise.resolve([]);
    const identityFailure=reason=>({schema:1,nonce:typeof cfg.requestIdentity?.nonce==='string'?cfg.requestIdentity.nonce.slice(0,128):'',status:'failed',source:'controlled-top-level-document',error:reason});
    const identityJob=cfg.requestIdentity?Promise.resolve().then(()=>cancelled?identityFailure('cancelled'):typeof globalThis.PocketRequestIdentityAudit?.run==='function'?globalThis.PocketRequestIdentityAudit.run(cfg.requestIdentity,stops):identityFailure('request-identity-helper-unavailable')).catch(()=>identityFailure('request-identity-helper-failed')):Promise.resolve(null);
    const [main,network,identity]=await Promise.all([mainJob,networkJob,identityJob]);if(cancelled)return;
    const isolated=publicSignal(),available=main.provenance==='page-main-world'&&main.parent&&typeof main.parent.ua==='string';
    const result={id:cfg.id,parent:available?main.parent:isolated,frame:available?main.frame:{error:'No page-main-world observation'},worker:available?main.worker:{error:'No page-main-world observation'},...(cfg.apiChecks===true?{apiChecks:available?main.apiChecks:missingApiChecks('page-main-world-unavailable'),apiContexts:available?main.apiContexts:missingApiContexts('page-main-world-unavailable')}:{}),...(cfg.requestIdentity?{requestIdentity:identity}:{}),isolated,provenance:available?'page-main-world':'extension-isolated-world-fallback',mainWorld:{observed:available,error:text(main.error),authenticity:'Page-provided public signals may be forged by the page; not independent attestation'},coverage:available?main.coverage:{crossOriginFrame:false,sharedWorker:false,serviceWorker:false},network:cfg.network===true?{ipv4:cleanIp(network[0]),ipv6:cleanIp(network[1]),headers:cleanHeaders(network[2]),provenance:'gecko-content-fetch'}:{}};
    const encoded=JSON.stringify(result);if(encoded.length<=64000)port.postMessage({kind:'auditResult',id:message.id,result:encoded});stops.length=0;auditCancel=()=>{};
  };
  window.PocketWebReply = {postMessage: text => {
    if(location.origin === 'https://chatgpt.com')port.postMessage({kind:'reply', text:String(text)});
  }};
  port.onMessage.addListener(message => {
    if(message.kind==='auditCancel'){auditCancel();return;}
    if(message.kind==='audit'&&Number.isInteger(message.id)){audit(message).catch(()=>port.postMessage({kind:'auditResult',id:message.id,result:'null'}));return;}
    if(message.kind === 'appearance'){
      if(message.protocol!==1||message.documentId!==appearanceDocument||!Number.isInteger(message.version)||message.version<1||typeof message.dark!=='boolean')return;
      const report=value=>port.postMessage(value);
      if(typeof globalThis.PocketAppearance?.synchronize==='function'){
        globalThis.PocketAppearance.synchronize(message,report);
      }else{
        report({kind:'appearanceReceipt',protocol:1,documentId:appearanceDocument,version:message.version,dark:message.dark,stage:'received'});
        report({kind:'appearanceReceipt',protocol:1,documentId:appearanceDocument,version:message.version,dark:message.dark,stage:'observed',attributesApplied:false,storage:'unavailable',colorStatus:'unavailable',reason:'script-unavailable',samples:[]});
      }
      return;
    }
    if(message.kind !== 'evaluate' || !Number.isInteger(message.id))return;
    try {
      const value = (0,eval)(message.code);
      // Match WebView.evaluateJavascript's immediate JSON result, including void.
      const result = value === undefined || value instanceof Promise ? 'null' : JSON.stringify(value);
      port.postMessage({kind:'result', id:message.id, result:result ?? 'null'});
    } catch (_) {port.postMessage({kind:'result', id:message.id, result:'null'});}
  });
  let scaleFrame=0,lastScale=null,lastWidth=null;
  const scale = () => {
    const value=devicePixelRatio*(visualViewport?.scale??1),width=document.documentElement?.clientWidth??0;
    if(value===lastScale&&width===lastWidth)return;
    lastScale=value;lastWidth=width;port.postMessage({kind:'scale',value,width});
  };
  const scheduleScale=()=>{if(!scaleFrame)scaleFrame=requestAnimationFrame(()=>{scaleFrame=0;scale();});};
  visualViewport?.addEventListener('resize',scheduleScale);
  window.addEventListener('resize',scheduleScale);
  const flushScale=()=>{if(scaleFrame){cancelAnimationFrame(scaleFrame);scaleFrame=0;scale();}};
  window.addEventListener('pagehide',flushScale);
  window.addEventListener('pagehide',()=>auditCancel());
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flushScale();});
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')port.postMessage({kind:'appearanceVisible',...appearanceIdentity});});
  document.addEventListener('DOMContentLoaded',scale,{once:true});
  let observedReady=false;
  const observer=new MutationObserver(()=>documentReady());
  const documentReady = () => {
    if(observedReady)return;
    if(document.readyState==='loading'||!document.body)return;
    if(document.body.innerText.trim()||document.querySelector('input,button,textarea,canvas')){
      observedReady=true;observer.disconnect();
      port.postMessage({kind:'documentReady',url:location.href,...appearanceIdentity});
    }
  };
  const observe = () => {if(document.documentElement)observer.observe(document.documentElement,{childList:true,subtree:true});documentReady();};
  observe();
  document.addEventListener('DOMContentLoaded',observe,{once:true});
  document.addEventListener('DOMContentLoaded',documentReady,{once:true});
  window.addEventListener('pageshow',()=>{observedReady=false;documentReady();});
  documentReady();
  port.postMessage({kind:'ready',...appearanceIdentity});
  scale();
})();
