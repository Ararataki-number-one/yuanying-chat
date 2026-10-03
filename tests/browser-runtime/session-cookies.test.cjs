/* Production extension with host API doubles; actual Cookie API also has Android coverage. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync('app/src/main/assets/gecko/background.js','utf8');
const copy=x=>JSON.parse(JSON.stringify(x)),checks=[];
const cookie=(name,extra={})=>({name,value:'synthetic',domain:'example.test',path:'/',session:true,
  secure:true,httpOnly:true,hostOnly:true,sameSite:'lax',storeId:'firefox-default',...extra});
function runtime(saved={},initial=[],failName=''){
  let cookies=copy(initial);const storage=copy(saved),sets=[],sent=[];let changed,message;
  const browser={proxy:{onRequest:{addListener(){}}},runtime:{sendNativeMessage:async()=>'{"type":"direct"}',
    connectNative:()=>({onMessage:{addListener(fn){message=fn;}},postMessage(value){sent.push(value);}})},
    storage:{local:{get:async key=>({[key]:copy(storage[key]??null)}),set:async value=>Object.assign(storage,copy(value))}},
    cookies:{onChanged:{addListener(fn){changed=fn;}},getAll:async()=>copy(cookies),set:async details=>{
      if(details.name===failName)throw new Error('synthetic Cookie API failure');sets.push(copy(details));
      const c=cookie(details.name,{...details,domain:details.domain??new URL(details.url).hostname,hostOnly:!details.domain});
      cookies.push(c);changed({cookie:c,removed:false});return c;
    }}};
  const context=vm.createContext({browser});vm.runInContext(code,context);
  return {storage,sets,sent,ready:()=>vm.runInContext('cookieReady',context),
    prepare:()=>message({kind:'prepare'}),read:()=>message({kind:'cookies',id:1,url:'https://example.test/'}),flush:()=>vm.runInContext('cookieCommit',context),
    clearNative(){cookies=[];},
    replace(list){cookies=copy(list);changed({cookie:cookie('event'),removed:true});}};
}
function check(name,value){assert.ok(value,name);checks.push({name,pass:true});}
(async()=>{
  const seed=runtime({},[cookie('session'),cookie('persistent',{session:false,expirationDate:1890000000})]);await seed.ready();
  check('Only session cookies enter the private journal',seed.storage.sessionCookiesV1.length===1&&seed.storage.sessionCookiesV1[0].name==='session');
  const restored=runtime(seed.storage);await restored.ready();await restored.prepare();
  const attributes=restored.sets[0];
  check('Native readiness waits for cookie restoration',restored.sent.at(-1).kind==='ready'&&restored.sets.length===1);
  check('Secure HttpOnly SameSite and host-only scope survive',attributes.secure&&attributes.httpOnly&&attributes.sameSite==='lax'&&!Object.hasOwn(attributes,'domain'));
  check('Session cookies do not receive an invented server expiry',!Object.hasOwn(attributes,'expirationDate'));
  restored.replace([]);await restored.flush();
  const logout=runtime(restored.storage);await logout.ready();
  check('Logout deletion cannot return after restart',logout.sets.length===0&&logout.storage.sessionCookiesV1.length===0);
  const cleared=runtime(seed.storage);await cleared.ready();cleared.clearNative();await cleared.read();
  const afterClear=runtime(cleared.storage);await afterClear.ready();
  check('Native bulk clear without cookie events cannot return after a completed read',afterClear.sets.length===0&&cleared.sent.at(-1).kind==='cookies'&&cleared.sent.at(-1).value==='');
  const existing=runtime(seed.storage,[cookie('session',{value:'newer-native-value'})]);await existing.ready();
  check('A newer native cookie is never overwritten by the journal',existing.sets.length===0&&existing.storage.sessionCookiesV1[0].value==='newer-native-value');
  const domain=runtime({sessionCookiesV1:[cookie('domain',{domain:'.example.test',hostOnly:false,sameSite:'strict',firstPartyDomain:'site.test',partitionKey:{topLevelSite:'https://site.test'}})]});await domain.ready();
  check('Domain and partition attributes remain scoped',domain.sets[0].domain==='.example.test'&&domain.sets[0].firstPartyDomain==='site.test'&&domain.sets[0].partitionKey.topLevelSite==='https://site.test');
  const original={sessionCookiesV1:[cookie('first'),cookie('failed')]};const failed=runtime(original,[],'failed');
  await assert.rejects(failed.ready());await failed.prepare();await failed.flush();
  check('A partial API failure keeps the complete recovery journal',JSON.stringify(failed.storage)===JSON.stringify(original));
  check('A failed restore never reports the browser ready',failed.sent.at(-1).kind==='cookieRecoveryError');
  console.log(JSON.stringify({passed:checks.length,total:checks.length,scope:'Production extension with host Cookie API doubles; no real account',checks}));
})().catch(error=>{console.error(error);process.exitCode=1;});
