/* Host-private adapter to the bundled native BrowsingContext setting API. */
(() => {
  'use strict';
  const FIELDS=['schema','status','requestToken','sessionId','requestedZoneId','nativeZoneId','contextId','nativeSettingReadback','scope','workerCoverageVerified','serviceWorkerCoverageVerified'];
  const identity=value=>typeof value==='string'&&/^[A-Za-z0-9_.:-]{1,160}$/.test(value);
  const zone=value=>{
    if(typeof value!=='string'||value.length>80||value!==''&&!/^[A-Za-z0-9_+\/-]+$/.test(value))return false;
    if(value!=='')try{new Intl.DateTimeFormat('en-US',{timeZone:value});}catch(_){return false;}
    return true;
  };
  const failure=(request,status,reason)=>({schema:1,status,requestToken:identity(request?.requestToken)?request.requestToken:'',sessionId:identity(request?.sessionId)?request.sessionId:'',requestedZoneId:request?.kind==='timezoneApply'&&zone(request.zoneId)?request.zoneId:'',nativeZoneId:'',contextId:'',nativeSettingReadback:false,scope:'top-browsing-context',workerCoverageVerified:false,serviceWorkerCoverageVerified:false,reason});
  const request=value=>{
    if(!value||typeof value!=='object'||Array.isArray(value))return null;
    const copy={kind:value.kind,id:value.id,sessionId:value.sessionId,requestToken:value.requestToken};
    if(!['timezoneApply','timezoneRead'].includes(copy.kind)||!Number.isInteger(copy.id)||copy.id<1||copy.id>2147483647||!identity(copy.sessionId)||!identity(copy.requestToken))return null;
    const expected=copy.kind==='timezoneApply'?['kind','id','sessionId','requestToken','zoneId']:['kind','id','sessionId','requestToken'];
    if(Object.keys(value).sort().join(',')!==expected.sort().join(','))return null;
    if(copy.kind==='timezoneApply'){copy.zoneId=value.zoneId;if(!zone(copy.zoneId))return null;}
    return copy;
  };
  const receipt=(value,selected)=>{
    if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join(',')!==FIELDS.slice().sort().join(','))return null;
    const copy={};for(const key of FIELDS)copy[key]=value[key];
    if(copy.schema!==1||copy.status!==(selected.kind==='timezoneApply'?'applied':'read')||copy.requestToken!==selected.requestToken||copy.sessionId!==selected.sessionId||typeof copy.contextId!=='string'||!/^[1-9][0-9]{0,23}$/.test(copy.contextId)||copy.nativeSettingReadback!==true||copy.scope!=='top-browsing-context'||copy.workerCoverageVerified!==false||copy.serviceWorkerCoverageVerified!==false||!zone(copy.requestedZoneId)||!zone(copy.nativeZoneId)||copy.requestedZoneId!==copy.nativeZoneId)return null;
    if(selected.kind==='timezoneApply'&&(copy.requestedZoneId!==selected.zoneId||copy.nativeZoneId!==selected.zoneId))return null;
    return copy;
  };
  globalThis.PocketNativeTimezoneBridge=Object.freeze({
    async handle(message){
      let selected;
      try{selected=request(message);}catch(_){selected=null;}
      if(!selected)return failure(null,'failed','invalid-timezone-request');
      try{
        const api=globalThis.browser?.pocketNativeTimezone;
        const method=selected.kind==='timezoneApply'?'applySession':'readSession';
        if(typeof api?.[method]!=='function')return failure(selected,'unsupported','native-timezone-api-unavailable');
        const raw=selected.kind==='timezoneApply'?await api.applySession(selected.sessionId,selected.zoneId,selected.requestToken):await api.readSession(selected.sessionId,selected.requestToken);
        const checked=receipt(raw,selected);
        return checked??failure(selected,'failed','native-timezone-receipt-invalid');
      }catch(error){
        const unsupported=new Set(['native-timezone-property-unavailable','native-timezone-readback-unavailable','timezone-window-enumeration-unavailable']);
        return failure(selected,unsupported.has(error?.message)?'unsupported':'failed',unsupported.has(error?.message)?error.message:'native-timezone-call-failed');
      }
    }
  });
})();
