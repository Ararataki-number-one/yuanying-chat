/* Static page-world observer. No privileged bridge, cookies, chat content or supplied code. */
(() => {
  'use strict';
  const element=document.currentScript;
  let configuration;
  try{configuration=JSON.parse(element?.getAttribute('data-pocket-audit')||'{}');}catch{return;}
  if(typeof configuration.nonce!=='string'||configuration.nonce.length>128)return;
  const nonce=configuration.nonce;
  const clean=[];let cancelled=false;
  const bounded=value=>typeof value==='string'?value.slice(0,2048):value;
  async function signal(){
    const n=navigator;
    const value={ua:bounded(n.userAgent),appVersion:bounded(n.appVersion),platform:bounded(n.platform),language:bounded(n.language),languages:Array.from(n.languages||[]).slice(0,8).map(bounded),cpu:n.hardwareConcurrency??null,memory:n.deviceMemory??null,offset:new Date().getTimezoneOffset(),zone:bounded(Intl.DateTimeFormat().resolvedOptions().timeZone||'')};
    if(typeof screen!=='undefined')value.screen={width:screen.width,height:screen.height,availWidth:screen.availWidth,availHeight:screen.availHeight,depth:screen.colorDepth};
    if(typeof window!=='undefined')value.viewport={width:innerWidth,height:innerHeight,pixelRatio:devicePixelRatio,touch:n.maxTouchPoints??0};
    try{const canvas=typeof document!=='undefined'?document.createElement('canvas'):new OffscreenCanvas(16,16);canvas.width=canvas.height=16;const gl=canvas.getContext('webgl');const ext=gl?.getExtension('WEBGL_debug_renderer_info');value.renderer=gl?ext?String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)).slice(0,2048):'restricted':'unavailable';}catch{value.renderer='unavailable';}
    try{const RTC=globalThis.RTCPeerConnection;if(!RTC)value.rtc='absent';else{const peer=new RTC({iceServers:[]});peer.close();value.rtc='available';}}catch(error){value.rtc=error.name==='NotAllowedError'?'restricted':'unavailable';}
    return value;
  }
  const frameJob=()=>new Promise(resolve=>{
    const frame=document.createElement('iframe');frame.hidden=true;let done=false;
    const finish=value=>{if(done)return;done=true;clearTimeout(timer);window.removeEventListener('message',receive);frame.remove();resolve(value);};
    const receive=event=>{if(event.source===frame.contentWindow&&event.data?.pocketAuditFrame===nonce)finish(event.data.value);};
    const timer=setTimeout(()=>finish({error:'Frame unavailable or blocked by CSP'}),2200);
    clean.push(()=>finish({error:'Cancelled'}));window.addEventListener('message',receive);
    frame.srcdoc='<script>('+signal.toString()+')().then(value=>parent.postMessage({pocketAuditFrame:'+JSON.stringify(nonce)+',value},"*"));<\/script>';
    // signal is self-contained in a frame/worker: bounded helper is inlined below.
    frame.srcdoc=frame.srcdoc.replace('('+signal.toString()+')','(function(){const bounded=value=>typeof value==="string"?value.slice(0,2048):value;return ('+signal.toString()+')();})');
    (document.body||document.documentElement).appendChild(frame);
  });
  const workerJob=()=>new Promise(resolve=>{
    let worker,url,done=false;
    const finish=value=>{if(done)return;done=true;clearTimeout(timer);worker?.terminate();if(url)URL.revokeObjectURL(url);resolve(value);};
    const timer=setTimeout(()=>finish({error:'Dedicated Worker unavailable or blocked by CSP'}),2600);clean.push(()=>finish({error:'Cancelled'}));
    try{url=URL.createObjectURL(new Blob(['const bounded=value=>typeof value==="string"?value.slice(0,2048):value;('+signal.toString()+')().then(value=>postMessage(value));'],{type:'application/javascript'}));worker=new Worker(url);worker.onmessage=event=>finish(event.data);worker.onerror=()=>finish({error:'Dedicated Worker unavailable'});}catch{finish({error:'Dedicated Worker unavailable'});}
  });
  const cancel=event=>{if(event.detail===nonce){cancelled=true;clean.forEach(stop=>stop());window.removeEventListener('pocket-audit-cancel',cancel);}};
  window.addEventListener('pocket-audit-cancel',cancel);
  Promise.all([signal(),frameJob(),workerJob()]).then(([parent,frame,worker])=>{
    window.removeEventListener('pocket-audit-cancel',cancel);
    if(cancelled)return;
    const result=JSON.stringify({nonce,parent,frame,worker,provenance:'page-main-world',coverage:{frame:'same-origin-srcdoc',worker:'dedicated-blob',crossOriginFrame:false,sharedWorker:false,serviceWorker:false}});
    if(result.length<=60000)window.dispatchEvent(new CustomEvent('pocket-audit-observation',{detail:result}));
  }).catch(()=>{});
})();
