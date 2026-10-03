// DOM behavior only. Rectangles are controlled; this does not test Android IME rendering.
const fs=require('node:fs');const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync(process.argv[2],'utf8'),checks=[];
const check=(name,pass)=>{if(!pass)throw new Error(name);checks.push({name,pass:true});};
const dom=new JSDOM('<!doctype html><title>Original title</title><body><select id="model"><option>Original model</option></select><article><pre><code>const unchanged = 1;</code></pre><p>Long reply</p></article><textarea>Unsent draft</textarea><button>Send</button><input type="checkbox"><div contenteditable="true">Editable draft</div></body>',{url:'https://chatgpt.com/c/reading',runScripts:'outside-only'});
const w=dom.window,input=w.document.querySelector('textarea');w.document.cookie='session=keep;path=/';let calls=0,options;
Object.defineProperty(w,'visualViewport',{value:{offsetTop:0,offsetLeft:0,height:300,width:390}});
input.scrollIntoView=o=>{calls++;options=o;};let rect={top:400,bottom:472,left:12,right:378,width:366,height:72};input.getBoundingClientRect=()=>rect;
const before=w.document.body.innerHTML;input.focus();const start=input.value;
check('A focused input covered by the keyboard is revealed',w.eval(source)===true&&calls===1);
check('Focus visibility uses nearest instant scroll',options.block==='nearest'&&options.inline==='nearest'&&options.behavior==='instant');
check('No title, model, code, message or input markup is rewritten',w.document.body.innerHTML===before&&w.document.title==='Original title');
check('The unsent draft and cookie are unchanged',input.value===start&&w.document.cookie.includes('session=keep'));
rect={top:180,bottom:252,left:12,right:378,width:366,height:72};check('A visible input is left in place',w.eval(source)===false&&calls===1);
w.document.querySelector('button').focus();check('Reading with no active input never scrolls the reply',w.eval(source)===false&&calls===1);
const checkbox=w.document.querySelector('input');checkbox.focus();check('A checkbox is not treated as the message composer',w.eval(source)===false);
const empty={top:0,bottom:0,left:0,right:0,width:0,height:0};input.focus();rect=empty;check('A hidden input cannot move the document',w.eval(source)===false);
const frame=w.document.createElement('iframe');w.document.body.append(frame);frame.contentWindow.eval(source);check('A child frame cannot run focus assistance',frame.contentWindow.eval(source)===false);
for(const url of ['https://accounts.google.com/','https://chatgpt.com.evil/','http://chatgpt.com/','https://chatgpt.com:444/']){const d=new JSDOM('<textarea>Private login field</textarea>',{url,runScripts:'outside-only'});const el=d.window.document.querySelector('textarea');el.focus();el.getBoundingClientRect=()=>({top:1000,bottom:1072,left:12,right:378,width:366,height:72});el.scrollIntoView=()=>{throw new Error('Unexpected login-page scroll');};check('No assistance on '+url,d.window.eval(source)===false);d.window.close();}
dom.window.close();console.log(JSON.stringify({passed:checks.length,total:checks.length,scope:'DOM behavior with controlled rectangles',checks},null,2));
