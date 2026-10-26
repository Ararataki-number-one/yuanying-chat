// Controlled author CSS and DOM boundaries; no live ChatGPT/Gecko/pixel claim.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync(process.env.APPEARANCE_SCRIPT||'app/src/main/assets/gecko/appearance.js','utf8');
const bright='html,body,main,form,textarea{background:rgb(252,252,252);color:rgb(13,13,13)}';
const dark='html,body,main,form,textarea{background:rgb(24,24,24);color:rgb(238,238,238)}';
const pause=()=>new Promise(resolve=>setTimeout(resolve,0));

function page(t,{css=bright,theme='light',depth=0,overlay=false,viewport,adopted=false,nonce='',url='https://chatgpt.com/c/controlled'}={}){
  const dom=new JSDOM('<!doctype html><html class="light other-class" data-theme="'+theme+'"><head><style'+(nonce?' nonce="'+nonce+'"':'')+'>'+css+'</style></head><body>'+ '<div>'.repeat(depth)+
    '<main><header>Header</header><p id="reply">Original response</p><form><textarea id="prompt-textarea">Unsent controlled draft</textarea><button style="color:rgb(5,100,220)">Accent</button><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="><pre><code style="color:rgb(180,40,100)">syntax</code></pre></form></main>'+'</div>'.repeat(depth)+'</body></html>',
    {url,runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window;let styleReads=0;const getStyle=w.getComputedStyle.bind(w);
  w.getComputedStyle=(...args)=>{styleReads++;return getStyle(...args)};
  const hits=[];
  Object.defineProperty(w,'visualViewport',{value:viewport||{offsetLeft:0,offsetTop:0,width:360,height:600,scale:1}});
  w.HTMLElement.prototype.getBoundingClientRect=function(){return this.id==='prompt-textarea'?{left:10,right:350,top:400,bottom:460,width:340,height:60}:{left:0,right:360,top:0,bottom:500,width:360,height:500}};
  let cover;
  if(overlay){cover=w.document.createElement('div');cover.style.background='white';w.document.body.append(cover)}
  w.document.elementFromPoint=(x,y)=>{hits.push({x,y});return cover||(y>=400&&y<=460?w.document.querySelector('textarea'):w.document.querySelector('main'))};
  const sheets=[];
  if(adopted){w.CSSStyleSheet=class{constructor(){sheets.push(this)}replaceSync(text){this.text=text}};Object.defineProperty(w.document,'adoptedStyleSheets',{value:[],writable:true})}
  w.localStorage.setItem('theme','light');w.localStorage.setItem('unrelated','keep');w.document.cookie='session=controlled';
  w.eval(source);
  t.after(()=>{w.dispatchEvent(new w.Event('pagehide'));w.close()});
  return {w,hits,sheets,styleReads:()=>styleReads};
}
function observed(w,version=1,dark=true){
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('Original bounded observation missing')),1500);
    const accepted=w.PocketAppearance.synchronize({protocol:1,documentId:'compatibility-document-1234',version,dark},r=>{if(r.stage==='observed'){clearTimeout(timer);resolve(r)}});
    if(!accepted){clearTimeout(timer);reject(Error('Native command rejected'))}
  });
}
function ownStyles(w){return w.document.querySelectorAll('style[data-pocket-appearance-sheet]')}

test('same persisted native choice sends an actual StorageEvent once per command; observer repair does not',async t=>{
  const {w}=page(t);w.localStorage.setItem('theme','dark');const events=[];
  w.addEventListener('storage',event=>{
    events.push(event);const bg=event.newValue==='dark'?'rgb(24,24,24)':'rgb(252,252,252)',fg=event.newValue==='dark'?'rgb(238,238,238)':'rgb(13,13,13)';
    for(const e of w.document.querySelectorAll('html,body,main,form,textarea')){e.style.backgroundColor=bg;e.style.color=fg}
  });
  const first=await observed(w);assert.equal(first.colorStatus,'verified');assert.equal(first.compatibilityApplied,false);
  assert.equal(events.length,1);assert.ok(events[0] instanceof w.StorageEvent);assert.equal(events[0].key,'theme');assert.equal(events[0].oldValue,'dark');assert.equal(events[0].newValue,'dark');assert.equal(events[0].storageArea,w.localStorage);
  w.document.documentElement.classList.remove('dark');await pause();assert.equal(events.length,1);
  await observed(w,2);assert.equal(events.length,2);assert.equal(ownStyles(w).length,0);
});

test('normal data-theme selectors work first without compatibility, and custom theme values remain untouched',async t=>{
  const css=bright+'html[data-theme="dark"],html[data-theme="dark"] body,html[data-theme="dark"] main,html[data-theme="dark"] form,html[data-theme="dark"] textarea{background:rgb(24,24,24);color:rgb(238,238,238)}';
  const {w}=page(t,{css,theme:'system'});const receipt=await observed(w);assert.equal(w.document.documentElement.dataset.theme,'dark');assert.equal(receipt.colorStatus,'verified');assert.equal(receipt.compatibilityApplied,false);
  w.document.documentElement.setAttribute('data-theme','system');await pause();assert.equal(w.document.documentElement.dataset.theme,'dark');
  w.document.documentElement.setAttribute('data-theme','solarized');await pause();assert.equal(w.document.documentElement.dataset.theme,'solarized');
});

