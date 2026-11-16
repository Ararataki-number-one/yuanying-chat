(function () {
  'use strict';
  const policy = __POCKETCHAT_CHROMIUM_FINGERPRINT_CONFIG__;
  const g = globalThis, marker = Symbol.for('local.pocketchat.chromiumFingerprint.v1');
  if (g[marker]) return;
  const apply = Reflect.apply, define = Object.defineProperty, descriptor = Object.getOwnPropertyDescriptor;
  const statuses = {}, installed = {};
  const origin = String(g.location && g.location.origin || 'null');
  function hash(text) { let h = 2166136261; for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619); return h >>> 0; }
  const salt = hash(policy.seed + '|' + origin);
  function replace(target, name, fn) {
    const d = descriptor(target, name);
    if (!d || typeof d.value !== 'function') return false;
    define(target, name, Object.assign({}, d, {value: fn}));
    return target[name] === fn;
  }
  function failure(message) { return new DOMException(message, 'SecurityError'); }
  const workerMode = policy.workers === 'restrict' ? 'restrict' : 'allow';
  const workerGuards = {}, workerAvailable = {}, workerOriginal = {};
  let workerFailed = false, registrationGuard = null, registrationProto = null;
  let registrationAvailable = false, registrationDenied = false;
  const rejectPromise = Promise.reject.bind(Promise), promiseThen = Promise.prototype.then;
  function lock(target, name, value) {
    const previous = descriptor(target, name);
    define(target, name, {value, enumerable: previous ? previous.enumerable : false,
      configurable: false, writable: false});
    return target[name] === value;
  }
  // Availability is observational even when creation restrictions were not requested.
  for (const name of ['Worker', 'SharedWorker']) {
    workerOriginal[name] = g[name];workerAvailable[name] = typeof workerOriginal[name] === 'function';
  }
  let container = null;
  try { container = g.navigator && g.navigator.serviceWorker; } catch (_) { /* Opaque/insecure contexts cannot register. */ }
  registrationProto = container && Object.getPrototypeOf(container);
  registrationAvailable = !!registrationProto && typeof registrationProto.register === 'function';
  if (workerMode === 'restrict') {
    for (const name of ['Worker', 'SharedWorker']) {
      const Native = workerOriginal[name];
      if (!workerAvailable[name]) continue;
      try {
        function blockedWorker() {
          if (!new.target) throw new TypeError(name + ' requires the new operator');
          throw failure('New ' + name + ' creation is restricted by this browser environment');
        }
        define(blockedWorker, 'name', {value: Native.name, configurable: true});
        define(blockedWorker, 'length', {value: Native.length, configurable: true});
        define(blockedWorker, 'prototype', {value: Native.prototype, writable: false});
        if (!lock(Native.prototype, 'constructor', blockedWorker) || !lock(g, name, blockedWorker)) throw failure('Worker creation guard unavailable');
        workerGuards[name] = blockedWorker;
      } catch (_) { workerFailed = true; }
    }
    try {
      if (registrationAvailable) {
        function blockedRegistration() { return rejectPromise(failure('New Service Worker registration is restricted by this browser environment')); }
        if (!lock(registrationProto, 'register', blockedRegistration)) throw failure('Service Worker registration guard unavailable');
        registrationGuard = blockedRegistration;
        // Exercise our installed guard only. No registration reaches the native API or network.
        apply(promiseThen, apply(blockedRegistration, container, ['__restricted_worker_probe__']),
          [() => { workerFailed = true; }, error => { registrationDenied = !!error && error.name === 'SecurityError'; }]);
      }
    } catch (_) { workerFailed = true; }
  }
  function workerObservation() {
    const result = {mode: workerMode, scope: 'page-frame-new-workers-only', state: 'not-requested',
      dedicatedAvailable: !!workerAvailable.Worker, sharedAvailable: !!workerAvailable.SharedWorker,
      dedicatedCreationDenied: false, sharedCreationDenied: false,
      serviceRegistrationAvailable: registrationAvailable, serviceRegistrationGuardInstalled: false,
      serviceRegistrationDenied: false, existingExecutionControlled: false};
    if (workerMode !== 'restrict') return result;
    let failed = workerFailed;
    for (const [name, field] of [['Worker', 'dedicatedCreationDenied'], ['SharedWorker', 'sharedCreationDenied']]) {
      if (!workerAvailable[name]) { if (g[name] !== workerOriginal[name]) failed = true;continue; }
      const guard = workerGuards[name];
      if (!guard || g[name] !== guard || guard.prototype.constructor !== guard) { failed = true;continue; }
      try { new guard('__restricted_worker_probe__');failed = true; }
      catch (error) { result[field] = !!error && error.name === 'SecurityError';if (!result[field]) failed = true; }
    }
    result.serviceRegistrationGuardInstalled = registrationAvailable && registrationProto.register === registrationGuard;
    result.serviceRegistrationDenied = result.serviceRegistrationGuardInstalled && registrationDenied;
    if (registrationAvailable && !result.serviceRegistrationGuardInstalled) failed = true;
    result.state = failed ? 'failed' : registrationAvailable && !registrationDenied ? 'requested' :
      (workerAvailable.Worker || workerAvailable.SharedWorker || registrationAvailable) ? 'page-observed' : 'unsupported';
    return result;
  }
  function domString(value) { if (typeof value === 'symbol') throw new TypeError('A Symbol cannot be converted to DOMString'); return String(value); }
  function different(a, b) { if (a.length !== b.length) return true; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return true; return false; }
  const Canvas = g.HTMLCanvasElement, Context = g.CanvasRenderingContext2D;
  const getContext = Canvas && Canvas.prototype.getContext;
  const getImageData = Context && Context.prototype.getImageData;
  const putImageData = Context && Context.prototype.putImageData;
  const createCanvas = g.document && g.document.createElement.bind(g.document);
  const canvasGetter = Context && descriptor(Context.prototype, 'canvas');
  const widthGetter = Canvas && descriptor(Canvas.prototype, 'width'), heightGetter = Canvas && descriptor(Canvas.prototype, 'height');
  const canvases = new WeakMap();
  let photoCanvases = null;
  function width(canvas) { return apply(widthGetter.get, canvas, []); }
  function height(canvas) { return apply(heightGetter.get, canvas, []); }
  function canvasOf(context) { return canvasGetter && canvasGetter.get ? apply(canvasGetter.get, context, []) : context.canvas; }
  function selectedPhotoCanvases() {
    // Preserve real file-selection image processing without exempting ordinary
    // drawing/fingerprinting canvases. This is document-local, not a site allow.
    const Input=g.HTMLInputElement, Image=g.HTMLImageElement, Reader=g.FileReader, Blob=g.Blob;
    const draw=Context.prototype.drawImage, createBitmap=g.createImageBitmap;
    const filesGetter=Input&&descriptor(Input.prototype,'files')?.get;
    const fileItem=g.FileList?.prototype.item, fileLength=g.FileList&&descriptor(g.FileList.prototype,'length')?.get;
    const typeGetter=Blob&&descriptor(Blob.prototype,'type')?.get;
    const sourceGetter=Image&&descriptor(Image.prototype,'currentSrc')?.get;
    const inputType=Input&&descriptor(Input.prototype,'type')?.get;
    const readerResult=Reader&&descriptor(Reader.prototype,'result')?.get;
    const readData=Reader&&Reader.prototype.readAsDataURL;
    const add=g.EventTarget?.prototype.addEventListener, remove=g.EventTarget?.prototype.removeEventListener;
    const objectURL=g.URL?.createObjectURL, then=g.Promise?.prototype.then;
    const filter=descriptor(Context.prototype,'filter')?.get, shadow=descriptor(Context.prototype,'shadowColor')?.get;
    if(!draw||!filesGetter||!fileItem||!fileLength||!typeGetter||!sourceGetter||!inputType||!readerResult||!readData||!add||!remove||!objectURL||!then||!filter||!shadow)return null;
    let files=new WeakSet(), bitmaps=new WeakSet(), states=new WeakMap(), urls=new Map(), dataURLs=new Set(), dataBytes=0, generation=0, live=true;
    const raster=new Set(['image/png','image/jpeg','image/webp','image/gif','image/bmp','image/avif','image/heic','image/heif','image/tiff']);
    const state=canvas=>{
      const w=width(canvas),h=height(canvas);let value=states.get(canvas);
      if(!value||value.width!==w||value.height!==h){value={width:w,height:h,kind:'blank',clip:false};states.set(canvas,value);}
      return value;
    };
    const imageOnly=canvas=>live&&canvases.has(canvas)&&state(canvas).kind==='photo';
    const selectedSource=source=>{
      if(!live||!source)return false;
      if(bitmaps.has(source)||files.has(source))return true;
      if(canvases.has(source))return imageOnly(source);
      try{const url=apply(sourceGetter,source,[]);return urls.has(url)||dataURLs.has(url);}catch(_){return false;}
    };
    apply(add,g.document,['change',event=>{
      if(!live||event.isTrusted!==true)return;
      try{
        const input=event.target;if(apply(inputType,input,[])!=='file')return;
        const chosen=apply(filesGetter,input,[]);
        for(let i=0;i<Math.min(apply(fileLength,chosen,[]),32);i++){
          const file=apply(fileItem,chosen,[i]);if(file&&raster.has(apply(typeGetter,file,[])))files.add(file);
        }
      }catch(_){}
    },true]);
    apply(add,g,['pagehide',()=>{live=false;generation++;files=new WeakSet();bitmaps=new WeakSet();states=new WeakMap();urls.clear();dataURLs.clear();dataBytes=0;}]);
    apply(add,g,['pageshow',()=>{live=true;}]);
    replace(g.URL,'createObjectURL',function(blob){
      const url=apply(objectURL,this,arguments);
      if(live&&files.has(blob)){if(urls.size>=128)urls.delete(urls.keys().next().value);urls.set(url,true);}
      return url;
    });
    replace(Reader.prototype,'readAsDataURL',function(blob){
      if(!live||!files.has(blob))return apply(readData,this,arguments);
      const reader=this,selectedGeneration=generation,onload=()=>{try{
        const url=apply(readerResult,reader,[]);
        if(!live||selectedGeneration!==generation||typeof url!=='string'||url.length>33554432)return;
        while(dataURLs.size&&(dataURLs.size>=8||dataBytes+url.length>33554432)){
          const old=dataURLs.values().next().value;dataURLs.delete(old);dataBytes-=old.length;
        }
        if(!dataURLs.has(url)){dataURLs.add(url);dataBytes+=url.length;}
      }catch(_){}};
      apply(add,reader,['load',onload,{once:true}]);
      try{return apply(readData,reader,arguments);}catch(error){apply(remove,reader,['load',onload]);throw error;}
    });
    if(typeof createBitmap==='function')replace(g,'createImageBitmap',function(source){
      const selected=selectedSource(source),selectedGeneration=generation,promise=apply(createBitmap,this,arguments);
      if(!selected)return promise;
      return apply(then,promise,[bitmap=>{if(live&&selectedGeneration===generation)bitmaps.add(bitmap);return bitmap;}]);
    });
    // Unknown drawing calls invalidate the image-only provenance. Read-only and
    // path/state APIs cannot insert pixels; clip is conservatively unsupported.
    const harmless=new Set(['constructor','drawImage','getImageData','getTransform','createImageData','createLinearGradient',
      'createRadialGradient','createConicGradient','createPattern','measureText','isPointInPath','isPointInStroke','getLineDash',
      'getContextAttributes','isContextLost','save','restore','scale','rotate','translate','transform','setTransform','resetTransform',
      'setLineDash','beginPath','closePath','moveTo','lineTo','bezierCurveTo','quadraticCurveTo','arc','arcTo','ellipse','rect','roundRect']);
    for(const name of Object.getOwnPropertyNames(Context.prototype)){
      const method=descriptor(Context.prototype,name)?.value;
      if(typeof method!=='function'||harmless.has(name))continue;
      replace(Context.prototype,name,function(){
        const canvas=canvasOf(this),value=state(canvas);
        if(name==='clip')value.clip=true;
        else if(name!=='clearRect')value.kind='other';
        const result=apply(method,this,arguments);
        if(name==='reset'){value.kind='blank';value.clip=false;}
        return result;
      });
    }
    replace(Context.prototype,'drawImage',function(source){
      const value=state(canvasOf(this)),args=Array.prototype.slice.call(arguments);
      const eligible=(value.kind==='blank'||value.kind==='photo')&&!value.clip&&selectedSource(source)&&
        [3,5,9].includes(args.length)&&args.slice(1).every(number=>typeof number==='number'&&Number.isFinite(number))&&
        apply(filter,this,[])==='none'&&/^rgba\(0,\s*0,\s*0,\s*0\)$/.test(apply(shadow,this,[]));
      value.kind='other';const result=apply(draw,this,args);if(eligible)value.kind='photo';return result;
    });
    return {track:context=>state(canvasOf(context)),imageOnly};
  }
  function perturb(image, canvas, x, y) {
    if (!(image.data instanceof Uint8ClampedArray)) throw failure('This canvas pixel format is not covered by the privacy guard');
    const w = width(canvas), hgt = height(canvas);
    if (!(w > 0 && hgt > 0 && image.width > 0 && image.height > 0)) return;
    const h = hash(salt + ':canvas:' + w + ':' + hgt), index = h % (w * hgt);
    const px = index % w, py = Math.floor(index / w);
    if (px < x || py < y || px >= x + image.width || py >= y + image.height) return;
    const i = ((py - y) * image.width + px - x) * 4;
    if (image.data[i + 3] === 0) image.data[i + 3] = 1;
    else image.data[i + h % 3] ^= 1;
  }
  function cloneWithNoise(canvas) {
    const w = width(canvas), h = height(canvas);
    if (w * h > 4194304) throw failure('Canvas privacy export exceeds its memory budget');
    const image = apply(getImageData, canvases.get(canvas), [0, 0, w, h]);
    perturb(image, canvas, 0, 0);
    const clone = createCanvas('canvas'); clone.width = w; clone.height = h;
    const context = apply(getContext, clone, ['2d']);
    if (!context) throw failure('Canvas privacy export unavailable');
    apply(putImageData, context, [image, 0, 0]);
    return clone;
  }
  if (policy.canvas) {
    try {
      if (!Canvas || !Context || !getImageData || !putImageData || !createCanvas || !widthGetter || !heightGetter) statuses.canvas = 'unsupported';
      else {
        const toDataURL = Canvas.prototype.toDataURL, toBlob = Canvas.prototype.toBlob;
        function guardedContext() { if (!arguments.length) return apply(getContext, this, arguments); width(this); const args = Array.prototype.slice.call(arguments); args[0] = domString(args[0]); const result = apply(getContext, this, args); if (result && args[0] === '2d') { canvases.set(this, result); photoCanvases?.track(result); } return result; }
        function guardedImageData() {
          const canvas = canvasOf(this);
          if (arguments.length < 4) return apply(getImageData, this, arguments);
          const args = Array.prototype.slice.call(arguments); for (let i = 0; i < 4; i++) args[i] = (+args[i]) | 0;
          const result = apply(getImageData, this, args), w = args[2], h = args[3];
          const x = args[0] + Math.min(0, w), y = args[1] + Math.min(0, h);
          if(!photoCanvases?.imageOnly(canvas))perturb(result, canvas, x, y); return result;
        }
        function tracked(canvas) { return canvases.has(canvas); }
        function exportArguments(args, typeIndex) { const result = Array.prototype.slice.call(args); if (result.length > typeIndex && result[typeIndex] !== undefined) result[typeIndex] = domString(result[typeIndex]); return result; }
        // Native readback validates taint; native export executes only once.
        function guardedURL() {
          if (!tracked(this)) return apply(toDataURL, this, arguments);
          const args = exportArguments(arguments, 0);
          if (!width(this) || !height(this)) return apply(toDataURL, this, args);
          if(photoCanvases?.imageOnly(this))return apply(toDataURL,this,args);
          return apply(toDataURL, cloneWithNoise(this), args);
        }
        function guardedBlob(callback) {
          if (typeof callback !== 'function' || !tracked(this)) return apply(toBlob, this, arguments);
          const args = exportArguments(arguments, 1);
          if (!width(this) || !height(this)) return apply(toBlob, this, args);
          if(photoCanvases?.imageOnly(this))return apply(toBlob,this,args);
          return apply(toBlob, cloneWithNoise(this), args);
        }
        const ok = replace(Canvas.prototype, 'getContext', guardedContext) && replace(Context.prototype, 'getImageData', guardedImageData) &&
          replace(Canvas.prototype, 'toDataURL', guardedURL) && replace(Canvas.prototype, 'toBlob', guardedBlob);
        if(ok)photoCanvases=selectedPhotoCanvases();
        installed.canvas = {guardedImageData, guardedURL, guardedBlob, guardedContext}; statuses.canvas = ok ? 'installed' : 'failed';
      }
    } catch (_) { statuses.canvas = 'failed'; }
  } else statuses.canvas = 'not-requested';
  if (policy.webgl) {
    try {
      let count = 0; installed.webgl = [];
      for (const WebGL of [g.WebGLRenderingContext, g.WebGL2RenderingContext]) {
        if (!WebGL) continue;
        const p = WebGL.prototype, extension = p.getExtension, parameter = p.getParameter, supported = p.getSupportedExtensions;
        function guardedExtension(name) { const key = domString(name); if (key.toLowerCase() === 'webgl_debug_renderer_info') { apply(extension, this, ['__privacy_receiver_check__']); return null; } return apply(extension, this, [key]); }
        function guardedParameter(name) { const key = (+name) >>> 0, result = apply(parameter, this, [key]); return key === 37445 || key === 37446 ? null : result; }
        function guardedExtensions() { const result = apply(supported, this, arguments); return result && result.filter(name => name.toLowerCase() !== 'webgl_debug_renderer_info'); }
        if (!replace(p, 'getExtension', guardedExtension) || !replace(p, 'getParameter', guardedParameter) || !replace(p, 'getSupportedExtensions', guardedExtensions)) throw failure('WebGL guard unavailable');
        installed.webgl.push({p,guardedExtension,guardedParameter,guardedExtensions}); count++;
      }
      statuses.webgl = count ? 'installed' : 'unsupported';
    } catch (_) { statuses.webgl = 'failed'; }
  } else statuses.webgl = 'not-requested';
  const Audio = g.AudioBuffer, nativeCopy = Audio && Audio.prototype.copyFromChannel;
  const audioLength = Audio && descriptor(Audio.prototype, 'length');
  const typedName = descriptor(Object.getPrototypeOf(Float32Array.prototype), Symbol.toStringTag);
  if (policy.audio) {
    try {
      if (!nativeCopy) statuses.audio = 'unsupported';
      else {
        function copiedAudio(destination, channel, start) {
          const total = audioLength && audioLength.get ? apply(audioLength.get, this, []) : this.length;
          if (arguments.length < 2 || !typedName || apply(typedName.get, destination, []) !== 'Float32Array') return apply(nativeCopy, this, arguments);
          const selected = (+channel) | 0, offset = start === undefined ? 0 : (+start) >>> 0;
          const result = apply(nativeCopy, this, [destination, selected, offset]);
          const length = Math.min(destination.length, Math.max(0, total - offset));
          const h = hash(salt + ':audio:' + total + ':' + this.sampleRate + ':' + selected);
          const sample = total > 0 ? h % total : -1;
          if (sample >= offset && sample < offset + length && Number.isFinite(destination[sample - offset])) destination[sample - offset] += h & 1 ? 0.0000001 : -0.0000001;
          return result;
        }
        installed.audio = copiedAudio; statuses.audio = replace(Audio.prototype, 'copyFromChannel', copiedAudio) ? 'installed' : 'failed';
      }
    } catch (_) { statuses.audio = 'failed'; }
  } else statuses.audio = 'not-requested';
  if (policy.webrtc) {
    try {
      installed.webrtc = []; let count = 0;
      for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection']) {
        if (typeof g[name] !== 'function') continue;
        const d = descriptor(g, name);
        function blockedPeerConnection() { throw new DOMException('Window WebRTC is disabled by this environment', 'NotAllowedError'); }
        define(g, name, Object.assign({}, d, {value: blockedPeerConnection}));
        if (g[name] !== blockedPeerConnection) throw failure('Window WebRTC guard unavailable');
        installed.webrtc.push([name, blockedPeerConnection]); count++;
      }
      statuses.webrtc = count ? 'installed' : 'unsupported';
    } catch (_) { statuses.webrtc = 'failed'; }
  } else statuses.webrtc = 'not-requested';
  function observation() {
    const fields = {};
    for (const field of ['canvas', 'webgl', 'audio', 'webrtc']) fields[field] = {state: statuses[field] === 'installed' ? 'failed' : statuses[field]};
    if (statuses.canvas === 'installed') {
      try {
        const methods = installed.canvas, canvas = createCanvas('canvas'); canvas.width = 8; canvas.height = 8;
        const context = canvas.getContext('2d'); context.fillStyle = '#517399'; context.fillRect(0, 0, 8, 8);
        const baseline = apply(getImageData, context, [0, 0, 8, 8]), observed = context.getImageData(0, 0, 8, 8);
        const preserved = apply(getImageData, context, [0, 0, 8, 8]);
        if (Context.prototype.getImageData === methods.guardedImageData && Canvas.prototype.toDataURL === methods.guardedURL && Canvas.prototype.toBlob === methods.guardedBlob && different(baseline.data, observed.data) && !different(baseline.data, preserved.data)) fields.canvas.state = 'page-observed';
      } catch (_) {}
    }
    if (statuses.webgl === 'installed' && installed.webgl.every(x => x.p.getExtension === x.guardedExtension && x.p.getParameter === x.guardedParameter && x.p.getSupportedExtensions === x.guardedExtensions)) {
      let context;
      try {
        const canvas = createCanvas('canvas'); canvas.width = 1; canvas.height = 1;
        context = canvas.getContext('webgl') || canvas.getContext('webgl2');
        if (!context) fields.webgl.state = 'unsupported';
        else {
          const extensions = context.getSupportedExtensions();
          if (extensions && !extensions.some(x => x.toLowerCase() === 'webgl_debug_renderer_info') && context.getExtension('WEBGL_debug_renderer_info') === null && context.getParameter(37445) === null && context.getParameter(37446) === null) fields.webgl.state = 'page-observed';
        }
      } catch (_) {}
      finally { if (context) try { const release = context.getExtension('WEBGL_lose_context'); if (release) release.loseContext(); } catch (_) {} }
    }
    if (statuses.audio === 'installed') {
      try {
        const buffer = new Audio({length: 64, numberOfChannels: 1, sampleRate: 48000}), live = buffer.getChannelData(0); live.fill(0.125);
        const baseline = new Float32Array(64), observed = new Float32Array(64); apply(nativeCopy, buffer, [baseline, 0]); buffer.copyFromChannel(observed, 0);
        if (Audio.prototype.copyFromChannel === installed.audio && different(baseline, observed) && live.every(x => x === 0.125)) fields.audio.state = 'page-observed';
      } catch (_) {}
    }
    if (statuses.webrtc === 'installed' && installed.webrtc.every(x => g[x[0]] === x[1])) {
      let blocked = true;
      for (const [name] of installed.webrtc) { try { new g[name](); blocked = false; } catch (error) { if (!error || error.name !== 'NotAllowedError') blocked = false; } }
      if (blocked) fields.webrtc.state = 'page-observed';
    }
    return {schema: 1, scope: 'document-start-frames', fingerprintProtectionVerified: false, fields, workerCreation: workerObservation(),
      unsupported: ['worker','serviceWorker','offscreenCanvas','timezone','hardware','fonts','language','tls','http2','webRtcNative','audioGetChannelData','audioWorklet','webglReadPixels']};
  }
  define(g, '__pocketchatChromiumFingerprintObserve', {value: observation, configurable: false, enumerable: false});
  define(g, marker, {value: true, configurable: false, enumerable: false});
})();
