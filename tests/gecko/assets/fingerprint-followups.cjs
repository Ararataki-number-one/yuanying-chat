'use strict';
// Test-only wrapper: the production detector still handles every known audit URL.
const fs=require('node:fs'),https=require('node:https');
const {createIdentityServer,DEFAULT_BASE,PROTOCOL}=require('../../../tools/fingerprint/request_identity_server.cjs');
const [keyFile,certFile,directory,runNonce]=process.argv.slice(2);
if(!keyFile||!certFile||!directory||!/^[a-f0-9]{32}$/.test(runNonce||''))throw Error('Exact synthetic invocation required');
const host=process.env.POCKETCHAT_FINGERPRINT_FIXTURE_HOST||'10.0.2.2';
if(!['10.0.2.2','127.0.0.1'].includes(host))throw Error('Only explicit synthetic loopback hosts allowed');
const origin='https://'+host+':9889',redirectOrigin='https://'+host+':9890',frameOrigin='https://'+host+':9891',faultOrigin='https://'+host+':9892';
let faultMode='valid';
const key=fs.readFileSync(keyFile),cert=fs.readFileSync(certFile);
for(const name of ['server-trace.json','server-trace.jsonl'])if(fs.existsSync(directory+'/'+name))throw Error('Never overwrite prior evidence');
const trace={schema:1,runNonce,events:[],dropped:0,scope:'Independent synthetic HTTPS arrivals; no public site or phone acceptance'};
const sockets=new Set();let connection=0,serial=0,stopping=false;
function save(){fs.writeFileSync(directory+'/server-trace.json.partial',JSON.stringify(trace,null,2)+'\n');fs.renameSync(directory+'/server-trace.json.partial',directory+'/server-trace.json');}
function observe(server,name){
  server.on('secureConnection',socket=>{socket.fixtureConnection=++connection;sockets.add(socket);socket.on('close',()=>sockets.delete(socket));});
  server.prependListener('request',(req,res)=>{
    const url=new URL(req.url,'https://detector.invalid');
    const event={index:++serial,kind:'http',server:name,at:Date.now(),connection:req.socket.fixtureConnection||0,
      method:req.method,path:url.pathname,nonce:url.searchParams.get('nonce')||'',runNonce:url.searchParams.get('runNonce')||'',
      diagnosticFrameOptIn:url.pathname===DEFAULT_BASE+'document'&&url.searchParams.get('frame')==='1',
      ...(name==='fault'?{controlledResponseMode:faultMode}:{}),
      headers:{userAgent:req.headers['user-agent']||'',acceptLanguage:req.headers['accept-language']||'',secFetchDest:req.headers['sec-fetch-dest']||''},
      sensitive:{cookie:req.headers.cookie!==undefined,authorization:req.headers.authorization!==undefined,proxyAuthorization:req.headers['proxy-authorization']!==undefined,referer:req.headers.referer!==undefined,origin:req.headers.origin!==undefined},
      syntheticCookiePresent:String(req.headers.cookie||'').includes('fingerprint-preserve='+runNonce),
      syntheticAuthorizationPresent:req.headers.authorization==='Bearer fingerprint-fixture-'+runNonce};
    if(trace.events.length<1024){trace.events.push(event);fs.appendFileSync(directory+'/server-trace.jsonl',JSON.stringify(event)+'\n');}else trace.dropped++;
    save();
  });
  server.on('tlsClientError',()=>{});
}
function reply(res,status,body,type='application/json'){
  res.writeHead(status,{'Content-Type':type+'; charset=utf-8','Cache-Control':'no-store'});res.end(typeof body==='string'?body:JSON.stringify(body));
}
function chat(){
  return '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
    '<title>Controlled fingerprint source</title><main><h1>Controlled empty chat fixture</h1><textarea id="prompt-textarea" placeholder="ChatGPT"></textarea>'+
    '<button data-testid="send-button" disabled>Send</button><pre id="fixture-fetch-result">{}</pre><pre id="fixture-mode-result">{}</pre><span id="send-count">0</span><span id="fixture-nonce">'+runNonce+'</span></main>'+
    '<div style="height:1800px">Controlled reading position</div><script>'+
    'document.cookie="fingerprint-preserve='+runNonce+'; Path=/; Secure; SameSite=Lax";'+
    'addEventListener("pocket-fixture-fetch",async event=>{let c;try{c=JSON.parse(event.detail)}catch{return}'+
    'if(!c||!/^[a-f0-9]{32}$/.test(c.nonce)||!'+JSON.stringify([origin,redirectOrigin])+'.includes(c.origin)||!["document","capabilities","strict-probe","credential-probe","redirect-control"].includes(c.kind))return;'+
    'const path=["document","capabilities"].includes(c.kind)?"'+DEFAULT_BASE+'"+c.kind:"/"+c.kind;const target=c.origin+path+"?nonce="+c.nonce;'+
    'const out={nonce:c.nonce,phase:c.phase,source:"controlled-page-main-world-fetch",done:false};'+
    'try{const r=await fetch(target,{credentials:"include",redirect:"follow",referrerPolicy:"unsafe-url",headers:c.origin===location.origin?{Authorization:"Bearer fingerprint-fixture-'+runNonce+'"}:{}});out.ok=true;out.status=r.status;await r.text()}catch(e){out.ok=false;out.error=String(e&&e.name||"FetchFailed")}'+
    'out.done=true;document.getElementById("fixture-fetch-result").textContent=JSON.stringify(out);});'+
    'addEventListener("pocket-fixture-mode",async event=>{let c;try{c=JSON.parse(event.detail)}catch{return}'+
    'if(!c||!'+JSON.stringify(['valid','protocol','capacity','redirect','oversize','timeout'])+'.includes(c.mode))return;'+
    'const out={mode:c.mode,done:false};try{const r=await fetch("/fixture-control?nonce='+runNonce+'&mode="+c.mode,{credentials:"omit",redirect:"error",referrerPolicy:"no-referrer"});out.status=r.status;out.ok=r.ok&&((await r.json()).mode===c.mode)}catch(e){out.ok=false;out.error=String(e&&e.name||"FetchFailed")}'+
    'out.done=true;document.getElementById("fixture-mode-result").textContent=JSON.stringify(out);});'+
    '</script>';
}
const service=createIdentityServer({key,cert,frameEndpoint:frameOrigin+DEFAULT_BASE,output:directory+'/identity-server.json',rawLog:directory+'/identity-server.jsonl',extraHandler(req,res){
  const url=new URL(req.url,'https://detector.invalid');
  if(url.pathname==='/chat'&&url.searchParams.get('runNonce')===runNonce){reply(res,200,chat(),'text/html');return true;}
  if(url.pathname==='/fixture-control'){
    if(url.searchParams.getAll('nonce').length!==1||url.searchParams.get('nonce')!==runNonce||url.searchParams.getAll('mode').length!==1||![...url.searchParams.keys()].every(name=>['nonce','mode'].includes(name))||!['valid','protocol','capacity','redirect','oversize','timeout'].includes(url.searchParams.get('mode'))){reply(res,400,{error:'invalid-owned-fixture-control'});return true;}
    faultMode=url.searchParams.get('mode');reply(res,200,{ok:true,mode:faultMode,scope:'Test-only fault-server selection; production service behavior is unchanged'});return true;
  }
  if(url.pathname==='/strict-probe'||url.pathname==='/credential-probe'||url.pathname==='/redirected'){
    if(url.pathname==='/redirected'){res.setHeader('Access-Control-Allow-Origin',req.headers.origin==='null'?'null':origin);res.setHeader('Access-Control-Allow-Credentials','true');}
    reply(res,200,{ok:true,nonce:url.searchParams.get('nonce'),source:'synthetic-control-only'});return true;
  }
  return false;
}});
const redirect=https.createServer({key,cert,minVersion:'TLSv1.2'},(req,res)=>{
  const url=new URL(req.url,'https://detector.invalid');
  if(url.pathname==='/seed'){reply(res,200,'<!doctype html><title>Controlled redirect origin</title><p id="redirect-seed">'+runNonce+'</p>','text/html');return;}
  if(url.pathname===DEFAULT_BASE+'document'||url.pathname==='/redirect-control'){
    res.writeHead(302,{'Location':origin+'/redirected?nonce='+encodeURIComponent(url.searchParams.get('nonce')||''),'Cache-Control':'no-store','Access-Control-Allow-Origin':origin,'Access-Control-Allow-Credentials':'true'});res.end();return;
  }
  reply(res,404,{error:'not-found'});
});
const frameService=createIdentityServer({key,cert,frameParentOrigin:origin,output:directory+'/frame-server.json',rawLog:directory+'/frame-server.jsonl',extraHandler(req,res){
  const url=new URL(req.url,'https://frame.invalid');if(url.pathname==='/seed'){reply(res,200,'<!doctype html><title>Controlled frame origin</title><p id="frame-seed">'+runNonce+'</p>','text/html');return true;}return false;
}});
const fault=https.createServer({key,cert,minVersion:'TLSv1.2'},(req,res)=>{
  const url=new URL(req.url,'https://fault.invalid');
  if(url.pathname==='/seed'){reply(res,200,'<!doctype html><title>Controlled fault origin</title><p id="fault-seed">'+runNonce+'</p>','text/html');return;}
  if(url.pathname!==DEFAULT_BASE+'capabilities'||url.searchParams.getAll('nonce').length!==1||!/^[a-f0-9]{32}$/.test(url.searchParams.get('nonce')||'')||[...url.searchParams.keys()].some(name=>name!=='nonce')){reply(res,400,{error:'invalid-owned-capability-probe'});return;}
  if(['cookie','authorization','proxy-authorization','referer','origin'].some(name=>Object.prototype.hasOwnProperty.call(req.headers,name))){reply(res,403,{error:'credential-header-observed'});return;}
  const token=url.searchParams.get('nonce');
  if(faultMode==='capacity'){reply(res,429,{error:'detector-capacity'});return;}
  if(faultMode==='redirect'){res.writeHead(302,{'Location':origin+DEFAULT_BASE+'capabilities?nonce='+token,'Cache-Control':'no-store'});res.end();return;}
  if(faultMode==='oversize'){res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.write('{"padding":"');res.write('x'.repeat(131072));res.end('"}');return;}
  if(faultMode==='timeout'){const timer=setTimeout(()=>reply(res,503,{error:'controlled-delayed-response'}),15000);timer.unref();res.once('close',()=>clearTimeout(timer));return;}
  reply(res,200,{schema:1,protocol:faultMode==='protocol'?'controlled-wrong-protocol':PROTOCOL,nonce:token,source:'controlled-service-capabilities',status:'ready',capabilities:{topLevelDocument:true,dedicatedWorker:true,boundedWorkerReply:true,crossOriginFrame:false,crossOriginFrameReceiver:false},limits:{checkTtlMs:30000,maxConcurrentChecks:64,maxCheckEvents:12,workerResponseBytes:8192}});
});
observe(service.server,'detector');observe(redirect,'redirect');observe(frameService.server,'frame');observe(fault,'fault');
Promise.all([new Promise(resolve=>service.server.listen(9889,'0.0.0.0',resolve)),new Promise(resolve=>redirect.listen(9890,'0.0.0.0',resolve)),new Promise(resolve=>frameService.server.listen(9891,'0.0.0.0',resolve)),new Promise(resolve=>fault.listen(9892,'0.0.0.0',resolve))])
  .then(()=>{save();process.stdout.write(JSON.stringify({ready:true,ports:[9889,9890,9891,9892],runNonce})+'\n');});
async function close(){if(stopping)return;stopping=true;for(const socket of sockets)socket.destroy();await Promise.all([service.close(),frameService.close(),new Promise(resolve=>redirect.close(resolve)),new Promise(resolve=>fault.close(resolve))]);save();process.exit(0);}
for(const signal of ['SIGINT','SIGTERM'])process.once(signal,close);
