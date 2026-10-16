/* Trusted host bridge in the extension's isolated world; never exposed to page scripts. */
(() => {
  'use strict';
  const port = browser.runtime.connectNative('pocketpage');
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
      const finish=value=>{if(done)return;done=true;clearTimeout(timer);window.removeEventListener('pocket-audit-observation',receive);script.remove();resolve(value);};
      const receive=event=>{if(typeof event.detail!=='string'||event.detail.length>60000)return;try{const value=JSON.parse(event.detail);if(value.nonce===nonce)finish({parent:cleanSignal(value.parent),frame:cleanSignal(value.frame),worker:cleanSignal(value.worker),provenance:value.provenance==='page-main-world'?'page-main-world':'',coverage:{frame:'same-origin-srcdoc',worker:'dedicated-blob',crossOriginFrame:false,sharedWorker:false,serviceWorker:false}});}catch{}};
      const timer=setTimeout(()=>finish({error:'Main-world script unavailable or blocked by CSP'}),4500);
      stops.push(()=>finish({error:'Cancelled'}));window.addEventListener('pocket-audit-observation',receive);
      script.src=browser.runtime.getURL('main-world-audit.js');script.setAttribute('data-pocket-audit',JSON.stringify({nonce}));
      script.onerror=()=>finish({error:'Main-world script blocked or unavailable'});
      (document.documentElement||document).appendChild(script);
    });
    const get=async url=>{
      const control=new AbortController();stops.push(()=>control.abort());const timer=setTimeout(()=>control.abort(),6500);
      try{const response=await fetch(url,{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',signal:control.signal});if(!response.ok)throw Error();if(!response.body||typeof response.body.getReader!=='function')throw Error();const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let bytes=0,body='';try{while(true){const part=await reader.read();if(part.done)break;if(!(part.value instanceof Uint8Array))throw Error();bytes+=part.value.byteLength;if(bytes>12000)throw Error();body+=decoder.decode(part.value,{stream:true});}body+=decoder.decode();return JSON.parse(body);}finally{await reader.cancel().catch(()=>{});reader.releaseLock();}}catch{return {error:'No verifiable response'};}finally{clearTimeout(timer);}
    };
    // Endpoint allowlist is static. Page events cannot request native evaluation or a URL.
    const networkJob=cfg.network===true?Promise.all([get('https://api.ipify.org/?format=json'),get('https://api6.ipify.org/?format=json'),get('https://httpbin.org/headers')]):Promise.resolve([]);
    const [main,network]=await Promise.all([mainJob,networkJob]);if(cancelled)return;
    const isolated=publicSignal(),available=main.provenance==='page-main-world'&&main.parent&&typeof main.parent.ua==='string';
    const result={id:cfg.id,parent:available?main.parent:isolated,frame:available?main.frame:{error:'No page-main-world observation'},worker:available?main.worker:{error:'No page-main-world observation'},isolated,provenance:available?'page-main-world':'extension-isolated-world-fallback',mainWorld:{observed:available,error:text(main.error),authenticity:'Page-provided public signals may be forged by the page; not independent attestation'},coverage:available?main.coverage:{crossOriginFrame:false,sharedWorker:false,serviceWorker:false},network:cfg.network===true?{ipv4:cleanIp(network[0]),ipv6:cleanIp(network[1]),headers:cleanHeaders(network[2]),provenance:'gecko-content-fetch'}:{}};
    const encoded=JSON.stringify(result);if(encoded.length<=64000)port.postMessage({kind:'auditResult',id:message.id,result:encoded});stops.length=0;auditCancel=()=>{};
  };
  window.PocketWebReply = {postMessage: text => {
    if(location.origin === 'https://chatgpt.com')port.postMessage({kind:'reply', text:String(text)});
  }};
  port.onMessage.addListener(message => {
    if(message.kind==='auditCancel'){auditCancel();return;}
    if(message.kind==='audit'&&Number.isInteger(message.id)){audit(message).catch(()=>port.postMessage({kind:'auditResult',id:message.id,result:'null'}));return;}
    if(message.kind === 'appearance'){globalThis.PocketAppearance?.apply(message.dark);return;}
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
  document.addEventListener('DOMContentLoaded',scale,{once:true});
  let observedReady=false;
  const observer=new MutationObserver(()=>documentReady());
  const documentReady = () => {
    if(observedReady)return;
    if(document.readyState==='loading'||!document.body)return;
    if(document.body.innerText.trim()||document.querySelector('input,button,textarea,canvas')){
      observedReady=true;observer.disconnect();
      port.postMessage({kind:'documentReady',url:location.href});
    }
  };
  const observe = () => {if(document.documentElement)observer.observe(document.documentElement,{childList:true,subtree:true});documentReady();};
  observe();
  document.addEventListener('DOMContentLoaded',observe,{once:true});
  document.addEventListener('DOMContentLoaded',documentReady,{once:true});
  window.addEventListener('pageshow',()=>{observedReady=false;documentReady();});
  documentReady();
  port.postMessage({kind:'ready'});
  scale();
})();
