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
 const scroll=w.document.querySelector('main');Object.defineProperty(scroll,'scrollHeight',{value:1000});Object.defineProperty(scroll,'clientHeight',{value:100});w.getComputedStyle=()=>({display:'block',visibility:'visible',overflowY:'auto'});
 // Capture the actual scroll geometry and position before changing it. A
 // pre-layout snapshot cannot authorize a pixel fallback after layout changes.
 scroll.scrollTop=120;snapshot=call('page-state',{expectedUrl:before});
 input.value='visible draft stays local to the webpage';scroll.scrollTop=0;
 result=await call('page-restore',{expectedUrl:before,state:{...snapshot,draft:null,draftComplete:false,draftOmittedReason:'local-saving-disabled',scrollTop:120},allowDraft:false,allowScroll:true});
 check('Disabled local draft copies still permit independent scroll recovery',result.ok&&result.restoredDraft===false&&scroll.scrollTop===120&&input.value==='visible draft stays local to the webpage');
 result=await call('page-restore',{expectedUrl:before,state:{...snapshot,draft:'old archived text',draftComplete:false,scrollTop:240},allowDraft:false,allowScroll:false});
 check('Disabled restoration neither inserts retained history nor overrides disabled scroll',result.ok&&result.restoredDraft===false&&scroll.scrollTop===120&&input.value==='visible draft stays local to the webpage');
 input.remove();snapshot=call('page-state',{expectedUrl:before});check('Missing composer is unknown rather than an empty captured input',snapshot.ok&&snapshot.draftComplete===false&&snapshot.draft===null&&snapshot.draftOmittedReason==='composer-unavailable');w.document.body.append(input);
 input.value='keep exact input';w.AbortController=AbortController;w.fetch=async(url,options)=>{assert.equal(options.method,'HEAD');head++;return {ok:false,status:501};};
 result=await call('page-recover',{expectedUrl:before});check('HEAD failure remains an unsuccessful read-only diagnostic',result.ok===false&&head===1&&result.probeMs>=0);
 check('Failed diagnostic preserves the original document draft and cookie',w.location.href===before&&input.value==='keep exact input'&&w.document.cookie.includes('session=synthetic')&&sends===0);
 const stop=w.document.createElement('button');stop.dataset.testid='stop-button';stop.textContent='Stop';w.document.body.append(stop);
 result=await call('page-recover',{expectedUrl:before});check('Busy page is not refreshed or probed by the page recovery check',result.ok===false&&head===1&&sends===0&&input.value==='keep exact input');stop.remove();
 result=call('page-state',{expectedUrl:'https://chatgpt.com/c/other'});check('Wrong route cannot capture a current document',!result.ok);
 for(const direction of ['forward','backward','none']){
  input.value='0123456789';input.focus();input.setSelectionRange(direction==='none'?4:2,direction==='none'?4:5,direction);
  const saved=call('page-state',{expectedUrl:before});input.value='';
  const recovered=await call('page-restore',{expectedUrl:before,state:saved,allowDraft:true,allowScroll:false});
  check('Saved textarea range retains its original '+direction+' direction',recovered.restoredDraft&&recovered.selectionReason==='restored'&&input.selectionStart===(direction==='none'?4:2)&&input.selectionEnd===(direction==='none'?4:5)&&input.selectionDirection===direction);
 }
 input.remove();const editor=w.document.createElement('div');editor.className='ProseMirror';editor.contentEditable='true';editor.setAttribute('contenteditable','true');editor.setAttribute('data-composer-markdown','');editor.tabIndex=0;w.document.body.append(editor);w.document.execCommand=()=>false;
 const rich='<p>前缀🙂<strong>第一行</strong><br>code</p><p>  第二行<br class="ProseMirror-trailingBreak"></p>';
 for(const backward of [false,true]){
  editor.innerHTML=rich;editor.focus();const first=editor.firstChild.firstChild,last=editor.lastChild.firstChild,selection=w.getSelection();
  selection.setBaseAndExtent(backward?last:first,backward?4:2,backward?first:last,backward?2:4);
  const saved=call('page-state',{expectedUrl:before});
  check('Contenteditable paragraph snapshot preserves exact multiline UTF-16 range '+backward,saved.draft==='前缀🙂第一行\ncode\n  第二行'&&saved.draftSelection?.anchor===(backward?17:2)&&saved.draftSelection?.focus===(backward?2:17));
  editor.innerHTML='';const recovered=await call('page-restore',{expectedUrl:before,state:saved,allowDraft:true,allowScroll:false});
  check('Contenteditable recovery resolves the saved '+(backward?'backward':'forward')+' range in its new DOM',recovered.restoredDraft&&recovered.selectionReason==='restored'&&editor.textContent===saved.draft&&selection.anchorNode===editor.firstChild&&selection.focusNode===editor.firstChild&&selection.anchorOffset===(backward?17:2)&&selection.focusOffset===(backward?2:17));
 }
 for(const backward of [false,true]){
  editor.innerHTML='<p>a<br>b</p>';editor.focus();const br=editor.querySelector('br'),last=editor.firstChild.lastChild,selection=w.getSelection();
  selection.setBaseAndExtent(backward?last:br,0,backward?br:last,0);const fragment=selection.getRangeAt(0).cloneContents();
  const saved=call('page-state',{expectedUrl:before});
  check('Direct BR endpoint captures the nonempty newline '+backward,[...fragment.childNodes].map(node=>node.outerHTML||node.textContent).join('')==='<br>'&&saved.draft==='a\nb'&&saved.draftSelection?.anchor===(backward?2:1)&&saved.draftSelection?.focus===(backward?1:2));
  editor.innerHTML='';const recovered=await call('page-restore',{expectedUrl:before,state:saved,allowDraft:true,allowScroll:false});
  check('Direct BR range restores newline and '+(backward?'backward':'forward')+' direction',recovered.selectionReason==='restored'&&!selection.isCollapsed&&selection.toString()==='\n'&&selection.anchorOffset===(backward?2:1)&&selection.focusOffset===(backward?1:2));
 }
 editor.innerHTML='<p>one</p><p><br class="ProseMirror-trailingBreak"></p>';editor.focus();w.getSelection().setBaseAndExtent(editor.lastChild,0,editor.lastChild,0);
 const emptyLine=call('page-state',{expectedUrl:before});editor.innerHTML='';result=await call('page-restore',{expectedUrl:before,state:emptyLine,allowDraft:true,allowScroll:false});
 check('A caret on the final empty source line is preserved',emptyLine.draft==='one\n'&&emptyLine.draftSelection?.anchor===4&&result.selectionReason==='restored'&&w.getSelection().anchorOffset===4);
 editor.innerHTML='<ul><li>unsupported rich list</li></ul>';editor.focus();w.getSelection().setBaseAndExtent(editor.querySelector('li').firstChild,2,editor.querySelector('li').firstChild,5);
 const unsupported=call('page-state',{expectedUrl:before});check('An unknown rich editor shape does not fabricate saved offsets',unsupported.draftComplete&&unsupported.draftSelection===null);
 editor.innerHTML='';result=await call('page-restore',{expectedUrl:before,state:unsupported,allowDraft:true,allowScroll:false});check('Unknown saved range keeps the browser range while preserving the text',result.restoredDraft&&result.selectionReason==='unavailable'&&editor.textContent===unsupported.draft);
 for(const anchor of [-1,300001,null]){
  editor.textContent='';result=await call('page-restore',{expectedUrl:before,state:{...emptyLine,draftSelection:{...emptyLine.draftSelection,anchor}},allowDraft:true,allowScroll:false});
  check('Malformed saved contenteditable offset is ignored '+anchor,result.restoredDraft&&result.selectionReason==='unavailable'&&editor.textContent===emptyLine.draft);
 }
 w.close();const executionInputsUnchanged=Object.entries(sourceFiles).every(([file,hash])=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')===hash);assert.ok(executionInputsUnchanged,'source stayed fixed during checks');console.log(JSON.stringify({status:'passed',checks:checks.length,details:checks,sourceCommit,sourceFiles,executionInputsUnchanged,actualProductionDriver:true,actualAndroidExecution:false,scope:'Exact production script in controlled DOM with mocked HEAD; no live website or phone acceptance'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
