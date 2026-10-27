'use strict';
// Actual loopback TLS + production scope helper. WebRequest/Port are VM doubles.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm'),https=require('node:https'),cp=require('node:child_process'),crypto=require('node:crypto');
const {createIdentityServer}=require('../../tools/fingerprint/request_identity_server.cjs');
const ROOT=path.resolve(__dirname,'../..'),HELPER=path.join(ROOT,'app/src/main/assets/gecko/request-identity-background.js'),PROTOCOL='pocketchat-request-identity-v1';
const SOURCE_FILES=[HELPER,path.join(ROOT,'tools/fingerprint/request_identity_server.cjs')];
const sourceHashes=()=>Object.fromEntries(SOURCE_FILES.map(file=>[path.relative(ROOT,file),crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
const INPUT_HASHES=sourceHashes();
function api(fetcher){
 const listeners={onBeforeRequest:[],onBeforeSendHeaders:[],onHeadersReceived:[]},browser={webRequest:{}};
 for(const [key,list] of Object.entries(listeners))browser.webRequest[key]={addListener(fn){list.push(fn);},removeListener(fn){const i=list.indexOf(fn);if(i>=0)list.splice(i,1);}};
 const context=vm.createContext({URL,Date,Uint8Array,TextDecoder,AbortController,setTimeout,clearTimeout,browser,fetch:(url,options)=>fetcher(url,options,listeners)});vm.runInContext(fs.readFileSync(HELPER,'utf8'),context,{filename:'request-identity-background.js'});return context.PocketRequestIdentityBackground;
}
function request(url,ca,headers={},signal){
 return new Promise((resolve,reject)=>{const req=https.get(url,{ca,headers,signal,agent:false},res=>resolve(res));req.on('error',reject);});
}
async function jsonRequest(url,ca,headers){const res=await request(url,ca,headers);const parts=[];for await(const chunk of res)parts.push(chunk);return {status:res.statusCode,body:JSON.parse(Buffer.concat(parts).toString())};}
async function listen(server){await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));return 'https://127.0.0.1:'+server.address().port+'/pocketchat-identity/v1/';}
async function close(server){server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
function transport(ca,records){return async(url,options,listeners)=>{
 let details={url,method:'GET'};for(const fn of listeners.onBeforeRequest)if(fn(details).cancel)throw new TypeError('VM-scoped request denied');
 const sentinel=[{name:'Cookie',value:'tls-fixture-only'},{name:'Authorization',value:'Bearer tls-fixture-only'},{name:'Referer',value:'https://chatgpt.com/c/tls-fixture'},{name:'Origin',value:'moz-extension://tls-fixture'},{name:'User-Agent',value:'TLSProbe/157'},{name:'Accept-Language',value:'ja-JP,en-US;q=0.8'}];let headers=sentinel;
 for(const fn of listeners.onBeforeSendHeaders){const result=fn({...details,requestHeaders:headers});if(result.cancel)throw new TypeError('VM-scoped headers denied');if(result.requestHeaders)headers=result.requestHeaders;}
 const res=await request(url,ca,Object.fromEntries(headers.map(x=>[x.name,x.value])),options.signal);records.push({status:res.statusCode,authorized:res.socket.authorized,headerNames:headers.map(x=>x.name)});
 for(const fn of listeners.onHeadersReceived)if(fn({...details,statusCode:res.statusCode}).cancel){res.destroy();throw new TypeError('VM-scoped redirect denied');}
 const iterator=res[Symbol.asyncIterator]();return {status:res.statusCode,body:{getReader:()=>({async read(){const next=await iterator.next();return next.done?{done:true}:{done:false,value:next.value};},async cancel(){res.destroy();},releaseLock(){}})}};
};}
const capability=(nonce)=>({schema:1,protocol:PROTOCOL,nonce,source:'controlled-service-capabilities',status:'ready',capabilities:{topLevelDocument:true,dedicatedWorker:true,boundedWorkerReply:true,crossOriginFrame:false},limits:{checkTtlMs:30000,maxConcurrentChecks:64,maxCheckEvents:12,workerResponseBytes:8192}});
test('real TLS service capability arrivals and bounded failures retain exact sources',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'service-probe-tls-')),keyPath=path.join(dir,'key.pem'),certPath=path.join(dir,'cert.pem');
 const generated=cp.spawnSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',keyPath,'-out',certPath,'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1'],{encoding:'utf8'});assert.equal(generated.status,0,'Generate short-lived explicit loopback CA');
 const key=fs.readFileSync(keyPath),cert=fs.readFileSync(certPath),reference=createIdentityServer({key,cert,maxChecks:1});let mode='valid';
 const custom=https.createServer({key,cert},(req,res)=>{const url=new URL(req.url,'https://fixture.invalid'),nonce=url.searchParams.get('nonce');if(mode==='timeout')return;if(mode==='redirect'){res.writeHead(302,{Location:'/outside'});res.end();return;}res.writeHead(mode==='capacity'?503:200,{'Content-Type':'application/json'});if(mode==='oversize'){res.end(JSON.stringify({padding:'x'.repeat(17000)}));return;}if(mode==='malformed'){res.end('not JSON');return;}res.end(JSON.stringify(mode==='capacity'?{status:'unavailable'}:capability(nonce)));});
 const checks=[],arrivals=[],records=[];const check=(name,ok)=>{checks.push({name,pass:!!ok});assert.ok(ok,name);};
 reference.server.prependListener('request',req=>arrivals.push({path:new URL(req.url,'https://fixture.invalid').pathname,sensitive:['cookie','authorization','proxy-authorization','referer','origin'].some(x=>req.headers[x]!==undefined),uaPresent:req.headers['user-agent']!==undefined,languagePresent:req.headers['accept-language']!==undefined}));
 try{
  const base=await listen(reference.server),badBase=await listen(custom),nonce=crypto.randomBytes(16).toString('hex');
  const positive=await jsonRequest(base+'capabilities?nonce='+nonce,cert,{Cookie:'tls-fixture-only'});check('real service rejects sensitive-header positive control',positive.status===403&&positive.body.reason==='credential-header-observed');
  const helper=api(transport(cert,records));const ack=helper.handle({action:'register',purpose:'capabilities',endpoint:base,nonce});check('actual production helper acknowledges capability-only scope',ack.ok&&ack.purpose==='capabilities');
  const ready=await helper.handle({action:'capabilities',endpoint:base,nonce});check('real reference service readiness is returned separately',ready.ok&&ready.httpStatus===200&&ready.service.protocol===PROTOCOL&&ready.service.nonce===nonce&&ready.service.capabilities.topLevelDocument===true);check('transport has explicit trusted CA verification',records[0].authorized===true);check('helper strips sensitive headers before actual TLS reception',arrivals.length===2&&arrivals[0].sensitive===true&&arrivals[1].sensitive===false&&arrivals[1].uaPresent&&arrivals[1].languagePresent);check('response reports actual bounded byte count',Number.isInteger(ready.responseBytes)&&ready.responseBytes>0&&ready.responseBytes<=16384);helper.handle({action:'cancel',nonce});const after=await helper.handle({action:'capabilities',endpoint:base,nonce});check('cancelled scope causes no further actual TLS request',after.ok===false&&arrivals.length===2);
  const occupied=crypto.randomBytes(16).toString('hex'),doc=await request(base+'document?nonce='+occupied,cert);for await(const chunk of doc){};const busyNonce=crypto.randomBytes(16).toString('hex'),busy=api(transport(cert,records));busy.handle({action:'register',purpose:'capabilities',endpoint:base,nonce:busyNonce});const full=await busy.handle({action:'capabilities',endpoint:base,nonce:busyNonce});check('real service capacity error retains HTTP and typed payload',full.ok&&full.httpStatus===429&&full.service.reason==='detector-capacity');busy.clear();
  for(const scenario of ['valid','oversize','malformed','redirect','capacity','timeout']){
   mode=scenario;const token=crypto.randomBytes(16).toString('hex'),h=api(transport(cert,records));h.handle({action:'register',purpose:'capabilities',endpoint:badBase,nonce:token});const value=await h.handle({action:'capabilities',endpoint:badBase,nonce:token});
   const expected={valid:v=>v.ok&&v.service.nonce===token,oversize:v=>!v.ok&&v.error==='service-response-too-large',malformed:v=>!v.ok&&v.error==='service-json-invalid',redirect:v=>!v.ok&&v.error==='service-connection-or-certificate-unavailable',capacity:v=>v.ok&&v.httpStatus===503,timeout:v=>!v.ok&&v.error==='service-timeout'};check('actual TLS '+scenario+' behavior is classified',expected[scenario](value));h.clear();
  }
  assert.deepEqual(sourceHashes(),INPUT_HASHES,'Actual helper and server inputs remain unchanged');
  const output=path.join(ROOT,'work/coverage-service/tls-results.json');fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify({schema:1,status:'passed',checks,arrivals,transportRecords:records,actualHttpsLoopbackExecution:true,actualBrowserExecution:false,actualAndroidExecution:false,actualGeckoExecution:false,webRequestIsVmDouble:true,executionInputsUnchanged:true,scope:'Production helper and owned reference server over real trusted loopback TLS; no real Gecko proxy admission, public service or phone proof',sourceSha256:INPUT_HASHES},null,2)+'\n');
 }finally{await Promise.all([reference.close(),close(custom)]);fs.rmSync(dir,{recursive:true,force:true});}
});
