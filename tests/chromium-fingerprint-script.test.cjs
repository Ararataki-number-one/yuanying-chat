const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const asset=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/chromium-fingerprint.js'),'utf8');
function realm(seed='1'.repeat(64),origin='https://first.example',options={}){
 const context=vm.createContext({DOMException,Uint8ClampedArray,Float32Array,queueMicrotask,Buffer});
 vm.runInContext(`
 const stats={exports:0,reads:0};
 class Canvas {
  constructor(){this.w=32;this.h=32;this.pixels=new Uint8ClampedArray(this.w*this.h*4);this.context=null;this.kind=null;this.tainted=false;}
  get width(){if(!(this instanceof Canvas))throw new TypeError('canvas receiver');return this.w;}
  set width(v){this.w=Number(v)>>>0;this.pixels=new Uint8ClampedArray(this.w*this.h*4);}
  get height(){if(!(this instanceof Canvas))throw new TypeError('canvas receiver');return this.h;}
  set height(v){this.h=Number(v)>>>0;this.pixels=new Uint8ClampedArray(this.w*this.h*4);}
  getContext(kind){if(!(this instanceof Canvas))throw new TypeError('canvas receiver');if(!arguments.length)throw new TypeError('missing kind');kind=''+kind;if(this.kind&&this.kind!==kind)return null;if(!['2d','webgl'].includes(kind))return null;this.kind=kind;return this.context||(this.context=kind==='2d'?new Context(this):new GL());}
  encode(type){if(!(this instanceof Canvas))throw new TypeError('canvas receiver');if(this.tainted)throw new DOMException('taint','SecurityError');if(!this.width||!this.height)return 'data:,';return JSON.stringify({w:this.width,h:this.height,pixels:Array.from(this.pixels),type:type===undefined?'image/png':''+type});}
  toDataURL(type){stats.exports++;return this.encode(type);}
  toBlob(callback,type){if(typeof callback!=='function')throw new TypeError('callback');const encoded=this.encode(type);stats.exports++;queueMicrotask(()=>callback(encoded==='data:,'?null:{encoded}));}
 }
 class Context {
  constructor(canvas){this.owner=canvas;}
  get canvas(){if(!(this instanceof Context))throw new TypeError('context receiver');return this.owner;}
  fillRect(){this.owner.pixels.fill(120);for(let i=3;i<this.owner.pixels.length;i+=4)this.owner.pixels[i]=255;}
  getImageData(x,y,w,h){if(!(this instanceof Context))throw new TypeError('context receiver');if(arguments.length<4)throw new TypeError('missing coordinates');stats.reads++;x=(+x)|0;y=(+y)|0;w=(+w)|0;h=(+h)|0;if(this.canvas.tainted)throw new DOMException('taint','SecurityError');if(w<0)x+=w;if(h<0)y+=h;w=Math.abs(w);h=Math.abs(h);if(!w||!h)throw new DOMException('zero','IndexSizeError');const data=new Uint8ClampedArray(w*h*4);for(let py=0;py<h;py++)for(let px=0;px<w;px++)if(x+px>=0&&y+py>=0&&x+px<this.canvas.width&&y+py<this.canvas.height)for(let c=0;c<4;c++)data[(py*w+px)*4+c]=this.canvas.pixels[((py+y)*this.canvas.width+px+x)*4+c];return {width:w,height:h,data};}
  putImageData(image){this.canvas.pixels.set(image.data);}
 }
 class GL {getExtension(name){return name==='WEBGL_debug_renderer_info'?{UNMASKED_RENDERER_WEBGL:37446}:null;}getParameter(name){return (+name)===37446?'actual gpu':(+name)===37445?'actual vendor':7;}getSupportedExtensions(){return ['WEBGL_debug_renderer_info','EXT_ordinary'];}}
 class AudioBuffer {constructor(o){this.length=o.length;this.sampleRate=o.sampleRate;this.channels=Array.from({length:o.numberOfChannels},()=>new Float32Array(o.length));}getChannelData(c){if(!this.channels[c])throw new RangeError('channel');return this.channels[c];}copyFromChannel(out,c,start=0){if(!(this instanceof AudioBuffer)||!(out instanceof Float32Array)||arguments.length<2)throw new TypeError('audio arguments');c=(+c)|0;start=(+start)>>>0;const source=this.getChannelData(c);out.set(source.subarray(start,start+out.length));}}
 globalThis.HTMLCanvasElement=Canvas;globalThis.CanvasRenderingContext2D=Context;globalThis.WebGLRenderingContext=GL;globalThis.AudioBuffer=AudioBuffer;globalThis.RTCPeerConnection=function RealPeer(){};globalThis.document={createElement:()=>new Canvas()};
 globalThis.nativeRead=Context.prototype.getImageData;globalThis.nativeCopy=AudioBuffer.prototype.copyFromChannel;globalThis.stats=stats;
 `,context);
 context.location={origin};
 const config=Object.assign({schema:1,seed,canvas:true,webgl:true,audio:true,webrtc:true},options);
 const compiled=asset.replace('__POCKETCHAT_CHROMIUM_FINGERPRINT_CONFIG__',JSON.stringify(config));vm.runInContext(compiled,context);
 return {context,run(code){return vm.runInContext(code,context);},inject(){vm.runInContext(compiled,context);}};
}
function pixels(r){return Array.from(r.run(`(()=>{const c=document.createElement('canvas'),x=c.getContext('2d');x.fillRect();return Array.from(x.getImageData(0,0,32,32).data)})()`));}
test('actual asset gives stable per-environment/origin readouts without modifying the original canvas',()=>{
 const r=realm();r.run(`var c=document.createElement('canvas'),x=c.getContext('2d');x.fillRect();var before=Array.from(nativeRead.call(x,0,0,32,32).data);`);
 const first=r.run('Array.from(x.getImageData(0,0,32,32).data)');assert.notDeepEqual(first,r.run('before'));assert.deepEqual(first,r.run('Array.from(x.getImageData(0,0,32,32).data)'));assert.deepEqual(r.run('before'),r.run('Array.from(nativeRead.call(x,0,0,32,32).data)'));
 assert.notDeepEqual(pixels(realm('2'.repeat(64))),pixels(r));assert.notDeepEqual(pixels(realm('1'.repeat(64),'https://other.example')),pixels(r));r.inject();assert.deepEqual(first,r.run('Array.from(x.getImageData(0,0,32,32).data)'));
});
test('exports encode once, do not lock untouched context types, and retain callback snapshot and async semantics',async()=>{
 const r=realm();r.run(`var blank=document.createElement('canvas');blank.toDataURL();var unlocked=blank.getContext('webgl')!==null;var c=document.createElement('canvas'),x=c.getContext('2d');x.fillRect();`);assert.equal(r.run('unlocked'),true);
 let calls=0;r.context.mime={toString(){calls++;return'image/png';}};const encoded=r.run('c.toDataURL(mime)');assert.equal(calls,1);assert.equal(r.run('stats.exports'),2);
 const untouched=r.run('Array.from(c.pixels)');let callbackBeforeReturn=true,callbackCount=0;
 const pending=new Promise(resolve=>{r.context.done=blob=>{assert.equal(callbackBeforeReturn,false);callbackCount++;resolve(blob);};r.run('c.toBlob(done,mime)');callbackBeforeReturn=false;r.run('c.pixels.fill(0)');});
 const blob=await pending;assert.equal(callbackCount,1);assert.equal(blob.encoded,encoded);assert.equal(calls,2);assert.equal(r.run('stats.exports'),3);assert.ok(untouched.some(x=>x!==0));assert.throws(()=>r.run('c.toBlob(null)'),{name:'TypeError'});
});
test('taint, empty canvas, native receiver checks, negative regions and resizing remain meaningful',async()=>{
 const r=realm();r.run(`var c=document.createElement('canvas'),x=c.getContext('2d');x.fillRect();c.tainted=true;`);
 for(const call of ['x.getImageData(0,0,32,32)','c.toDataURL()','c.toBlob(()=>{})'])assert.throws(()=>r.run(call),{name:'SecurityError'});
 assert.throws(()=>r.run('HTMLCanvasElement.prototype.getContext.call({},"2d")'),{name:'TypeError'});
 r.run('c.tainted=false');assert.deepEqual(r.run('Array.from(x.getImageData(32,32,-32,-32).data)'),r.run('Array.from(x.getImageData(0,0,32,32).data)'));
 r.run('c.width=16;c.height=16;x.fillRect()');assert.deepEqual(r.run('Array.from(x.getImageData(0,0,16,16).data)'),r.run('Array.from(x.getImageData(0,0,16,16).data)'));
 r.run('c.width=0');assert.equal(r.run('c.toDataURL()'),'data:,');assert.equal(await new Promise(resolve=>{r.context.done=resolve;r.run('c.toBlob(done)');}),null);
});
test('canvas budget fails closed before an encoder allocation and type coercion happens once',()=>{
 const r=realm();let conversions=0;r.context.kind={toString(){conversions++;return'2d';}};r.run(`var c=document.createElement('canvas'),x=c.getContext(kind);`);assert.equal(conversions,1);
 r.run('c.width=2049;c.height=2049');assert.throws(()=>r.run('c.toDataURL()'),{name:'SecurityError'});assert.equal(r.run('stats.exports'),0);
});
test('WebGL debug data is hidden for numeric and string enums, ordinary APIs still work',()=>{
 const r=realm();r.run(`var gl=new WebGLRenderingContext();`);assert.equal(r.run('gl.getExtension("WEBGL_debug_renderer_info")'),null);assert.equal(r.run('gl.getParameter(37446)'),null);assert.equal(r.run('gl.getParameter("37446")'),null);assert.equal(r.run('gl.getParameter(2)'),7);assert.equal(r.run('gl.getSupportedExtensions().join(",")'),'EXT_ordinary');
 let calls=0;r.context.ext={toString(){calls++;return'WEBGL_debug_renderer_info';}};assert.equal(r.run('gl.getExtension(ext)'),null);assert.equal(calls,1);
});
test('copied audio gets stable noise while writable live channel/playback data remains untouched',()=>{
 const r=realm();r.run(`var b=new AudioBuffer({length:64,numberOfChannels:1,sampleRate:48000}),live=b.getChannelData(0);live.fill(.125);var a=new Float32Array(64),z=new Float32Array(64);b.copyFromChannel(a,0);b.copyFromChannel(z,0);`);assert.deepEqual(r.run('Array.from(a)'),r.run('Array.from(z)'));assert.ok(r.run('Array.from(a).some(x=>x!==.125)'));assert.equal(r.run('b.getChannelData(0)===live'),true);assert.equal(r.run('live.every(x=>x===.125)'),true);r.run('live[0]=.75');assert.equal(r.run('b.getChannelData(0)[0]'),.75);assert.throws(()=>r.run('b.copyFromChannel(a,5)'),{name:'RangeError'});
});
test('native coordinate and audio argument conversion occurs once and BigInt/missing argument failures remain native',()=>{
 const r=realm();let coordinates=0,channels=0,starts=0;
 r.context.coordinate={valueOf(){coordinates++;return 0;}};r.context.channel={valueOf(){channels++;return 0;}};r.context.start={valueOf(){starts++;return 0;}};
 r.run(`var c=document.createElement('canvas'),x=c.getContext('2d');x.fillRect();x.getImageData(coordinate,0,32,32);var b=new AudioBuffer({length:64,numberOfChannels:1,sampleRate:48000}),out=new Float32Array(64);b.copyFromChannel(out,channel,start);`);
 assert.equal(coordinates,1);assert.equal(channels,1);assert.equal(starts,1);
 for(const call of ['c.getContext()','x.getImageData()','x.getImageData(0n,0,32,32)','b.copyFromChannel(out,0n)','b.copyFromChannel(out)'])assert.throws(()=>r.run(call),{name:'TypeError'});
});
test('DOMString arguments use string primitive hints exactly once and reject Symbols',()=>{
 const r=realm(),hints=[];for(const [name,value]of [['kind','2d'],['mime','image/png'],['ext','WEBGL_debug_renderer_info']])r.context[name]={[Symbol.toPrimitive](hint){hints.push(hint);return value;}};
 r.run(`var c=document.createElement('canvas'),x=c.getContext(kind);x.fillRect();c.toDataURL(mime);(new WebGLRenderingContext()).getExtension(ext);`);assert.deepEqual(hints,['string','string','string']);
 for(const call of ['c.getContext(Symbol())','c.toDataURL(Symbol())','c.toBlob(()=>{},Symbol())','(new WebGLRenderingContext()).getExtension(Symbol())'])assert.throws(()=>r.run(call),{name:'TypeError'});
});
test('window peer construction is denied and capability report never exposes seed or claims uncovered contexts',()=>{
 const r=realm();assert.throws(()=>r.run('new RTCPeerConnection()'),{name:'NotAllowedError'});const report=r.run('__pocketchatChromiumFingerprintObserve()');assert.equal(report.fingerprintProtectionVerified,false);for(const row of Object.values(report.fields))assert.equal(row.state,'page-observed');assert.ok(report.unsupported.includes('worker'));assert.ok(report.unsupported.includes('audioGetChannelData'));assert.equal(JSON.stringify(report).includes('1'.repeat(64)),false);
 r.run('CanvasRenderingContext2D.prototype.getImageData=function(){throw Error("changed")}');assert.equal(r.run('__pocketchatChromiumFingerprintObserve().fields.canvas.state'),'failed');
});
test('all disabled controls keep native readout/RTC semantics and report not-requested',()=>{
 const r=realm('3'.repeat(64),'https://plain.example',{canvas:false,webgl:false,audio:false,webrtc:false});r.run(`var c=document.createElement('canvas'),x=c.getContext('2d');x.fillRect();`);assert.deepEqual(r.run('Array.from(x.getImageData(0,0,32,32).data)'),r.run('Array.from(nativeRead.call(x,0,0,32,32).data)'));assert.doesNotThrow(()=>r.run('new RTCPeerConnection()'));for(const row of Object.values(r.run('__pocketchatChromiumFingerprintObserve().fields')))assert.equal(row.state,'not-requested');
});
test('missing real WebGL contexts and replaced RTC constructors cannot be reported page-observed',()=>{
 const r=realm();r.run(`var savedContext=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind){return kind==='webgl'||kind==='webgl2'?null:savedContext.apply(this,arguments)};RTCPeerConnection=function ForeignPeer(){};`);
 assert.equal(r.run('__pocketchatChromiumFingerprintObserve().fields.webgl.state'),'unsupported');assert.equal(r.run('__pocketchatChromiumFingerprintObserve().fields.webrtc.state'),'failed');
});
