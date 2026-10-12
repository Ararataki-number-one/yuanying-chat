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
 console.log(JSON.stringify({status:'passed',validationScope:'Production original-website DOM contracts; no Android runtime or performance claim',passed:checks.length,total:checks.length,checks}));w.close();
})().catch(error=>{w.close();console.error(error);process.exitCode=1;});
