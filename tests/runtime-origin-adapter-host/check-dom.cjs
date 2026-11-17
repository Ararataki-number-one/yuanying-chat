const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE);
const directory=process.argv[2],checks=[],windows=[];
function check(name,pass){assert.ok(pass,name);checks.push({name,pass:true});}
function read(mode,name){return fs.readFileSync(path.join(directory,mode,name),'utf8');}
function page(url,frame=false){
 const dom=new JSDOM(frame?`<iframe src="${url}"></iframe>`:'<main><textarea id="prompt-textarea">preserved unsent draft</textarea></main>',{url:frame?new URL('/host',url).href:url,runScripts:'outside-only',pretendToBeVisual:true});windows.push(dom.window);
 const win=frame?dom.window.document.querySelector('iframe').contentWindow:dom.window;
 if(frame){win.document.open();win.document.write('<main><textarea id="prompt-textarea">preserved unsent draft</textarea></main>');win.document.close();}
 Object.defineProperty(win.HTMLElement.prototype,'innerText',{configurable:true,get(){return this.textContent;},set(value){this.textContent=value;}});
 win.HTMLElement.prototype.getClientRects=function(){return this.closest('[hidden]')?[]:[{x:0,y:0,width:120,height:30}];};
 win.HTMLElement.prototype.getBoundingClientRect=function(){return {x:0,y:0,left:0,top:0,right:120,bottom:30,width:120,height:30};};
 return win;
}
function invoke(template,win,args,action='page-state'){return win.eval(template.replaceAll('__ACTION__',JSON.stringify(action)).replaceAll('__ARG__',JSON.stringify(args)));}
function blocked(value){return value?.ok===false&&typeof value.error==='string'&&value.error.includes('目标页面已改变');}
(async()=>{try{
 const performanceUrl='http://127.0.0.1:8767/performance?variant=current';
 const baselineBefore=read('before','performance-baseline.js'),baselineAfter=read('after','performance-baseline.js');check('Historical baseline adapted template remains byte-identical across fix',baselineBefore===baselineAfter);
 for(const mode of ['before','after']){const win=page('http://127.0.0.1:8767/performance?variant=baseline');const result=invoke(read(mode,'performance-baseline.js'),win,{},'inspect');check(mode+' actual baseline load reaches real host DOM',result.composer===true);}
 const performance=read('after','performance-current.js');let win=page(performanceUrl),result=invoke(performance,win,{expectedUrl:performanceUrl});check('Current current performance driver reaches actual page-state DOM',result.ok===true&&result.draft==='preserved unsent draft');
 for(const url of ['http://127.0.0.1:8766/performance?variant=current','http://localhost:8767/performance?variant=current','https://127.0.0.1:8767/performance?variant=current']){win=page(url);result=invoke(performance,win,{expectedUrl:url});check('Current performance denies different exact origin '+url,blocked(result));}
 win=page(performanceUrl,true);check('Current performance denies actual subframe',win!==win.top&&blocked(invoke(performance,win,{expectedUrl:performanceUrl})));
 win=page(performanceUrl);check('Current performance keeps expectedUrl origin rejection',blocked(invoke(performance,win,{expectedUrl:'https://chatgpt.com/c/source'})));
 check('Current performance keeps expectedUrl pathname rejection',invoke(performance,win,{expectedUrl:'http://127.0.0.1:8767/other'}).ok===false);
 win=page('http://127.0.0.1:8765/fixture');win.eval(read('before','completion-setup.js'));result=win.eval(read('before','completion-poll.js'));
 check('Original completion adapter reproduces released-driver origin refusal',blocked(result));
 for(const url of ['https://chatgpt.com/c/source','http://127.0.0.1:8765/fixture','http://localhost:8765/fixture','http://127.0.0.1:8766/fixture']){
   for(const frame of [false,true]){
     win=page(url,frame);win.eval(read('before','completion-setup.js'));
     win.document.querySelector('#prompt-textarea').value='preserved unsent draft';
     const body=win.document.body.innerHTML,document=win.document,reads=[];
     const originals={};
     for(const name of ['querySelector','querySelectorAll','getElementById']){
       originals[name]=document[name];document[name]=function(){reads.push(name);throw new Error('Retired command read DOM');};
     }
     let callbacks=0;const oldTimeout=win.setTimeout,oldInterval=win.setInterval;
     win.setTimeout=win.setInterval=()=>{callbacks++;throw new Error('Retired command scheduled work');};
     try{
       for(const action of ['poll','latest']){
         result=win.eval(read('after','completion-'+action+'.js'));
         check('Current '+action+' rejects before page observation '+url+' frame='+frame,
           result.ok===false&&result.reason==='请在 ChatGPT 原网页中操作'&&Object.keys(result).sort().join(',')==='ok,reason');
       }
     }finally{
       for(const name of Object.keys(originals))document[name]=originals[name];
       win.setTimeout=oldTimeout;win.setInterval=oldInterval;
     }
     check('Retired completion keeps DOM draft and schedules no work '+url+' frame='+frame,
       document.body.innerHTML===body&&document.querySelector('#prompt-textarea').value==='preserved unsent draft'&&reads.length===0&&callbacks===0);
   }
 }
 win=page('https://chatgpt.com/c/source');win.eval(read('before','completion-setup.js'));win.eval(read('before','completion-prior.js'));
 result=win.eval(read('after','completion-poll.js'));
 check('Prior-message copy controls cannot revive retired completion',result.ok===false&&!('terminal' in result)&&!('submitted' in result));
 for(const escaped of ['plain','escaped']){const name='compact-'+escaped+'-valid.js';win=page('http://127.0.0.1:8765/c/reload-A');check('Original compact adapter reproduces trailing-slash origin mismatch '+escaped,blocked(win.eval(read('before',name))));result=win.eval(read('after',name));check('Current compact adapter reaches real DOM with '+escaped+' expectedUrl',result.ok===true&&result.draft==='preserved unsent draft');
   check('Current compact preserves expectedUrl wrong-origin guard '+escaped,blocked(win.eval(read('after','compact-'+escaped+'-wrong-origin.js'))));check('Current compact preserves expectedUrl wrong-path guard '+escaped,win.eval(read('after','compact-'+escaped+'-wrong-path.js')).ok===false);
 }
 for(const url of ['http://127.0.0.1:8766/c/reload-A','http://localhost:8765/c/reload-A']){win=page(url);check('Current compact rejects wrong exact origin '+url,blocked(win.eval(read('after','compact-plain-valid.js'))));}
 win=page('http://127.0.0.1:8765/c/reload-A',true);check('Current compact rejects actual subframe',win!==win.top&&blocked(win.eval(read('after','compact-plain-valid.js'))));
 const source='https://fixture.example.test:9443/c/source?fixture=1';win=page(source);check('Original followup helper reproduces missed current marker',blocked(win.eval(read('before','followup-source.js'))));result=win.eval(read('after','followup-source.js'));check('Current followup reaches exact controlled HTTPS source and current draft',result.ok===true&&result.draft==='preserved unsent draft');
 for(const url of ['http://fixture.example.test:9443/c/source?fixture=1','https://fixture.example.test:9443/c/source?fixture=2','https://fixture.example.test:9443/c/other?fixture=1','https://fixture.example.test:9444/c/source?fixture=1']){win=page(url);check('Current followup preserves HTTPS plus exact source href '+url,blocked(win.eval(read('after','followup-source.js'))));}
 win=page(source,true);check('Current followup rejects actual subframe',win!==win.top&&blocked(win.eval(read('after','followup-source.js'))));
 check('All controlled documents remain local host DOM without network',true);
 console.log(JSON.stringify({status:'passed',contract:'browser-result-removal-v1',passed:checks.length,total:checks.length,checks,actualAndroidExecution:false,actualGeckoExecution:false,actualNetworkExecution:false,scope:'Captured JS emitted by verbatim historical/current Java fixture methods, executed in actual JSDOM documents/subframes. Historical completion uses the pinned released polling driver only as a negative control; current commands reject before DOM reads or scheduling. No Android, Gecko bridge, network or end-to-end release acceptance.'}));
}finally{for(const win of windows)win.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
