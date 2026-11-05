/* Real request-header alignment. This never changes a website JavaScript API. */
(() => {
  'use strict';
  const CANCEL=Object.freeze({cancel:true});
  const DEADLINE_MS=5000;
  let installed=false,attempted=false,owner=null,serial=0,revision=null,ipBootstrap=null;
  const pending=new Set();
  const changed=()=>{serial++;for(const cancel of Array.from(pending))cancel();};
  const ownOrigin=()=>{
    try{
      const url=new URL(browser.runtime.getURL(''));
      if(url.protocol!=='moz-extension:'||!url.hostname||url.username||url.password)return null;
      // Custom-scheme URL.origin can be "null"; comparing it would treat every
      // extension as the same owner. The browser-supplied authority is explicit.
      return url.protocol+'//'+url.host;
    }catch(_){return null;}
  };
  const extensionInitiated=details=>{
    const own=ownOrigin();if(!own)return false;
    let observed=false;
    for(const key of ['originUrl','documentUrl']){
      const value=details[key];if(value===undefined||value===null||value==='')continue;
      if(typeof value!=='string')return false;
      try{
        const url=new URL(value);
        if(url.username||url.password||url.protocol+'//'+url.host!==own)return false;
        observed=true;
      }catch(_){return false;}
    }
    return observed;
  };
  const current=(port,epoch)=>owner===port&&serial===epoch&&installed;
  const headers=(details,sanitized)=>{
    if(!sanitized||typeof sanitized!=='object'||Array.isArray(sanitized)||sanitized.cancel===true)return null;
    const values=Object.prototype.hasOwnProperty.call(sanitized,'requestHeaders')?sanitized.requestHeaders:details.requestHeaders??[];
    if(!Array.isArray(values)||values.some(value=>!value||typeof value!=='object'||typeof value.name!=='string'))return null;
    return values.map(value=>({...value}));
  };
  const proof=raw=>{
    if(typeof raw!=='string'||raw.length>4096)return null;
    try{
      const value=JSON.parse(raw);
      if(!value||typeof value!=='object'||Array.isArray(value)||value.allowed!==true||!Number.isSafeInteger(value.revision)||value.revision<1)return null;
      const keys=Object.keys(value).sort().join(',');
      if(keys==='allowed,revision,scope'&&value.scope==='private-admission-unchanged')return value;
      if(keys!=='allowed,revision,userAgent'||typeof value.userAgent!=='string'||value.userAgent.length<1||value.userAgent.length>1024||!/^[\x20-\x7e]+$/.test(value.userAgent))return null;
      return value;
    }catch(_){return null;}
  };
  const aligned=(values,userAgent)=>{
    const result=[];let present=false;
    for(const value of values){
      if(value.name.toLowerCase()==='user-agent'){
        if(present)continue;present=true;
        const header={...value,value:userAgent};delete header.binaryValue;result.push(header);
      }else result.push(value);
    }
    if(!present)result.push({name:'User-Agent',value:userAgent});
    return {requestHeaders:result};
  };
  const ipHeaders=values=>values.filter(value=>!['cookie','authorization','proxy-authorization','origin','referer'].includes(value.name.toLowerCase()));
  const filter=(details,sanitized={})=>{
    if(!installed||owner===null||!details||typeof details!=='object'||typeof details.url!=='string'||details.url.length>8192)return Promise.resolve(CANCEL);
    try{const url=new URL(details.url);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return Promise.resolve(CANCEL);}catch(_){return Promise.resolve(CANCEL);}
    let values=headers(details,sanitized);if(values===null)return Promise.resolve(CANCEL);
    const port=owner,epoch=serial;
    const bootstrap=ipBootstrap;let ipAuthorization;
    try{ipAuthorization=bootstrap?.authorization(details)??null;}catch(_){return Promise.resolve(CANCEL);}
    if(ipAuthorization)values=ipHeaders(values);
    try{
      if(!ipAuthorization&&extensionInitiated(details)&&globalThis.PocketRequestIdentityBackground?.controlRequest(details)===true)return Promise.resolve({requestHeaders:values});
    }catch(_){return Promise.resolve(CANCEL);}
    return new Promise(resolve=>{
      let finished=false;
      const cancel=()=>finish(CANCEL);
      const finish=value=>{if(finished)return;finished=true;clearTimeout(timer);pending.delete(cancel);resolve(value);};
      const timer=setTimeout(()=>finish(CANCEL),DEADLINE_MS);
      pending.add(cancel);
      let request;
      try{request=browser.runtime.sendNativeMessage('pocketroute',ipAuthorization?{kind:'timezoneIpHeaders',url:details.url,method:details.method,requestToken:ipAuthorization.requestToken,routeStamp:ipAuthorization.routeStamp}:{kind:'requestHeaderPolicy',url:details.url});}
      catch(_){finish(CANCEL);return;}
      Promise.resolve(request).then(raw=>{
        if(finished||!current(port,epoch)||ipAuthorization&&(bootstrap!==ipBootstrap||bootstrap.authorization(details)!==ipAuthorization)){finish(CANCEL);return;}
        const accepted=proof(raw);if(!accepted||ipAuthorization&&accepted.scope||revision!==null&&accepted.revision!==revision){finish(CANCEL);return;}
        let latest;
        try{
          const scope=globalThis.PocketRequestIdentityBackground;
          if(typeof scope?.headerDecision!=='function'){finish(CANCEL);return;}
          // Scope cancellation/expiry while native work was pending must win.
          // Start from the already sanitized copy so no earlier removal can
          // be undone if a subsequent sanitizer has fewer fields to remove.
          const snapshot={...details,requestHeaders:values};latest=headers(snapshot,scope.headerDecision(snapshot));
        }catch(_){finish(CANCEL);return;}
        if(ipAuthorization&&latest!==null)latest=ipHeaders(latest);
        if(latest===null||!current(port,epoch)||ipAuthorization&&(bootstrap!==ipBootstrap||bootstrap.authorization(details)!==ipAuthorization)){finish(CANCEL);return;}
        // Only a still-current first proof may establish the initial revision.
        // A delayed response never overwrites a newer native invalidation.
        if(revision===null)revision=accepted.revision;
        // Only the native guard classifies a private admitted target. Preserve
        // its existing headers without presenting this as a native UA read.
        finish(accepted.scope==='private-admission-unchanged'?{requestHeaders:latest}:aligned(latest,accepted.userAgent));
      },()=>finish(CANCEL));
    });
  };
  const listener=details=>{
    let sanitized;
    try{
      if(typeof globalThis.PocketRequestIdentityBackground?.headerDecision!=='function')return Promise.resolve(CANCEL);
      sanitized=globalThis.PocketRequestIdentityBackground.headerDecision(details);
    }catch(_){return Promise.resolve(CANCEL);}
    return filter(details,sanitized);
  };
  const install=()=>{
    if(attempted)return installed;attempted=true;
    let event;
    try{
      event=browser.webRequest?.onBeforeSendHeaders;
      if(typeof event?.addListener!=='function'||typeof event?.removeListener!=='function'||typeof browser.runtime?.sendNativeMessage!=='function'||typeof browser.runtime?.getURL!=='function')return false;
      event.addListener(listener,{urls:['http://*/*','https://*/*']},['blocking','requestHeaders']);installed=true;
    }catch(_){try{event?.removeListener(listener);}catch(_){}installed=false;}
    return installed;
  };
  globalThis.PocketGeckoRequestHeaders=Object.freeze({
    activate(port,bootstrap=null){
      if(!port||typeof port!=='object')return {installed:false};
      owner=port;ipBootstrap=bootstrap;changed();revision=null;return {installed:install()};
    },
    clear(port){if(port!==owner)return false;owner=null;ipBootstrap=null;changed();revision=null;return true;},
    invalidate(port,value){
      if(port!==owner||!Number.isSafeInteger(value)||value<1||revision!==null&&value<revision)return false;
      changed();revision=value;return true;
    },
    filter,
    status(){return {installed};}
  });
  install();
})();
