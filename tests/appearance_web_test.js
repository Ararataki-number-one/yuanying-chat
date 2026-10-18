const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const script=fs.readFileSync('app/src/main/assets/gecko/appearance.js','utf8');
let checks=0;
function fixture(origin='https://chatgpt.com',top=true,storageThrows=false){
  const classes=new Set(['light','official-page']),events={},values=new Map([['theme','light'],['draft','中文草稿'],['session','synthetic-login']]);
  const root={classList:{contains:name=>classes.has(name),toggle(name,on){if(on)classes.add(name);else classes.delete(name)}},style:{}};
  const doc={documentElement:root,addEventListener(name,fn){events[name]=fn},cookie:'session=synthetic'};
  const win={addEventListener(name,fn){events[name]=fn}};win.top=top?win:{};
  const context={location:{origin},window:win,document:doc,localStorage:{getItem:k=>values.get(k),setItem(k,v){if(storageThrows)throw Error('unavailable');values.set(k,v)}}};
  vm.runInNewContext(script,context);return {context,classes,events,values,root,doc};
}
function check(fn){fn();checks++}
const f=fixture(),apply=f.context.PocketAppearance.apply;
check(()=>assert.equal(apply(true),true));
check(()=>assert.ok(f.classes.has('dark')&&!f.classes.has('light')&&f.classes.has('official-page')));
check(()=>assert.equal(f.root.style.colorScheme,'dark'));
check(()=>assert.equal(f.values.get('theme'),'dark'));
check(()=>assert.equal(f.values.get('draft'),'中文草稿'));
check(()=>assert.equal(f.values.get('session'),'synthetic-login'));
check(()=>assert.equal(f.doc.cookie,'session=synthetic'));
check(()=>assert.equal(f.doc.documentElement,f.root));
check(()=>assert.equal(apply(false),true));
check(()=>assert.ok(f.classes.has('light')&&!f.classes.has('dark')));
check(()=>assert.equal(f.values.get('theme'),'light'));
check(()=>assert.equal(apply('dark'),false));
for(const origin of ['https://accounts.google.com','https://auth.openai.com','http://chatgpt.com','https://chatgpt.com.evil.example']){
 const other=fixture(origin);check(()=>assert.equal(other.context.PocketAppearance.apply(true),false));check(()=>assert.equal(other.values.get('theme'),'light'));
}
check(()=>assert.equal(fixture('https://chatgpt.com',false).context.PocketAppearance.apply(true),false));
check(()=>assert.equal(fixture('https://chatgpt.com',true,true).context.PocketAppearance.apply(true),true));
apply(true);f.classes.delete('dark');f.events.DOMContentLoaded();check(()=>assert.ok(f.classes.has('dark')));
f.classes.delete('dark');f.events.pageshow();check(()=>assert.ok(f.classes.has('dark')));
check(()=>assert.equal(f.context.PocketAppearance.apply(null),false));
console.log(`Official-page appearance: ${checks} checks passed`);
