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
  function run(configuration,stops) {
    const nonce=configuration?.nonce;
    const failed=reason=>({schema:1,nonce:typeof nonce==='string'?nonce:'',status:'failed',source:'controlled-top-level-document',error:reason});
    if(typeof nonce!=='string'||!/^[0-9a-f]{32}$/.test(nonce))return Promise.resolve(failed('invalid-nonce'));
    let base,target;
    try {
      base=new URL(configuration.endpoint);target=new URL('document?nonce='+nonce,base);
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
        if(value.status==='failed'){finish(failed('controlled-page-or-worker-unavailable'));return;}
        if(value.status!=='complete')return;
        const document=signal(value.document),worker=signal(value.worker);
        if(!document||!worker){finish(failed('incomplete-javascript-observation'));return;}
        finish({schema:1,nonce,status:'complete',source:'controlled-top-level-document',document,worker});
      };
      const timer=setTimeout(()=>finish(failed('controlled-page-observation-timeout')),6000);
      if(Array.isArray(stops))stops.push(()=>finish(failed('cancelled')));
      window.addEventListener('message',receive);
      window.postMessage({pocketRequestIdentityCollect:nonce},base.origin);
    });
  }
  globalThis.PocketRequestIdentityAudit=Object.freeze({run});
})();
