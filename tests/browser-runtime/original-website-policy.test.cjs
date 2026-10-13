/* Actual production script contracts; DOM semantics, not Android performance. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync('app/src/main/assets/page-driver.js','utf8');
const w=new JSDOM('<!doctype html><title>ChatGPT</title><body><button data-testid="model-switcher-dropdown-button" aria-expanded="false">GPT official</button><main><article data-message-author-role="user" data-message-id="u1">Existing question</article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="a1"><div class="markdown"><p>Existing answer</p></div></div></section></main><textarea id="prompt-textarea">  old draft\nkeep every character  </textarea><button data-testid="send-button" aria-label="Send">Send</button><input type="file" id="upload-photos" accept="image/*">',{url:'https://chatgpt.com/c/original-fixture',runScripts:'outside-only'}).window;
Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
w.Element.prototype.getClientRects=()=>[{}];w.getComputedStyle=()=>({display:'block',visibility:'visible',overflowY:'auto'});
let sends=0,inputs=0;w.document.querySelector('[data-testid="send-button"]').addEventListener('click',()=>sends++);
const composer=w.document.querySelector('textarea');composer.addEventListener('input',()=>inputs++);
w.document.cookie='session=original-preserved;Path=/';
const call=(action,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));
const checks=[],check=(name,pass)=>{assert.ok(pass,name);checks.push({name,pass:true});};
async function recoveryRace(name,mutate,verify,editable=false){
 const editor=editable?'<div contenteditable="true" data-composer-markdown tabindex="0"></div>':'<textarea id="prompt-textarea"></textarea>';
 const win=new JSDOM('<!doctype html><body><main id="scroll"><article data-message-author-role="user">Existing question</article></main>'+editor+'<button id="outside">Other control</button>',{url:'https://chatgpt.com/c/recovery-race',runScripts:'outside-only'}).window;
 Object.defineProperty(win.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
 win.Element.prototype.getClientRects=()=>[{}];win.getComputedStyle=()=>({display:'block',visibility:'visible',overflowY:'auto'});
 const doc=win.document,input=doc.querySelector(editable?'[contenteditable]':'textarea'),scroll=doc.getElementById('scroll'),text='exact saved draft',invoke=(action,arg={})=>win.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));
 Object.defineProperty(scroll,'scrollHeight',{value:1000});Object.defineProperty(scroll,'clientHeight',{value:100});scroll.scrollTop=40;
 if(editable){input.textContent=text;doc.execCommand=()=>false;}else input.value=text;input.focus();if(!editable)input.setSelectionRange(4,4);
 const saved=invoke('page-state',{expectedUrl:win.location.href});if(editable)input.textContent='';else input.value='';scroll.scrollTop=0;
 const types=new Set(['pointerdown','keydown','beforeinput','input','compositionstart','compositionupdate','compositionend','wheel','select','selectionchange','focusin','focusout']),listeners=new Map();let added=0,removed=0,trustedSelections=0;
 input.addEventListener('select',event=>{if(event.isTrusted)trustedSelections++;});
 win.addEventListener('selectionchange',event=>{if(event.isTrusted)trustedSelections++;},true);
 const add=doc.addEventListener,remove=doc.removeEventListener;
 doc.addEventListener=function(type,listener,...rest){if(types.has(type)){if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(listener);added++;}return add.call(this,type,listener,...rest);};
 doc.removeEventListener=function(type,listener,...rest){if(types.has(type)&&listeners.get(type)?.delete(listener))removed++;return remove.call(this,type,listener,...rest);};
 const ctx={win,doc,input,scroll,text,saved,invoke,listeners,foreign:null,emit(type,trusted){const registered=[...(listeners.get(type)||[])];assert.ok(registered.length,'Production restoration listener for '+type);for(const listener of registered)listener({type,isTrusted:trusted});}};
 try{
  const pending=invoke('page-restore',{expectedUrl:win.location.href,state:saved,allowDraft:true,allowScroll:true}).then(result=>({result}),error=>({error}));
  const mutation=mutate?new Promise((resolve,reject)=>win.setTimeout(()=>{try{mutate(ctx);resolve();}catch(error){reject(error);}},10)):Promise.resolve();
  const [{result,error}]=await Promise.all([pending,mutation]);
  check(name,verify({...ctx,result,error,trustedSelections}));
  check(name+' removes every temporary document listener',added>0&&added===removed&&[...listeners.values()].every(value=>value.size===0));
 }finally{ctx.foreign?.close();win.close();}
}
(async()=>{
 const before=w.document.body.innerHTML,draft=composer.value;
 for(const action of ['fill','submit','model-open','model-options','model-catalog-open','model-select','slider-focus','slider-set','message-regenerate-prepare','message-regenerate-submit','history-sync','history-rename','history-delete','history-older','page-navigate','attachment-open','attachment-remove','unknown-action']){
  const result=await call(action,{text:'replacement',value:9,url:'https://chatgpt.com/c/different',expectedUrl:w.location.href});
  check('Original website rejects native '+action,result?.ok===false&&/原网页/.test(result.reason)&&composer.value===draft&&w.document.body.innerHTML===before&&sends===0&&inputs===0);
 }
 const saved=call('page-state',{expectedUrl:w.location.href});
 check('Browser snapshot keeps the exact original draft and route',saved.ok&&saved.draft===draft&&saved.url===w.location.href);
 composer.value='newer draft typed on the official website';let result=await call('page-restore',{expectedUrl:w.location.href,state:saved,allowDraft:true,allowScroll:false});
 check('Browser recovery never overwrites a newer official draft',result.ok&&result.conflict&&composer.value==='newer draft typed on the official website'&&sends===0);
 composer.value='';result=await call('page-restore',{expectedUrl:w.location.href,state:saved,allowDraft:false,allowScroll:false});
 check('An active reply can prohibit draft restoration',result.ok&&!result.restoredDraft&&composer.value===''&&sends===0);
 result=await call('page-restore',{expectedUrl:'https://chatgpt.com/c/different',state:saved,allowDraft:true});
 check('A different conversation cannot receive the saved draft',!result.ok&&composer.value===''&&sends===0);
 w.__pocketWebReplyObserver={lastGestureAt:()=>1};result=await call('page-restore',{expectedUrl:w.location.href,state:saved,allowDraft:true});
 check('A newer trusted website gesture prevents restoring older browser input',!result.ok&&result.reason==='new-gesture'&&composer.value===''&&sends===0);
 delete w.__pocketWebReplyObserver;result=await call('page-restore',{expectedUrl:w.location.href,state:saved,allowDraft:true,allowScroll:false});
 check('Safe browser recovery restores an empty draft exactly without submitting',result.ok&&result.restoredDraft&&composer.value===draft&&sends===0&&inputs===1);
 check('Original title, model control, file input and account cookie remain intact',w.document.title==='ChatGPT'&&w.document.querySelector('[data-testid="model-switcher-dropdown-button"]').outerHTML===before.slice(0,before.indexOf('<main>'))&&!!w.document.getElementById('upload-photos')&&w.document.cookie.includes('session=original-preserved'));
 await recoveryRace('Uninterrupted recovery ignores its own queued selection events and restores the saved caret',null,({result,input,scroll,text})=>result.ok&&result.restoredDraft&&!result.interacted&&input.value===text&&input.selectionStart===4&&input.selectionEnd===4&&scroll.scrollTop===40);
 await recoveryRace('Selection-only movement during recovery preserves the new caret and unchanged text',({input})=>input.setSelectionRange(2,2),({result,input,scroll,text,trustedSelections})=>trustedSelections>0&&result.ok&&result.restoredDraft&&result.interacted&&input.value===text&&input.selectionStart===2&&input.selectionEnd===2&&scroll.scrollTop===0);
 await recoveryRace('Selection-only range change preserves its direction during recovery',({input})=>input.setSelectionRange(2,6,'backward'),({result,input,text})=>result.ok&&result.interacted&&input.value===text&&input.selectionStart===2&&input.selectionEnd===6&&input.selectionDirection==='backward');
 await recoveryRace('Typing during recovery preserves the newer text and caret',({input,win})=>{input.value='new text typed during recovery';input.setSelectionRange(3,3);input.dispatchEvent(new win.InputEvent('input',{bubbles:true,inputType:'insertText',data:'new text'}));},({result,input})=>result.ok&&!result.restoredDraft&&result.interacted&&input.value==='new text typed during recovery'&&input.selectionStart===3);
 // JSDOM supplies real trusted select/focus events above. These cases
 // directly exercise production callbacks with synthetic host gesture records;
 // they are not actual Android keyboard, pointer or beforeinput evidence.
 for(const type of ['pointerdown','keydown','beforeinput','input','compositionstart','compositionupdate','compositionend','wheel'])await recoveryRace('Synthetic host trusted '+type+' cancels stale caret restoration',ctx=>{if(type==='wheel')ctx.scroll.scrollTop=77;ctx.emit(type,true);},({result,input,scroll,text})=>result.ok&&result.interacted&&input.value===text&&input.selectionStart===text.length&&scroll.scrollTop===(type==='wheel'?77:0));
 await recoveryRace('Untrusted synthetic gestures do not prevent otherwise safe restoration',ctx=>{for(const type of ['pointerdown','keydown','beforeinput'])ctx.emit(type,false);},({result,input})=>result.ok&&!result.interacted&&input.selectionStart===4);
 await recoveryRace('Changing focused control during recovery preserves the new focus',({doc})=>doc.getElementById('outside').focus(),({result,input,doc,text})=>result.ok&&result.interacted&&doc.activeElement===doc.getElementById('outside')&&input.value===text&&input.selectionStart===text.length);
 await recoveryRace('Replacing the composer prevents old recovery from changing the replacement',({input})=>{const next=input.cloneNode(false);next.value='replacement draft';input.replaceWith(next);},({result,input,doc,text})=>!result.ok&&result.reason==='composer'&&doc.querySelector('textarea').value==='replacement draft'&&input.selectionStart===text.length);
 await recoveryRace('A changed document identity rejects the old recovery',({win})=>{win.__pocketDocumentId='new-document-identity';},({result,input,text})=>!result.ok&&result.reason==='route'&&input.selectionStart===text.length);
 await recoveryRace('Moving the old composer to another document cannot carry its recovery listeners',ctx=>{ctx.foreign=new JSDOM('<!doctype html><body>').window;ctx.foreign.document.body.append(ctx.foreign.document.adoptNode(ctx.input));ctx.input.setSelectionRange(1,1);const next=ctx.doc.createElement('textarea');next.id='prompt-textarea';next.value='fresh document draft';ctx.doc.body.append(next);},({result,input,doc,foreign})=>!result.ok&&result.reason==='composer'&&input.ownerDocument===foreign.document&&input.selectionStart===1&&doc.querySelector('textarea').value==='fresh document draft');
 await recoveryRace('Conversation navigation rejects the in-progress recovery',({win})=>win.history.pushState(null,'','/c/other-conversation'),({result,input,text})=>!result.ok&&result.reason==='route'&&input.selectionStart===text.length);
 await recoveryRace('A reply starting during recovery prevents late caret application',({doc})=>{const stop=doc.createElement('button');stop.dataset.testid='stop-button';doc.body.append(stop);},({result,input,text})=>!result.ok&&result.reason==='page-state'&&input.selectionStart===text.length);
 await recoveryRace('A failing DOM read still removes the restoration listeners',({input})=>Object.defineProperty(input,'value',{get(){throw new Error('Controlled DOM read failure');}}),({error})=>error?.message==='Controlled DOM read failure');
 await recoveryRace('Uninterrupted contenteditable recovery keeps the full draft and restores scrolling',null,({result,input,scroll,text})=>result.ok&&result.restoredDraft&&!result.interacted&&input.textContent===text&&scroll.scrollTop===40,true);
 await recoveryRace('A new contenteditable selection keeps its anchor and offset during recovery',({input,doc,win})=>{const range=doc.createRange();range.setStart(input.firstChild,2);range.setEnd(input.firstChild,6);const selection=win.getSelection();selection.removeAllRanges();selection.addRange(range);},({result,input,scroll,win,text,trustedSelections})=>trustedSelections>0&&result.ok&&result.interacted&&input.textContent===text&&win.getSelection().anchorNode===input.firstChild&&win.getSelection().anchorOffset===2&&win.getSelection().focusOffset===6&&scroll.scrollTop===0,true);
 await recoveryRace('A website error during recovery prevents late caret and scroll restoration',({doc})=>{const error=doc.createElement('div');error.setAttribute('role','alert');error.textContent='Something went wrong';doc.body.append(error);},({result,input,scroll,text})=>!result.ok&&result.reason==='page-state'&&input.selectionStart===text.length&&scroll.scrollTop===0);
 console.log(JSON.stringify({status:'passed',validationScope:'Production original-website DOM contracts; JSDOM selection/focus and explicitly synthetic host gesture callbacks; no Android runtime, hardware-input repair or performance claim',passed:checks.length,total:checks.length,checks}));w.close();
})().catch(error=>{w.close();console.error(error);process.exitCode=1;});
