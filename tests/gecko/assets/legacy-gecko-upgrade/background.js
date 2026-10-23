'use strict';
const port = browser.runtime.connectNative('pocketroute');
port.onMessage.addListener(async message => {
  if(message.kind !== 'seed')return;
  const cookie = await browser.cookies.set({url:'https://chatgpt.com/',name:'pocket_upgrade_fixture',value:'retained-session',secure:true,httpOnly:true});
  port.postMessage({kind:'seeded',session:cookie.session});
});