test('author bright CSS with no artificial dark rule uses one color-only fallback and preserves the editor and accents',async t=>{
  const {w}=page(t);const input=w.document.querySelector('textarea'),image=w.document.querySelector('img');input.focus();input.setSelectionRange(2,7);
  const receipt=await observed(w);assert.equal(receipt.colorStatus,'verified');assert.equal(receipt.compatibilityApplied,true);assert.equal(ownStyles(w).length,1);
  assert.equal(w.document.activeElement,input);assert.equal(w.document.querySelector('textarea'),input);assert.equal(input.value,'Unsent controlled draft');assert.equal(input.selectionStart,2);assert.equal(input.selectionEnd,7);assert.equal(w.document.querySelector('img'),image);
  assert.equal(w.getComputedStyle(w.document.querySelector('button')).color,'rgb(5, 100, 220)');assert.equal(w.getComputedStyle(w.document.querySelector('code')).color,'rgb(180, 40, 100)');assert.equal(w.localStorage.getItem('unrelated'),'keep');assert.equal(w.document.cookie,'session=controlled');
  const sheet=ownStyles(w)[0];assert.ok(!/(?:width|height|margin|padding|position|font|filter)\s*:/.test(sheet.textContent));assert.ok(!/\*\s*\{/.test(sheet.textContent));assert.ok(w.document.querySelector('form').hasAttribute('data-pocket-appearance-composer'));
  const repeated=observed(w,2,true);assert.equal(w.document.documentElement.getAttribute('data-pocket-appearance-compat'),'dark','same-mode native requests must not flash back to author white');await repeated;assert.equal(ownStyles(w).length,1);
  const light=await observed(w,3,false);assert.equal(light.colorStatus,'verified');assert.equal(light.compatibilityApplied,false);assert.ok(!w.document.documentElement.hasAttribute('data-pocket-appearance-compat'));assert.ok(!w.document.querySelector('form').hasAttribute('data-pocket-appearance-composer'));assert.equal(ownStyles(w)[0],sheet);
});

test('opposite static dark author CSS receives a light compatibility palette',async t=>{
  const {w}=page(t,{css:dark});const receipt=await observed(w,1,false);assert.equal(receipt.colorStatus,'verified');assert.equal(receipt.compatibilityApplied,true);assert.equal(w.document.documentElement.getAttribute('data-pocket-appearance-compat'),'light');
});

test('both root and body must actually be opposite before compatibility can activate',async t=>{
  for(const css of [bright+'html{background:rgb(24,24,24)}',bright+'body{background:rgb(24,24,24)}']){
    const {w}=page(t,{css});const receipt=await observed(w);assert.equal(receipt.colorStatus,'mismatch');assert.equal(receipt.compatibilityApplied,false);assert.equal(ownStyles(w).length,0);
  }
});

test('an actual white main inside an already dark root/body remains a failing negative control',async t=>{
  const {w}=page(t,{css:dark+'main{background:white!important}'});const receipt=await observed(w);assert.equal(receipt.colorStatus,'mismatch');assert.equal(receipt.reason,'color-mismatch');assert.equal(receipt.compatibilityApplied,false);assert.equal(receipt.samples.find(r=>r.region==='main').backgroundLuminance,1);
});

test('unknown transparent canvas cannot trigger an assumed compatibility color',async t=>{
  const {w}=page(t,{css:'html,body,main,form,textarea{background:transparent;color:rgb(13,13,13)}'});const receipt=await observed(w);assert.equal(receipt.colorStatus,'unavailable');assert.equal(receipt.compatibilityApplied,false);assert.equal(ownStyles(w).length,0);
});

test('deep opaque chat is measured using a shared finite ancestor style cache',async t=>{
  const value=page(t,{css:dark,depth:40});const receipt=await observed(value.w);assert.equal(receipt.colorStatus,'verified');assert.ok(receipt.samples.filter(r=>['main','composer'].includes(r.region)).every(r=>r.visible));assert.ok(value.styleReads()<65);
});

test('ancestor budget exhaustion stays unavailable rather than claiming visibility',async t=>{
  const value=page(t,{css:dark,depth:270});const receipt=await observed(value.w);assert.equal(receipt.colorStatus,'unavailable');assert.ok(receipt.samples.filter(r=>['main','composer'].includes(r.region)).every(r=>!r.visible));assert.ok(value.styleReads()<=512);
});

test('single-center overlay remains conservatively unavailable',async t=>{
  const {w}=page(t,{css:dark,overlay:true});const receipt=await observed(w);assert.equal(receipt.colorStatus,'unavailable');assert.ok(receipt.samples.filter(r=>['main','composer'].includes(r.region)).every(r=>!r.visible));
});

test('native dark background with nearly black text is not confirmed',async t=>{
  const {w}=page(t,{css:'html,body,main,form,textarea{background:rgb(24,24,24);color:rgb(13,13,13)}'});const receipt=await observed(w);assert.equal(receipt.colorStatus,'mismatch');assert.equal(receipt.reason,'color-contrast');assert.equal(receipt.compatibilityApplied,false);
});

test('foreground alpha uses the measured background for actual contrast',async t=>{
  const {w}=page(t,{css:'html,body,main,form,textarea{background:rgb(24,24,24);color:rgba(255,255,255,.5)}'});const receipt=await observed(w);assert.equal(receipt.colorStatus,'verified');const sample=receipt.samples.find(r=>r.region==='main');assert.ok(sample.foregroundLuminance>.2&&sample.foregroundLuminance<.35);
});

test('low alpha text remains a contrast failure',async t=>{
  const {w}=page(t,{css:'html,body,main,form,textarea{background:rgb(24,24,24);color:rgba(255,255,255,.1)}'});const receipt=await observed(w);assert.equal(receipt.colorStatus,'mismatch');assert.equal(receipt.reason,'color-contrast');
});

test('constructed-sheet API is preferred and its marker never substitutes for real computed colors',async t=>{
  const {w,sheets}=page(t,{adopted:true});const first=await observed(w);assert.equal(first.compatibilityApplied,true);assert.equal(first.colorStatus,'mismatch');assert.equal(sheets.length,1);assert.equal(w.document.adoptedStyleSheets.length,1);assert.equal(ownStyles(w).length,0);
  await observed(w,2);assert.equal(sheets.length,1);assert.equal(w.document.adoptedStyleSheets.length,1);
});

test('fallback style is reused after root replacement rather than duplicated',async t=>{
  const {w}=page(t);await observed(w);const root=w.document.documentElement.cloneNode(true);w.document.documentElement.replaceWith(root);await pause();const receipt=await observed(w,2);assert.equal(receipt.colorStatus,'verified',JSON.stringify(receipt));assert.equal(ownStyles(w).length,1);
});

test('a removed fallback sheet is reattached once at the next existing observation',async t=>{
  const {w}=page(t);await observed(w);const sheet=ownStyles(w)[0];sheet.remove();const receipt=await observed(w,2);assert.equal(receipt.colorStatus,'verified');assert.equal(ownStyles(w).length,1);assert.equal(ownStyles(w)[0],sheet);
});

test('fallback style copies the same page nonce without putting it in receipts',async t=>{
  const nonce='controlled-page-nonce-not-a-receipt';const {w}=page(t,{nonce});const receipt=await observed(w);assert.equal(receipt.colorStatus,'verified');assert.equal(ownStyles(w)[0].nonce,nonce);assert.ok(!JSON.stringify(receipt).includes(nonce));assert.ok(!ownStyles(w)[0].textContent.includes(nonce));
});

test('preserved background images and transparent ancestor image layers cannot be confirmed from backgroundColor',async t=>{
  const {w}=page(t,{css:bright+'main{background-image:linear-gradient(white,white)}'});const reply=w.document.getElementById('reply');w.document.elementFromPoint=(x,y)=>y>=400?w.document.querySelector('textarea'):reply;const receipt=await observed(w);assert.equal(receipt.colorStatus,'unavailable');assert.equal(receipt.samples.find(r=>r.region==='main').backgroundLuminance,null);assert.ok(w.getComputedStyle(w.document.querySelector('main')).backgroundImage.includes('linear-gradient'));
});

test('root and composer ancestor filters block compatibility and remain unknown without removing the filter',async t=>{
  for(const selector of ['html','form']){
    const {w}=page(t,{css:bright+selector+'{filter:invert(1)}'});const receipt=await observed(w);assert.equal(receipt.colorStatus,'unavailable');assert.equal(receipt.compatibilityApplied,false);assert.equal(ownStyles(w).length,0);assert.equal(w.getComputedStyle(w.document.querySelector(selector)).filter,'invert(1)');assert.equal(receipt.samples.find(r=>r.region==='composer').backgroundLuminance,null);
  }
});

test('nonzero visual offsets retain layout coordinates for the center hit',async t=>{
  const {w,hits}=page(t,{css:dark,viewport:{offsetLeft:70,offsetTop:110,width:250,height:400,scale:1.25}});const receipt=await observed(w);assert.equal(receipt.colorStatus,'verified');assert.deepEqual(hits[0],{x:195,y:305});assert.deepEqual(hits[1],{x:195,y:430});
});

test('foreign and lookalike origins neither install compatibility nor dispatch provider events',t=>{
  for(const url of ['https://accounts.google.com/','https://auth.openai.com/','http://chatgpt.com/','https://chatgpt.com.example/']){
    const {w}=page(t,{url});let events=0;w.addEventListener('storage',()=>events++);assert.equal(w.PocketAppearance.apply(true),false);assert.equal(ownStyles(w).length,0);assert.equal(events,0);assert.equal(w.document.documentElement.dataset.theme,'light');
  }
});
