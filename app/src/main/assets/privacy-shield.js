/* Limited WebView privacy controls. No identity, timezone or country fabrication. */
(() => {
  'use strict';
  if(window.__pocketPrivacy)return;
  const level=__LEVEL__;
  const denied=()=>{throw new DOMException('This feature is restricted by the app privacy mode.','NotAllowedError');};
  const replace=(object,key,value)=>{try{Object.defineProperty(object,key,{value,writable:false,configurable:false});return true;}catch{return false;}};
  let rtc=false,hardware=false,canvas=false,webgl=false,network=false,battery=false;
  for(const key of ["connection","mozConnection","webkitConnection"])if(key in navigator){try{Object.defineProperty(Navigator.prototype,key,{get:()=>undefined,configurable:false});network=true;}catch{}}
  if(typeof navigator.getBattery==="function")battery=replace(Navigator.prototype,"getBattery",()=>Promise.reject(new DOMException("Battery access is restricted by privacy settings.","NotAllowedError")));
  for(const key of ['RTCPeerConnection','webkitRTCPeerConnection','mozRTCPeerConnection'])if(key in window)rtc=replace(window,key,function RestrictedPeerConnection(){denied();})||rtc;
  for(const key of ['hardwareConcurrency','deviceMemory'])if(key in navigator){const native=Number(navigator[key]);try{Object.defineProperty(Navigator.prototype,key,{get:()=>Math.min(native||4,4),configurable:false});hardware=true;}catch{}}
  for(const type of ['WebGLRenderingContext','WebGL2RenderingContext']){
    const prototype=window[type]?.prototype;if(!prototype)continue;const parameter=prototype.getParameter,extension=prototype.getExtension;
    if(parameter)webgl=replace(prototype,'getParameter',function(value){return value===0x9245||value===0x9246?'':parameter.call(this,value);})||webgl;
    if(extension)replace(prototype,'getExtension',function(name){return String(name).toLowerCase()==='webgl_debug_renderer_info'?null:extension.call(this,name);});
  }
  if(level>=2){
    for(const [type,methods] of [['HTMLCanvasElement',['toDataURL','toBlob']],['OffscreenCanvas',['convertToBlob']],['CanvasRenderingContext2D',['getImageData']],['OffscreenCanvasRenderingContext2D',['getImageData']],['WebGLRenderingContext',['readPixels']],['WebGL2RenderingContext',['readPixels']],['AudioBuffer',['getChannelData','copyFromChannel']]]){
      const prototype=window[type]?.prototype;if(!prototype)continue;for(const method of methods)if(typeof prototype[method]==='function')canvas=replace(prototype,method,denied)||canvas;
    }
  }
  Object.defineProperty(window,'__pocketPrivacy',{value:Object.freeze({level,rtc,hardware,canvas,webgl,network,battery}),writable:false,configurable:false});
})();
