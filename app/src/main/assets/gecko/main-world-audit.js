/* Static page-world observer. No privileged bridge, cookies, chat content or supplied code. */
(() => {
  'use strict';
  const element=document.currentScript;
  let configuration;
  try{configuration=JSON.parse(element?.getAttribute('data-pocket-audit')||'{}');}catch{return;}
  if(typeof configuration.nonce!=='string'||configuration.nonce.length>128)return;
  const nonce=configuration.nonce;
  const apiRequested=configuration.apiChecks===true;
  const clean=[];let cancelled=false;
  const bounded=value=>typeof value==='string'?value.slice(0,2048):value;
  async function signal(){
    const n=navigator;
    const value={ua:bounded(n.userAgent),appVersion:bounded(n.appVersion),platform:bounded(n.platform),language:bounded(n.language),languages:Array.from(n.languages||[]).slice(0,8).map(bounded),cpu:n.hardwareConcurrency??null,memory:n.deviceMemory??null,offset:new Date().getTimezoneOffset(),zone:bounded(Intl.DateTimeFormat().resolvedOptions().timeZone||'')};
    if(typeof screen!=='undefined')value.screen={width:screen.width,height:screen.height,availWidth:screen.availWidth,availHeight:screen.availHeight,depth:screen.colorDepth};
    if(typeof window!=='undefined')value.viewport={width:innerWidth,height:innerHeight,pixelRatio:devicePixelRatio,touch:n.maxTouchPoints??0};
    let gl;try{const canvas=typeof document!=='undefined'?document.createElement('canvas'):new OffscreenCanvas(16,16);canvas.width=canvas.height=16;gl=canvas.getContext('webgl');const ext=gl?.getExtension('WEBGL_debug_renderer_info');value.renderer=gl?ext?String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)).slice(0,2048):'restricted':'unavailable';}catch{value.renderer='unavailable';}finally{try{gl?.getExtension('WEBGL_lose_context')?.loseContext();}catch{}}
    try{const RTC=globalThis.RTCPeerConnection;if(!RTC)value.rtc='absent';else{const peer=new RTC({iceServers:[]});peer.close();value.rtc='available';}}catch(error){value.rtc=error.name==='NotAllowedError'?'restricted':'unavailable';}
    return value;
  }
  // These finite probes run only after an explicit native API-check request.
  // Results describe operations, not privacy effectiveness or an installed font list.
  // The elapsed guard is cooperative: JS cannot preempt one native browser call.
  const apiChecks=async(source='page-main-world')=>{
    const workerContext=source==='dedicated-worker';
    const began=performance.now(),limits={canvasPixels:4096,audioFrames:workerContext?0:2048,fontCandidates:workerContext?0:5,totalBudgetMs:1200};
    const deadline=began+limits.totalBudgetMs,probes={},names=['canvas','audio','fonts','webgl'];
    const cleanups=new Set();let alive=true;
    const release=()=>{if(!alive)return;alive=false;for(const run of cleanups){try{run();}catch{}}cleanups.clear();};
    clean.push(release);
    const remaining=()=>Math.max(0,deadline-performance.now());
    const active=()=>alive&&!cancelled&&remaining()>0;
    const uncovered=reason=>({state:'uncovered',reason});
    const failure=error=>({state:/^(SecurityError|NotAllowedError|NS_ERROR_DOM_SECURITY_ERR)$/.test(String(error?.name))?'restricted':'failed',reason:String(error?.name||'operation-failed').slice(0,96)});
    const hash=async bytes=>{
      if(!active()||!globalThis.crypto?.subtle?.digest)return '';
      const digest=await crypto.subtle.digest('SHA-256',bytes);
      return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
    };
    const boundedWait=(promise,ms)=>new Promise((resolve,reject)=>{
      let done=false;
      const finish=(value,error)=>{if(done)return;done=true;clearTimeout(timer);cleanups.delete(stop);error?reject(error):resolve(value);};
      const stop=()=>finish(uncovered('cancelled'));
      const timer=setTimeout(()=>finish(uncovered('time-budget-exhausted')),Math.max(1,Math.min(ms,remaining())));
      cleanups.add(stop);Promise.resolve(promise).then(value=>finish(value),error=>finish(null,error));
    });
    const hashed=async(value,bytes)=>{
      try{const digest=await hash(bytes);if(digest){value.hash=digest;value.hashAlgorithm='sha256';}else value.hashUnavailable=true;}catch{value.hashUnavailable=true;}
      return value;
    };
    const makeSurface=(width,height)=>{
      if(workerContext)return typeof OffscreenCanvas==='function'?new OffscreenCanvas(width,height):null;
      const value=document.createElement('canvas');value.width=width;value.height=height;return value;
    };
    const canvas=async()=>{
      const imageSurface=makeSurface(128,32);if(!imageSurface)return uncovered('offscreen-canvas-unavailable');
      const surface=imageSurface;
      try{
        const context=surface.getContext('2d',{willReadFrequently:true});if(!context)return uncovered('canvas-2d-unavailable');
        context.fillStyle='#2673a8';context.fillRect(0,0,128,32);context.fillStyle='#f0e1c2';context.font='16px sans-serif';context.fillText('PocketChat Ω 中文',2,22);
        const image=context.getImageData(0,0,128,32);if(image.data.length!==16384)throw new Error('unexpected-readback-length');
        return hashed({state:'available',reason:'draw-and-pixel-readback-completed',pixels:4096},image.data);
      }finally{surface.width=surface.height=0;}
    };
    const audio=async()=>{
      if(workerContext)return uncovered('not-applicable-in-worker');
      const Offline=globalThis.OfflineAudioContext||globalThis.webkitOfflineAudioContext;
      if(typeof Offline!=='function')return uncovered('offline-audio-unavailable');
      const context=new Offline(1,2048,44100);let oscillator,compressor,retired=false;
      const retire=()=>{if(retired)return;retired=true;try{oscillator?.stop();}catch{}try{oscillator?.disconnect();}catch{}try{compressor?.disconnect();}catch{}try{const closed=context.close?.();closed?.catch?.(()=>{});}catch{}};
      cleanups.add(retire);
      try{
        oscillator=context.createOscillator();compressor=context.createDynamicsCompressor();
        oscillator.type='triangle';oscillator.frequency.value=1000;compressor.threshold.value=-50;compressor.knee.value=40;compressor.ratio.value=12;compressor.attack.value=0;compressor.release.value=.25;
        oscillator.connect(compressor);compressor.connect(context.destination);oscillator.start(0);
        const rendered=await boundedWait(context.startRendering(),400);
        if(!active())return uncovered(cancelled?'cancelled':'time-budget-exhausted');
        if(rendered?.state==='uncovered')return rendered;
        const channel=rendered.getChannelData(0);if(channel.length!==2048)throw new Error('unexpected-audio-frame-count');
        const quantized=new Int32Array(2048);let peak=0;
        for(let i=0;i<2048;i++){const sample=channel[i];if(!Number.isFinite(sample))throw new Error('non-finite-audio-sample');peak=Math.max(peak,Math.abs(sample));quantized[i]=Math.round(Math.max(-1,Math.min(1,sample))*1000000);}
        return hashed({state:'available',reason:'offline-render-completed-no-speaker-output',frames:2048,sampleRate:44100,peak:Math.round(peak*1000000)/1000000},new Uint8Array(quantized.buffer));
      }finally{retire();cleanups.delete(retire);}
    };
    const fonts=async()=>{
      if(workerContext)return uncovered('not-applicable-in-worker');
      const surface=document.createElement('canvas');surface.width=surface.height=16;
      try{
        const context=surface.getContext('2d');if(!context)return uncovered('font-measurement-unavailable');
        const candidates=['Arial','Times New Roman','Courier New','Noto Sans','Noto Sans CJK SC'],text='mmmmWWW0123',samples=[];
        for(const name of candidates){
          if(!active())return uncovered(cancelled?'cancelled':'time-budget-exhausted');
          const widths=[];for(const fallback of ['monospace','sans-serif']){context.font='16px "'+name+'",'+fallback;const width=context.measureText(text).width;if(!Number.isFinite(width))throw new Error('non-finite-font-width');widths.push(Math.round(width*1000)/1000);}
          let faceCheck=null;try{if(typeof document.fonts?.check==='function')faceCheck=document.fonts.check('16px "'+name+'"',text);}catch{}
          samples.push({name,faceCheck,monospaceWidth:widths[0],sansSerifWidth:widths[1]});
        }
        const faceChecks=samples.every(sample=>typeof sample.faceCheck==='boolean');
        return hashed({state:faceChecks?'available':'restricted',reason:faceChecks?'limited-font-face-check-and-widths-not-installation-proof':'font-face-api-unavailable-widths-only',candidateCount:5,samples},new TextEncoder().encode(JSON.stringify(samples)));
      }finally{surface.width=surface.height=0;}
    };
    const webgl=async()=>{
      const imageSurface=makeSurface(16,16);if(!imageSurface)return uncovered('offscreen-canvas-unavailable');
      const surface=imageSurface,context=surface.getContext('webgl');if(!context)return uncovered('webgl-context-unavailable');
      const retire=()=>{try{context.getExtension('WEBGL_lose_context')?.loseContext();}catch{}surface.width=surface.height=0;};cleanups.add(retire);
      try{
        const debug=context.getExtension('WEBGL_debug_renderer_info'),extensions=context.getSupportedExtensions()||[];
        const value={state:debug?'available':'restricted',reason:debug?'bounded-capabilities-read':'unmasked-renderer-extension-unavailable',version:String(context.getParameter(context.VERSION)).slice(0,256),shadingLanguageVersion:String(context.getParameter(context.SHADING_LANGUAGE_VERSION)).slice(0,256),vendor:String(context.getParameter(context.VENDOR)).slice(0,256),renderer:String(context.getParameter(context.RENDERER)).slice(0,256),maxTextureSize:context.getParameter(context.MAX_TEXTURE_SIZE),maxRenderbufferSize:context.getParameter(context.MAX_RENDERBUFFER_SIZE),maxVertexAttribs:context.getParameter(context.MAX_VERTEX_ATTRIBS),extensionCount:extensions.length,extensions:['ANGLE_instanced_arrays','EXT_texture_filter_anisotropic','OES_element_index_uint','OES_standard_derivatives','OES_texture_float','WEBGL_debug_renderer_info','WEBGL_lose_context'].filter(name=>extensions.includes(name))};
        if(debug)value.unmaskedRenderer=String(context.getParameter(debug.UNMASKED_RENDERER_WEBGL)).slice(0,256);
        if(workerContext){
          context.clearColor(.125,.25,.5,1);context.clear(context.COLOR_BUFFER_BIT);
          const pixels=new Uint8Array(1024);context.readPixels(0,0,16,16,context.RGBA,context.UNSIGNED_BYTE,pixels);
          if(context.getError()!==context.NO_ERROR)throw new Error('webgl-readback-failed');
          value.readbackPixels=256;value.readbackBytes=1024;
          const readbackHash=await hash(pixels);if(readbackHash){value.readbackHash=readbackHash;value.readbackHashAlgorithm='sha256';}else value.readbackHashUnavailable=true;
        }
        return hashed(value,new TextEncoder().encode(JSON.stringify(value)));
      }finally{retire();cleanups.delete(retire);}
    };
    const jobs={canvas,audio,fonts,webgl};
    try{
      for(const name of names){
        await new Promise(resolve=>setTimeout(resolve,0));
        if(!active()){probes[name]=uncovered(cancelled?'cancelled':'time-budget-exhausted');continue;}
        try{probes[name]=await boundedWait(jobs[name](),Math.min(500,remaining()));}catch(error){probes[name]=failure(error);}
      }
      return {schema:1,requested:true,source,probeVersion:1,status:names.every(name=>probes[name].state!=='uncovered')?'completed':'partial',durationMs:Math.round((performance.now()-began)*1000)/1000,limits,probes,protectionVerified:false,coverage:source==='page-main-world'?'current-page-main-world-only; frame and Worker API operations not sampled':source+'-only; independently sampled, not hash-equality attestation'};
    }finally{release();}
  };
  const frameJob=()=>new Promise(resolve=>{
    const frame=document.createElement('iframe');frame.hidden=true;let done=false;
    const finish=value=>{if(done)return;done=true;clearTimeout(timer);window.removeEventListener('message',receive);frame.remove();resolve(value);};
    const receive=event=>{if(event.source===frame.contentWindow&&event.origin===location.origin&&event.data?.pocketAuditFrame===nonce)finish(event.data.value);};
    const timer=setTimeout(()=>finish({error:'Frame unavailable or blocked by CSP'}),2200);
    clean.push(()=>finish({error:'Cancelled'}));window.addEventListener('message',receive);
    const helpers='const bounded=value=>typeof value==="string"?value.slice(0,2048):value;const clean=[];let cancelled=false;addEventListener("pagehide",()=>{cancelled=true;clean.forEach(stop=>stop());},{once:true});';
    const operations=apiRequested?'('+apiChecks.toString()+')("same-origin-srcdoc")':'Promise.resolve(null)';
    frame.srcdoc='<script>'+helpers+'Promise.all([('+signal.toString()+')(),'+operations+']).then(([value,apiChecks])=>parent.postMessage({pocketAuditFrame:'+JSON.stringify(nonce)+',value:{...value,...(apiChecks?{apiChecks}:{})}},"*"));<\/script>';
    (document.body||document.documentElement).appendChild(frame);
  });
  const workerJob=()=>new Promise(resolve=>{
    let worker,url,done=false;
    const finish=value=>{if(done)return;done=true;clearTimeout(timer);worker?.terminate();if(url)URL.revokeObjectURL(url);resolve(value);};
    const timer=setTimeout(()=>finish({error:'Dedicated Worker unavailable or blocked by CSP'}),2600);clean.push(()=>finish({error:'Cancelled'}));
    try{const operations=apiRequested?'('+apiChecks.toString()+')("dedicated-worker")':'Promise.resolve(null)';
      url=URL.createObjectURL(new Blob(['const bounded=value=>typeof value==="string"?value.slice(0,2048):value;const clean=[];let cancelled=false;Promise.all([('+signal.toString()+')(),'+operations+']).then(([value,apiChecks])=>postMessage({...value,...(apiChecks?{apiChecks}:{})}));'],{type:'application/javascript'}));worker=new Worker(url);worker.onmessage=event=>finish(event.data);worker.onerror=()=>finish({error:'Dedicated Worker unavailable'});}catch{finish({error:'Dedicated Worker unavailable'});}
  });
  const cancel=event=>{if(event.detail===nonce){cancelled=true;clean.forEach(stop=>stop());window.removeEventListener('pocket-audit-cancel',cancel);}};
  const leave=()=>cancel({detail:nonce});
  window.addEventListener('pocket-audit-cancel',cancel);
  window.addEventListener('pagehide',leave,{once:true});
  Promise.all([signal(),frameJob(),workerJob(),apiRequested?apiChecks():Promise.resolve(null)]).then(([parent,frame,worker,apis])=>{
    window.removeEventListener('pocket-audit-cancel',cancel);
    window.removeEventListener('pagehide',leave);
    if(cancelled)return;
    const frameValue=frame&&typeof frame==='object'&&!Array.isArray(frame)?frame:{error:'Frame observation unavailable'},workerValue=worker&&typeof worker==='object'&&!Array.isArray(worker)?worker:{error:'Dedicated Worker observation unavailable'};
    const {apiChecks:frameApis,...frameSignal}=frameValue,{apiChecks:workerApis,...workerSignal}=workerValue;
    const result=JSON.stringify({nonce,parent,frame:frameSignal,worker:workerSignal,...(apis?{apiChecks:apis,apiContexts:{schema:1,requested:true,frame:frameApis||null,worker:workerApis||null}}:{}),provenance:'page-main-world',coverage:{frame:'same-origin-srcdoc',worker:'dedicated-blob',crossOriginFrame:false,sharedWorker:false,serviceWorker:false}});
    if(result.length<=60000)window.dispatchEvent(new CustomEvent('pocket-audit-observation',{detail:result}));
  }).catch(()=>{});
})();
