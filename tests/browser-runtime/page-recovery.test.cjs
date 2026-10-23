/* Exact production page driver; controlled DOM/HEAD only, no account or phone claim. */
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync('app/src/main/assets/page-driver.js','utf8'),checks=[];
const sourceCommit=process.env.GITHUB_SHA||process.env.POCKET_SOURCE_COMMIT||null;
const sourceFiles=Object.fromEntries(['app/src/main/assets/page-driver.js',__filename].map(file=>[file===__filename?'tests/browser-runtime/page-recovery.test.cjs':file,crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
function check(name,pass){assert.ok(pass,name);checks.push({name,pass:true});}
(async()=>{
 const w=new JSDOM('<!doctype html><main><article data-message-author-role="user" data-message-id="u"><div data-user-message-bubble>question</div></article><section><div data-message-author-role="assistant" data-message-id="r"><p>answer</p></div></section></main><textarea id="prompt-textarea"></textarea><button data-testid="send-button">Send</button>',{url:'https://chatgpt.com/c/retained',runScripts:'outside-only',pretendToBeVisual:true}).window;
 w.HTMLElement.prototype.getClientRects=function(){return this.hidden?[]:[{}];};Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.hidden?'':this.textContent;}});w.getComputedStyle=()=>({display:'block',visibility:'visible'});
 const call=(action,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg))),input=w.document.querySelector('textarea'),before=w.location.href;
 let sends=0,head=0;w.document.querySelector('button').onclick=()=>sends++;w.document.cookie='session=synthetic;path=/';
 for(const length of [0,1,299999,300000,300001,600000]){
  const draft='长'.repeat(length);input.value=draft;const result=call('page-state',{expectedUrl:before});
  check('Snapshot reports exact real length '+length,result.ok&&result.draftLength===length&&result.hasDraft===(length>0));
  if(length<=300000)check('In-limit draft is preserved exactly '+length,result.draftComplete&&result.draft===draft&&result.draftOmittedReason==='');
  else check('Oversize draft is explicitly incomplete '+length,result.draftComplete===false&&result.draft===null&&result.draftOmittedReason==='too-long');
  check('Snapshot never edits the browser input '+length,input.value===draft);
 }
 input.value='未发送🙂\n   原始输入';let snapshot=call('page-state',{expectedUrl:before});check('Unicode and line breaks are preserved with UTF-16 length',snapshot.draft===input.value&&snapshot.draftLength===input.value.length&&snapshot.draftComplete);
 input.value='';let result=await call('page-restore',{expectedUrl:before,state:{...snapshot,draft:'older archived text',draftComplete:false},allowDraft:true});check('Incomplete metadata cannot restore an older draft as the current input',!result.ok&&result.reason==='incomplete-draft'&&input.value==='');
 input.remove();snapshot=call('page-state',{expectedUrl:before});check('Missing composer is unknown rather than an empty captured input',snapshot.ok&&snapshot.draftComplete===false&&snapshot.draft===null&&snapshot.draftOmittedReason==='composer-unavailable');w.document.body.append(input);
 input.value='keep exact input';w.AbortController=AbortController;w.fetch=async(url,options)=>{assert.equal(options.method,'HEAD');head++;return {ok:false,status:501};};
 result=await call('page-recover',{expectedUrl:before});check('HEAD failure remains an unsuccessful read-only diagnostic',result.ok===false&&head===1&&result.probeMs>=0);
 check('Failed diagnostic preserves the original document draft and cookie',w.location.href===before&&input.value==='keep exact input'&&w.document.cookie.includes('session=synthetic')&&sends===0);
 const stop=w.document.createElement('button');stop.dataset.testid='stop-button';stop.textContent='Stop';w.document.body.append(stop);
 result=await call('page-recover',{expectedUrl:before});check('Busy page is not refreshed or probed by the page recovery check',result.ok===false&&head===1&&sends===0&&input.value==='keep exact input');stop.remove();
 result=call('page-state',{expectedUrl:'https://chatgpt.com/c/other'});check('Wrong route cannot capture a current document',!result.ok);
 w.close();const executionInputsUnchanged=Object.entries(sourceFiles).every(([file,hash])=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')===hash);assert.ok(executionInputsUnchanged,'source stayed fixed during checks');console.log(JSON.stringify({status:'passed',checks:checks.length,details:checks,sourceCommit,sourceFiles,executionInputsUnchanged,actualProductionDriver:true,actualAndroidExecution:false,scope:'Exact production script in controlled DOM with mocked HEAD; no live website or phone acceptance'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
