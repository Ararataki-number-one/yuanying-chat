'use strict';

// Fixed code for the explicitly selected controlled cross-origin document.
// The server serializes this function; it accepts no page-supplied code or URL.
async function controlledFrameGraphics() {
  'use strict';
  const began=performance.now(),deadline=began+1200;
  const limits={canvasPixels:4096,audioFrames:0,fontCandidates:0,totalBudgetMs:1200};
  const probes={audio:{state:'uncovered',reason:'not-covered-by-controlled-frame-graphics'},fonts:{state:'uncovered',reason:'not-covered-by-controlled-frame-graphics'}};
  let live=true;
  const cleanup=new Set();
  const retire=()=>{if(!live)return;live=false;for(const run of cleanup){try{run();}catch{}}cleanup.clear();};
  addEventListener('pagehide',retire,{once:true});
  const active=()=>live&&performance.now()<deadline;
  const uncovered=reason=>({state:'uncovered',reason});
  const failure=error=>({state:/^(SecurityError|NotAllowedError|NS_ERROR_DOM_SECURITY_ERR)$/.test(String(error?.name))?'restricted':'failed',reason:String(error?.name||'operation-failed').slice(0,96)});
  const surface=(width,height)=>{const value=document.createElement('canvas');value.width=width;value.height=height;return value;};
  const hash=async bytes=>{
    if(!active()||!globalThis.crypto?.subtle?.digest)return '';
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
  };
  const hashed=async(value,bytes)=>{try{const digest=await hash(bytes);if(digest){value.hash=digest;value.hashAlgorithm='sha256';}else value.hashUnavailable=true;}catch{value.hashUnavailable=true;}return value;};
  const bounded=promise=>new Promise(resolve=>{
    let done=false;
    const finish=value=>{if(done)return;done=true;clearTimeout(timer);cleanup.delete(stop);resolve(value);};
    const stop=()=>finish(uncovered('cancelled'));
    const timer=setTimeout(()=>finish(uncovered('time-budget-exhausted')),Math.max(1,Math.min(500,deadline-performance.now())));
    cleanup.add(stop);Promise.resolve(promise).then(finish,error=>finish(failure(error)));
  });
  const canvas=async()=>{
    const value=surface(128,32);const clear=()=>{value.width=value.height=0;};cleanup.add(clear);
    try{
      const context=value.getContext('2d',{willReadFrequently:true});if(!context)return uncovered('canvas-2d-unavailable');
      context.fillStyle='#2673a8';context.fillRect(0,0,128,32);context.fillStyle='#f0e1c2';context.font='16px sans-serif';context.fillText('PocketChat Ω 中文',2,22);
      const image=context.getImageData(0,0,128,32);if(image.data.length!==16384)throw new Error('unexpected-readback-length');
      return hashed({state:'available',reason:'draw-and-pixel-readback-completed',pixels:4096},image.data);
    }finally{clear();cleanup.delete(clear);}
  };
  const webgl=async()=>{
    const value=surface(16,16),context=value.getContext('webgl');if(!context)return uncovered('webgl-context-unavailable');
    const clear=()=>{try{context.getExtension('WEBGL_lose_context')?.loseContext();}catch{}value.width=value.height=0;};cleanup.add(clear);
    try{
      const debug=context.getExtension('WEBGL_debug_renderer_info'),extensions=context.getSupportedExtensions()||[];
      const result={state:debug?'available':'restricted',reason:debug?'bounded-capabilities-and-readback':'unmasked-renderer-extension-unavailable',version:String(context.getParameter(context.VERSION)).slice(0,256),shadingLanguageVersion:String(context.getParameter(context.SHADING_LANGUAGE_VERSION)).slice(0,256),vendor:String(context.getParameter(context.VENDOR)).slice(0,256),renderer:String(context.getParameter(context.RENDERER)).slice(0,256),maxTextureSize:context.getParameter(context.MAX_TEXTURE_SIZE),maxRenderbufferSize:context.getParameter(context.MAX_RENDERBUFFER_SIZE),maxVertexAttribs:context.getParameter(context.MAX_VERTEX_ATTRIBS),extensionCount:extensions.length,extensions:['ANGLE_instanced_arrays','EXT_texture_filter_anisotropic','OES_element_index_uint','OES_standard_derivatives','OES_texture_float','WEBGL_debug_renderer_info','WEBGL_lose_context'].filter(name=>extensions.includes(name))};
      if(debug)result.unmaskedRenderer=String(context.getParameter(debug.UNMASKED_RENDERER_WEBGL)).slice(0,256);
      context.clearColor(.125,.25,.5,1);context.clear(context.COLOR_BUFFER_BIT);
      const pixels=new Uint8Array(1024);context.readPixels(0,0,16,16,context.RGBA,context.UNSIGNED_BYTE,pixels);if(context.getError()!==context.NO_ERROR)throw new Error('webgl-readback-failed');
      result.readbackPixels=256;result.readbackBytes=1024;
      const readbackHash=await hash(pixels);if(readbackHash){result.readbackHash=readbackHash;result.readbackHashAlgorithm='sha256';}else result.readbackHashUnavailable=true;
      return hashed(result,new TextEncoder().encode(JSON.stringify(result)));
    }finally{clear();cleanup.delete(clear);}
  };
  try{
    for(const [name,run] of [['canvas',canvas],['webgl',webgl]]){
      await new Promise(resolve=>setTimeout(resolve,0));
      if(!active()){probes[name]=uncovered(live?'time-budget-exhausted':'cancelled');continue;}
      try{probes[name]=await bounded(run());}catch(error){probes[name]=failure(error);}
    }
    return {schema:1,requested:true,source:'controlled-cross-origin-iframe',probeVersion:1,status:['canvas','webgl'].every(name=>probes[name].state!=='uncovered')?'completed':'partial',durationMs:Math.round((performance.now()-began)*1000)/1000,limits,probes,protectionVerified:false,coverage:'controlled-cross-origin-iframe graphics only; independently sampled, not hash-equality attestation'};
  }finally{retire();removeEventListener('pagehide',retire);}
}

module.exports={controlledFrameGraphics};
