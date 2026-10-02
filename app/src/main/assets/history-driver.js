(async function(action,arg){
  'use strict';
 if(action==='history-older'){const first=document.querySelector('[data-message-author-role]');if(!first)return {ok:false,reason:'网页还没有加载消息'};let scroll=first.parentElement;while(scroll&&scroll.scrollHeight<=scroll.clientHeight+20)scroll=scroll.parentElement;if(!scroll)scroll=document.scrollingElement;const before=document.querySelectorAll('[data-message-author-role]').length;scroll.scrollTop=0;first.scrollIntoView({block:'start'});await new Promise(r=>setTimeout(r,2400));const after=document.querySelectorAll('[data-message-author-role]').length;return {ok:true,reason:after>before?'已加载更早的消息':'当前网页没有提供更多消息；可在原网页查看'};}

  if(location.protocol!=='https:'||location.hostname!=='chatgpt.com')return {ok:false,reason:'请先在 ChatGPT 完成登录'};
  const wait=ms=>new Promise(r=>setTimeout(r,ms)),norm=s=>String(s||'').replace(/\s+/g,' ').trim();
  const visible=e=>!!e&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('[hidden],[aria-hidden="true"],[inert]');
  const label=e=>norm(e.getAttribute('aria-label')||e.textContent);
  const controls=()=>[...document.querySelectorAll('button,[role="button"],[role="menuitem"]')].filter(visible);
  const urlOf=e=>{try{const u=new URL(e.href,location.href);return u.origin===location.origin&&/^\/(?:g\/[^/]+\/)?c\/[^/]+$/.test(u.pathname)?u.origin+u.pathname:'';}catch{return '';}};
  const links=()=>[...document.querySelectorAll('a[href]')].filter(e=>visible(e)&&urlOf(e));
  let opened=false;
  async function openSidebar(){const b=controls().find(e=>/^(Open sidebar|Show sidebar|显示侧边栏|打开侧边栏|打开边栏)$/i.test(label(e)));if(b&&b.getAttribute('aria-expanded')!=='true'){b.click();opened=true;await wait(450);}}
  function closeSidebar(){if(!opened)return;const b=controls().find(e=>/^(Close sidebar|Hide sidebar|隐藏侧边栏|关闭侧边栏|关闭边栏)$/i.test(label(e)));if(b)b.click();}
  function scroller(items){for(const link of items){let n=link.parentElement;while(n&&n!==document.body){if(n.scrollHeight>n.clientHeight+15&&/(auto|scroll)/.test(getComputedStyle(n).overflowY))return n;n=n.parentElement;}}return null;}
  async function scan(target){await openSidebar();const initial=scroller(links());if(initial){initial.scrollTop=0;initial.dispatchEvent(new Event('scroll',{bubbles:true}));await wait(300);}const found=new Map();let stable=0,previous='',root=null;for(let turn=0;turn<650;turn++){
    if(location.hostname!=='chatgpt.com')return {ok:false,complete:false,chats:[...found.values()],reason:'同步过程中离开了 ChatGPT'};
    const items=links();for(const e of items){const url=urlOf(e),title=norm(e.getAttribute('aria-label')||e.textContent);if(title)found.set(url,{url,title});if(target&&url===target)return {ok:true,element:e,chats:[...found.values()]};}
    root=scroller(items)||root;const more=controls().find(e=>/^(Load more|Show more|加载更多|查看更多)$/i.test(label(e)));const panel=(items[0]&&items[0].closest('nav,[role="dialog"],aside'))||document.querySelector('#stage-slideover-sidebar,#app-shell-sidebar,#browser-sidebar-popover')||document.body;
    const loading=[...panel.querySelectorAll('[role="status"],span,div')].some(e=>visible(e)&&e.children.length===0&&/^(正在加载聊天|Loading chats|加载中[.…]*|Loading[.…]*)$/i.test(norm(e.textContent)));
    const atBottom=!root||root.scrollTop+root.clientHeight>=root.scrollHeight-6;const signature=[found.size,root?root.scrollHeight:0,root?Math.round(root.scrollTop):0].join(':');
    stable=signature===previous&&atBottom&&!loading&&!more?stable+1:0;previous=signature;
    if(stable>=8)return {ok:!target,complete:!target,chats:[...found.values()],reason:target?'未找到目标会话':'已到当前工作区历史列表末尾'};
    if(more)more.click();else if(root){root.scrollTop=Math.min(root.scrollHeight,root.scrollTop+Math.max(120,root.clientHeight*.75));root.dispatchEvent(new Event('scroll',{bubbles:true}));}
    await wait(600);
  }return {ok:false,complete:false,chats:[...found.values()],reason:'已保存本轮历史，但尚未到列表末尾，请继续同步'};}
  async function openAction(target,kind){const located=await scan(target);if(!located.ok)return located;let row=located.element.parentElement,menu=null;for(let i=0;row&&i<6;i++,row=row.parentElement){const candidates=[...row.querySelectorAll('button,[role="button"]')].filter(e=>(/^(Chat actions|Conversation actions|聊天操作|对话操作)$/i.test(label(e))||/^Open conversation options for /i.test(label(e))||e.hasAttribute("data-conversation-options-trigger")));if(candidates.length===1){menu=candidates[0];break;}if(row.querySelectorAll('a[href]').length>3)break;}
    if(!menu)return {ok:false,reason:'未识别目标会话的操作按钮'};menu.focus();menu.dispatchEvent(new PointerEvent('pointerdown',{button:0,buttons:1,pointerType:'mouse',isPrimary:true,bubbles:true,cancelable:true}));menu.dispatchEvent(new PointerEvent('pointerup',{button:0,buttons:0,pointerType:'mouse',isPrimary:true,bubbles:true,cancelable:true}));await wait(100);if(menu.getAttribute('aria-expanded')!=='true'&&menu.getAttribute('data-state')!=='open')menu.click();await wait(350);const pattern=kind==='rename'?/^(Rename|重命名)(?:\s|$)/i:/^(Delete|删除)(?:\s|$)/i;const options=controls().filter(e=>pattern.test(label(e))&&e.matches('[role="menuitem"],button'));if(options.length!==1)return {ok:false,reason:'会话菜单发生变化，未执行修改'};options[0].click();await wait(350);return {ok:true};}
  try{
    if(action==='history-sync')return await scan('');
    const target=new URL(arg.url);if(target.origin!==location.origin||!/^\/(?:g\/[^/]+\/)?c\/[^/]+$/.test(target.pathname))return {ok:false,reason:'会话地址无效'};
    if(action==='history-rename'){
      const title=norm(arg.title);if(!title||title.length>200)return {ok:false,reason:'名称应为 1–200 个字符'};
      const opened=await openAction(target.origin+target.pathname,'rename');if(!opened.ok)return opened;
      let input=document.activeElement;if(!input||!input.matches('input[type="text"],input:not([type]),textarea')||!visible(input)){const candidates=[...document.querySelectorAll('[role="dialog"] input,[role="dialog"] textarea')].filter(visible);if(candidates.length!==1)return {ok:false,reason:'未找到唯一的重命名输入框'};input=candidates[0];}
      const proto=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(input,title);input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));await wait(100);
      const save=controls().find(e=>/^(Save|保存|确认|Confirm)$/i.test(label(e))&&e.matches('button'));
      if(save)save.click();else{input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));input.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));}
      for(let i=0;i<20;i++){await wait(200);const item=links().find(e=>urlOf(e)===target.origin+target.pathname);if(item&&norm(item.getAttribute('aria-label')||item.textContent)===title)return {ok:true,title};}
      return {ok:false,reason:'网页未确认新名称，请查看原网页后再试'};
    }
    if(action==='history-delete'){
      if(arg.confirmed!==true)return {ok:false,reason:'删除需要用户确认'};
      const opened=await openAction(target.origin+target.pathname,'delete');if(!opened.ok)return opened;
      const dialogs=[...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(visible);const buttons=dialogs.flatMap(d=>[...d.querySelectorAll('button')]).filter(e=>visible(e)&&/^(Delete|删除|删除聊天|删除对话)$/i.test(label(e)));const unique=[...new Set(buttons)];
      if(unique.length!==1)return {ok:false,reason:'未找到唯一的删除确认按钮，未继续'};unique[0].click();await wait(1500);
      const remaining=links().some(e=>urlOf(e)===target.origin+target.pathname);const error=[...document.querySelectorAll('[role="alert"]')].filter(visible).some(e=>/failed|error|失败|错误/i.test(e.textContent));
      if(!remaining&&!error)return {ok:true};return {ok:false,reason:'删除未得到网页确认，请检查后再试'};
    }
    return {ok:false,reason:'未知历史操作'};
  }finally{closeSidebar();}
})(__ACTION__,__ARG__)
