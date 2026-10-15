/* Exact Java test adapter + unchanged production asset; controlled host DOM/HTTP only. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const os=require('node:os'),http=require('node:http'),cp=require('node:child_process');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const root=path.resolve(__dirname,'../..'),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'continuity-adapter-'));
const target='http://127.0.0.1:8765/browser-continuity?command=4',asset=path.join(root,'app/src/main/assets/page-driver.js');
const checks=[],requests=[];let server,win;
function check(name,pass){assert.ok(pass,name);checks.push({name,pass:true});}
function java(tool){return process.env.JAVA_HOME?path.join(process.env.JAVA_HOME,'bin',tool):tool;}
function exec(tool,args){const r=cp.spawnSync(java(tool),args,{encoding:'utf8'});assert.equal(r.status,0,r.stderr||r.stdout);return r;}
function invoke(driver,args,action='page-recover',escaped=false){let json=JSON.stringify(args);if(escaped)json=json.replaceAll('/','\\/');return win.eval(driver.replaceAll('__ACTION__',JSON.stringify(action)).replaceAll('__ARG__',json));}
(async()=>{
  exec('javac',['-encoding','UTF-8','-d',tmp,path.join(root,'tests/gecko/ContinuityDriverAdapter.java'),path.join(root,'tests/browser-runtime/ContinuityDriverAdapterHost.java')]);
  const adaptedFile=path.join(tmp,'adapted.js');exec('java',['-cp',tmp,'local.pocketchat.ContinuityDriverAdapterHost',asset,target,adaptedFile]);
  const adapted=fs.readFileSync(adaptedFile,'utf8'),original=fs.readFileSync(asset,'utf8');
  server=http.createServer((request,response)=>{requests.push({method:request.method,url:request.url});response.writeHead(501,{'Content-Length':'0'});response.end();});
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(8765,'127.0.0.1',resolve);});
  const dom=new JSDOM('<h1>Controlled page continuity</h1><textarea id="prompt-textarea">keep unsent draft</textarea><button id="stop" data-testid="stop-button">Stop</button>',{url:target,runScripts:'outside-only',pretendToBeVisual:true});win=dom.window;
  win.HTMLElement.prototype.getClientRects=function(){return this.closest('[hidden]')?[]:[{x:0,y:0,width:120,height:30}];};
  win.AbortController=AbortController;win.fetch=(url,options)=>fetch(url,options);
  const siteOnly=original.replace("location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'","location.protocol !== 'http:' || location.hostname !== '127.0.0.1' || location.port !== '8765'");
  let result=await invoke(siteOnly,{expectedUrl:'https://chatgpt.com/'});
  check('Site-only adapter reproduces the rejected original CI probe',result.ok===false&&/目标页面已改变/.test(result.error)&&requests.length===0);
  result=await invoke(original,{expectedUrl:'https://chatgpt.com/'});
  check('The unchanged production driver still rejects the controlled HTTP origin',result.ok===false&&/目标页面已改变/.test(result.error)&&requests.length===0);
  for(const escaped of [false,true]){
    const before=requests.length;result=await invoke(adapted,{expectedUrl:'https://chatgpt.com/'},'page-recover',escaped);
    check('Paired adapter reaches actual busy DOM with '+(escaped?'escaped':'plain')+' JSON URL',result.ok===false&&!result.error&&!('probeMs'in result)&&requests.length===before);
  }
  win.document.getElementById('stop').hidden=true;
  for(const escaped of [false,true]){
    const before=requests.length;result=await invoke(adapted,{expectedUrl:'https://chatgpt.com/'},'page-recover',escaped);
    check('Paired adapter reaches real HEAD 501 with '+(escaped?'escaped':'plain')+' JSON URL',result.ok===false&&!result.error&&result.probeMs>=0&&requests.length===before+1&&requests.at(-1).method==='HEAD'&&requests.at(-1).url==='/browser-continuity?command=4');
  }
  let before=requests.length;
  result=await invoke(adapted,{expectedUrl:'https://chatgpt.com/c/wrong'});
  check('Wrong semantic document is rejected before any probe',result.ok===false&&/目标页面已改变/.test(result.error)&&requests.length===before);
  result=await invoke(adapted,{expectedUrl:'http://127.0.0.1:8765/wrong-document'});
  check('Wrong actual document keeps the original pathname rejection',result.ok===false&&!('probeMs'in result)&&requests.length===before);
  result=await invoke(adapted,{expectedUrl:'https://chatgpt.com/'},'page-state');
  check('Only page-recover receives the semantic expected-URL mapping',result.ok===false&&/目标页面已改变/.test(result.error)&&requests.length===before);
  const rejected=cp.spawnSync(java('java'),['-cp',tmp,'local.pocketchat.ContinuityDriverAdapterHost',asset,'http://127.0.0.1:8765/wrong-document',path.join(tmp,'rejected.js')],{encoding:'utf8'});
  check('The adapter refuses a target outside its exact fixture path',rejected.status!==0&&!fs.existsSync(path.join(tmp,'rejected.js')));
  check('The original draft remains intact throughout all controls',win.document.getElementById('prompt-textarea').value==='keep unsent draft');
  console.log(JSON.stringify({status:'passed',passed:checks.length,total:checks.length,checks,actualAndroidExecution:false,actualHttpHeadExecution:true,httpRequests:requests,scope:'Exact integration-only Java adapter and unchanged production asset in host DOM; busy observations and actual local HTTP 501. No Android, ChatGPT account, live proxy or WAN acceptance.'}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{win?.close();if(server?.listening)await new Promise(resolve=>server.close(resolve));fs.rmSync(tmp,{recursive:true,force:true});});
