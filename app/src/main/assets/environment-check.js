/* Runs only in the app's isolated diagnostic document. No account page or cookies. */
(() => {
  'use strict';
  window.__pocketAuditStart = async cfg => {
    async function signal() {
      const n=navigator, result={ua:n.userAgent,appVersion:n.appVersion,platform:n.platform,language:n.language,languages:Array.from(n.languages||[]),cpu:n.hardwareConcurrency??null,memory:n.deviceMemory??null,offset:new Date().getTimezoneOffset(),zone:Intl.DateTimeFormat().resolvedOptions().timeZone||'',early:typeof window!=='undefined'&&!!window.__pocketAuditFirst,shield:typeof window!=='undefined'?window.__pocketPrivacy||null:null};
      if(n.userAgentData){result.hints={brands:n.userAgentData.brands,mobile:n.userAgentData.mobile,platform:n.userAgentData.platform};try{result.hints.high=await n.userAgentData.getHighEntropyValues(['architecture','bitness','model','platformVersion','fullVersionList']);}catch{result.hints.error='unavailable';}}
      try{let canvas=typeof document!=='undefined'?document.createElement('canvas'):new OffscreenCanvas(16,16);canvas.width=canvas.height=16;const gl=canvas.getContext('webgl');if(gl){const ext=gl.getExtension('WEBGL_debug_renderer_info');result.renderer=ext?String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)):'restricted';}else result.renderer='unavailable';}catch{result.renderer='unavailable';}
      try{const RTC=globalThis.RTCPeerConnection||globalThis.webkitRTCPeerConnection;if(!RTC)result.rtc='absent';else {const peer=new RTC({iceServers:[]});peer.close();result.rtc='available';}}catch(e){result.rtc=e.name==='NotAllowedError'?'restricted':'unavailable';}
      return result;
    }
    async function get(url){const stop=new AbortController(),timer=setTimeout(()=>stop.abort(),6500);try{const r=await fetch(url,{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',signal:stop.signal});if(!r.ok)throw Error('HTTP '+r.status);const text=await r.text();if(text.length>12000)throw Error('response limit');return JSON.parse(text);}catch{return {error:'No verifiable response'};}finally{clearTimeout(timer);}}
    const parent=await signal(), nonce=cfg.id;
    const frameJob=new Promise(resolve=>{const frame=document.createElement('iframe');frame.style.display='none';let done=false;const finish=value=>{if(done)return;done=true;clearTimeout(timer);window.removeEventListener('message',receive);frame.remove();resolve(value);};const receive=e=>{if(e.source===frame.contentWindow&&e.data?.id===nonce)finish(e.data.value);};const timer=setTimeout(()=>finish({error:'Frame unavailable'}),2500);window.addEventListener('message',receive);frame.srcdoc='<script>window.__pocketAuditFirst=window.__pocketPrivacy||null;('+signal.toString()+')().then(value=>parent.postMessage({id:'+JSON.stringify(nonce)+',value},"*"));<\/script>';document.body.appendChild(frame);});
    const workerJob=new Promise(resolve=>{let worker,url,done=false;const finish=value=>{if(done)return;done=true;clearTimeout(timer);worker?.terminate();if(url)URL.revokeObjectURL(url);resolve(value);};const timer=setTimeout(()=>finish({error:'Worker unavailable'}),9000);try{url=URL.createObjectURL(new Blob(['('+signal.toString()+')().then(async value=>{if('+JSON.stringify(cfg.network)+')value.ip=await ('+get.toString()+')('+JSON.stringify(cfg.ipv4)+');postMessage(value);});'],{type:'application/javascript'}));worker=new Worker(url);worker.onmessage=e=>finish(e.data);worker.onerror=()=>finish({error:'Worker unavailable'});}catch{finish({error:'Worker unavailable'});}});
    const netJob=cfg.network?Promise.all([get(cfg.ipv4),get(cfg.ipv6),get(cfg.headers)]):Promise.resolve([]);
    const [frame,worker,network]=await Promise.all([frameJob,workerJob,netJob]);
    window.__pocketAuditResult={id:nonce,parent,frame,worker,network:cfg.network?{ipv4:network[0],ipv6:network[1],headers:network[2]}:{}};
  };
})();
