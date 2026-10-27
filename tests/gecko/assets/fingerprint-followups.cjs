'use strict';
// Test-only wrapper: the production detector still handles every known audit URL.
const fs=require('node:fs'),https=require('node:https');
const {createIdentityServer,DEFAULT_BASE}=require('../../../tools/fingerprint/request_identity_server.cjs');
const [keyFile,certFile,directory,runNonce]=process.argv.slice(2);
if(!keyFile||!certFile||!directory||!/^[a-f0-9]{32}$/.test(runNonce||''))throw Error('Exact synthetic invocation required');
const host=process.env.POCKETCHAT_FINGERPRINT_FIXTURE_HOST||'10.0.2.2';
if(!['10.0.2.2','127.0.0.1'].includes(host))throw Error('Only explicit synthetic loopback hosts allowed');
const origin='https://'+host+':9889',redirectOrigin='https://'+host+':9890';
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
    '<button data-testid="send-button" disabled>Send</button><pre id="fixture-fetch-result">{}</pre><span id="send-count">0</span><span id="fixture-nonce">'+runNonce+'</span></main>'+
    '<div style="height:1800px">Controlled reading position</div><script>'+
    'document.cookie="fingerprint-preserve='+runNonce+'; Path=/; Secure; SameSite=Lax";'+
    'addEventListener("pocket-fixture-fetch",async event=>{let c;try{c=JSON.parse(event.detail)}catch{return}'+
    'if(!c||!/^[a-f0-9]{32}$/.test(c.nonce)||!'+JSON.stringify([origin,redirectOrigin])+'.includes(c.origin)||!["document","strict-probe","credential-probe","redirect-control"].includes(c.kind))return;'+
    'const path=c.kind==="document"?"'+DEFAULT_BASE+'document":"/"+c.kind;const target=c.origin+path+"?nonce="+c.nonce;'+
    'const out={nonce:c.nonce,phase:c.phase,source:"controlled-page-main-world-fetch",done:false};'+
    'try{const r=await fetch(target,{credentials:"include",redirect:"follow",referrerPolicy:"unsafe-url",headers:c.origin===location.origin?{Authorization:"Bearer fingerprint-fixture-'+runNonce+'"}:{}});out.ok=true;out.status=r.status;await r.text()}catch(e){out.ok=false;out.error=String(e&&e.name||"FetchFailed")}'+
    'out.done=true;document.getElementById("fixture-fetch-result").textContent=JSON.stringify(out);});'+
    '</script>';
}
const service=createIdentityServer({key,cert,output:directory+'/identity-server.json',rawLog:directory+'/identity-server.jsonl',extraHandler(req,res){
  const url=new URL(req.url,'https://detector.invalid');
  if(url.pathname==='/chat'&&url.searchParams.get('runNonce')===runNonce){reply(res,200,chat(),'text/html');return true;}
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
observe(service.server,'detector');observe(redirect,'redirect');
Promise.all([new Promise(resolve=>service.server.listen(9889,'0.0.0.0',resolve)),new Promise(resolve=>redirect.listen(9890,'0.0.0.0',resolve))])
  .then(()=>{save();process.stdout.write(JSON.stringify({ready:true,ports:[9889,9890],runNonce})+'\n');});
async function close(){if(stopping)return;stopping=true;for(const socket of sockets)socket.destroy();await Promise.all([service.close(),new Promise(resolve=>redirect.close(resolve))]);save();process.exit(0);}
for(const signal of ['SIGINT','SIGTERM'])process.once(signal,close);
