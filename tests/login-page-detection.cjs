const fs=require('node:fs');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const script=fs.readFileSync(process.argv[2],'utf8'),checks=[];
const check=(name,ok)=>{if(!ok)throw new Error(name);checks.push({name,pass:true});};
function fixture(text,url='https://accounts.google.com/v3/signin/rejected'){
  return new JSDOM('<!doctype html><html><body><p id="notice"></p><input id="account" value="fixture-only"><textarea>keep this draft</textarea></body></html>',{url,runScripts:'outside-only'});
}
for(const [name,text,blocked] of [
  ['Simplified Chinese browser rejection','无法登录。此浏览器或应用可能不安全。',true],
  ['English browser rejection','Could not sign you in. This browser or app may not be secure.',true],
  ['Provider error code','Error: disallowed_useragent',true],
  ['Ordinary account selection','Choose an account',false],
  ['Wrong password does not imply browser restriction','Wrong password. Try again.',false],
]){const dom=fixture(text),w=dom.window;w.document.querySelector('#notice').textContent=text;const before=w.document.body.innerHTML;const result=w.eval(script);check(name,result===blocked);check(name+' leaves the page and fields untouched',before===w.document.body.innerHTML&&w.document.querySelector('#account').value==='fixture-only');check(name+' returns a boolean without account content',typeof result==='boolean');w.close();}
const other=fixture('', 'https://example.com/');other.window.document.querySelector('#notice').textContent='This browser or app may not be secure';check('Only the trusted Google host is inspected',other.window.eval(script)===false);other.window.close();
const root=fixture('');const frame=root.window.document.createElement('iframe');root.window.document.body.appendChild(frame);frame.contentDocument.body.textContent='This browser or app may not be secure';check('Child frames do not trigger the native login warning',frame.contentWindow.eval(script)===false);root.window.close();
console.log(JSON.stringify({passed:checks.length,total:checks.length,scope:'DOM detection only; no Google authentication or Android UI',checks},null,2));
