// Production observer with explicit DOM/event/timer boundaries; no real browser claim.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const events={},posted=[],timers=[];
class Element {closest(selector){return selector==='button,[role="button"]'?this:null;}getAttribute(name){return name==='aria-label'?'Send':null;}matches(selector){return selector==='[data-testid="send-button"]';}contains(){return false;}}
const button=new Element(),input=new Element();let draftReads=0;
const document={addEventListener:(name,handler)=>events[name]=handler};
const window={__pocketReplyObservationAllowed:false,PocketWebReply:{postMessage:raw=>posted.push(JSON.parse(raw))},addEventListener(){}};window.top=window;
const context={window,document,location:{origin:'https://chatgpt.com',href:'https://chatgpt.com/c/example'},URL,Element,crypto:require('crypto').webcrypto,MutationObserver:class{observe(){}},setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){},Date,Set,JSON};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/src/main/assets/web-reply-observer.js','utf8'),context);
window.__pocketInstallWebReplyObserver({composer:()=>input,sendButton:()=>button,draft:()=>{draftReads++;return 'private prompt';},messages:()=>[],busy:()=>false,resourceBusy:()=>true,uploadBusy:()=>true},'fixture-binding');
events.click({isTrusted:true,target:button});events.keydown({isTrusted:true,target:input,key:'Enter'});
assert.equal(draftReads,0);assert.equal(posted.some(x=>x.type==='intent'),false);assert.equal(window.__pocketWebReplyObserver.lastGestureAt(),0);
assert.equal(window.__pocketWebReplyObserver.requestResources('12345678-1234-1234'),true);assert.equal(posted.at(-1).type,'resource-work');assert.equal(posted.at(-1).uploading,true);
console.log(JSON.stringify({status:'passed',checks:6,scope:'Actual observer script; declared event/DOM/timer adapters. Disabled send observation never reads prompt or creates intent; resource/upload status remains available.',actualAndroidExecution:false}));
