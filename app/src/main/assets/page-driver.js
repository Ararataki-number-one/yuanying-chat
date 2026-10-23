(function (action, arg) {
  'use strict';
  // The website owns message/model/history actions. This public bridge only
  // observes it, restores guarded browser drafts and handles requested files.
  if(!["inspect","web-inspect","observe-install","web-transcript","transcript","poll","latest","chats","page-state","page-content","page-timing","page-recover","page-restore","attachment-state","file-prepare","file-point","file-followup"].includes(action))return {ok:false,reason:'请在 ChatGPT 原网页中操作'};
  const rendered = el => !!el && !el.closest('[hidden],[aria-hidden="true"]') && el.getClientRects().length > 0 &&
    getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden';
  const visible=el=>rendered(el) && !el.closest('[inert]');
  const norm = s => String(s || '').replace(/\u00a0/g, ' ').replace(/\r\n?/g, '\n').trim();
  const exactText = s => String(s || '').replace(/\r\n?/g, '\n');
  const signature = s => norm(s).replace(/\s+/g, ' ');
  const label = el => [el.getAttribute('aria-label'), el.getAttribute('title'), el.innerText].filter(Boolean).join(' ').trim();
  const buttons = () => [...document.querySelectorAll('button,[role="button"]')].filter(visible);
  function composer(includeInactive=false) {
    const selectors = ['[contenteditable="true"][data-composer-markdown]','#prompt-textarea', '[data-composer-body] [contenteditable="true"]',
      'textarea[placeholder*="ChatGPT"]', '[contenteditable="true"][role="textbox"]',
      '[contenteditable="true"].ProseMirror', 'textarea[data-testid="prompt-textarea"]'];
    for (const s of selectors) { const el = [...document.querySelectorAll(s)].filter(x=>!x.closest('[data-markdown-copy="code-block"],.cm-editor,.monaco-editor,[data-editor-search-surface],[data-message-author-role],[data-chatgpt-conversation-selection-target]')).find(includeInactive?rendered:visible); if (el) return el; }
    return null;
  }
  function draft(el) {
    if(!el)return '';if(el.tagName==='TEXTAREA')return el.value;
    // The current markdown composer puts each source line in a paragraph. Its
    // rendered innerText adds layout blank lines which are not message content.
    if(el.matches('.ProseMirror') && el.children.length>0 && [...el.children].every(x=>x.tagName==='P')){
      const walk=node=>node.nodeType===Node.TEXT_NODE?node.nodeValue:node.nodeType!==Node.ELEMENT_NODE?'':node.matches('br.ProseMirror-trailingBreak')?'':node.tagName==='BR'?'\n':[...node.childNodes].map(walk).join('');
      return [...el.children].map(walk).join('\n');
    }
    return el.innerText;
  }
  function sendButton() {
    return [...document.querySelectorAll('button,[role="button"]')].find(el => (el.matches('[data-testid="send-button"]') ||
      /^(发送|发送消息|Send|Send prompt|Send message)$/i.test((el.getAttribute('aria-label') || el.innerText || '').trim()))&&visible(el));
  }
  function busy() {
    return [...document.querySelectorAll('button,[role="button"]')].some(el => (el.matches('[data-testid="stop-button"]') ||
      /^(停止|停止生成|Stop|Stop generating|Stop streaming)$/i.test((el.getAttribute('aria-label') || el.innerText || '').trim())) && rendered(el));
  }
  function modelControl() {
    const selectors = ['[data-testid="model-switcher-dropdown-button"]',
      'button[aria-label="选择 ChatGPT 模型"]', 'button[aria-label="Select ChatGPT model"]',
      'button[aria-label="选择模型"]', 'button[aria-label="Select model"]',
      'button[aria-label*="Model selector"]', 'button[aria-label*="模型选择"]'];
    let el = null;
    for (const s of selectors) { el = [...document.querySelectorAll(s)].find(visible); if (el) break; }
    if(!el){const choices=[...document.querySelectorAll('form button')].filter(visible).filter(b=>/^(?:(?:GPT[ -]?)?\d+(?:\.\d+)*(?:\s+Sol)?\s+)?(?:Light|Standard|High|Extra[ -]?High|Pro|Thinking|Instant|Auto|Thinking effort|Reasoning effort|GPT[ -]?[\d.]+(?:\s+(?:Thinking|Pro|Instant))?|轻量|标准|高|极高|思考|思考强度|思考时间|自动|快速)$/i.test(norm(b.innerText)));if(choices.length===1)el=choices[0];}
    return el;
  }
  function effortControl() {
    return buttons().find(el=>/thinking effort|reasoning effort|思考强度|推理强度|思考时间|thinking time/i.test(label(el)) && el!==modelControl());
  }
  function modelInfo() {
    const el=modelControl(), effort=effortControl();
    let text = el ? norm(el.innerText || el.getAttribute('aria-valuetext') || label(el)) : '';
    if(/^(思考强度|Thinking effort|Reasoning effort)$/i.test(text))text=sliderLabel(slider()) || text;
    const effortText=effort?norm(effort.innerText || label(effort)):'';
    return { text, effort:effortText, pro: /\bpro\b/i.test(text) && !/upgrade|升级/i.test(text), known: !!el };
  }
  function slider() {
    const controls=[...document.querySelectorAll('[data-reasoning-slider="true"]')].filter(visible);
    if(controls.length===1)return controls[0];
    const modern=[...document.querySelectorAll('[data-model-reasoning-effort-slider]')].filter(visible).map(x=>x.closest('[aria-keyshortcuts*="ArrowLeft"]')).filter(visible);
    if(modern.length===1)return modern[0];
    const found=[...document.querySelectorAll('[role="slider"],input[type="range"]')].filter(visible);
    return found.length===1?found[0]:null;
  }
  function sliderLabel(el) {
    if(!el)return '';
    const described=(el.getAttribute('aria-describedby')||'').split(/\s+/).map(id=>document.getElementById(id)).filter(Boolean);
    const announced=described.map(x=>norm(x.textContent)).find(x=>/第\s*\d+\s*项|\d+\s+of\s+\d+/i.test(x));
    return norm(el.getAttribute('aria-valuetext') || announced || el.getAttribute('aria-label') || '').split(/[，,。]/)[0];
  }
  function messages(role) {
    const build=()=>{const nodes = [...document.querySelectorAll('[data-message-author-role="' + role + '"],article[data-turn="' + role + '"],[data-chatgpt-search-unit-key$=":'+role+'"],[data-content-search-unit-key$=":'+role+'"]')];
      const selector='[data-message-author-role="'+role+'"],article[data-turn="'+role+'"],[data-chatgpt-search-unit-key$=":'+role+'"],[data-content-search-unit-key$=":'+role+'"]';return nodes.filter(el=>!el.parentElement?.closest(selector));};
    return window.__pocketWebPerformance?.messageNodes(role,build) ?? build();
  }
  function hasMessages(){return !!document.querySelector('[data-message-author-role="user"],[data-message-author-role="assistant"],article[data-turn="user"],article[data-turn="assistant"],[data-chatgpt-search-unit-key$=":user"],[data-chatgpt-search-unit-key$=":assistant"],[data-content-search-unit-key$=":user"],[data-content-search-unit-key$=":assistant"]');}
  function userText(el) {
    const body=el.querySelector('[data-user-message-bubble]');
    if(body){if(body.querySelector('[data-markdown-copy="code-block"]')){const walk=node=>node.nodeType===Node.TEXT_NODE?node.nodeValue:node.nodeType!==Node.ELEMENT_NODE?'':node.matches('[data-markdown-copy="code-block"]')?codeBlock(node):node.matches('button,svg,[data-markdown-copy="exclude"]')?'':node.tagName==='BR'?'\n':[...node.childNodes].map(walk).join('');return walk(body);}return body.innerText;}
    const excluded='button,[role="button"],.sr-only,[data-conversation-role],[aria-hidden="true"]';
    if(!el.querySelector(excluded))return el.innerText;
    const clone=el.cloneNode(true);clone.querySelectorAll(excluded).forEach(x=>x.remove());
    const text=node=>node.nodeType===Node.TEXT_NODE?node.nodeValue:node.nodeType!==Node.ELEMENT_NODE?'':node.tagName==='BR'?'\n':[...node.childNodes].map(text).join('')+(/^(DIV|P|LI)$/.test(node.tagName)?'\n':'');
    return text(clone).trim();
  }
  function observed(node,kind,build){return window.__pocketWebPerformance?.memo(node,kind,build) ?? build();}
  function observedUserText(node){return observed(node,'userText',()=>userText(node));}
  function observedMarkdown(node){return observed(node,'markdown',()=>markdown(node));}
  function observedFiles(node){return observed(assistantScope(node)||node,'files',()=>fileControls(node));}
  function ownMessageId(el) {
    return el.getAttribute('data-message-id') || el.getAttribute('data-chatgpt-selection-message-id') ||
      (el.getAttribute('data-chatgpt-search-message-ids')||'').trim().split(/\s+/)[0] || '';
  }
  function legacyKey(el, index) {
    const id=ownMessageId(el)||el.id;if(id)return 'id:'+id;
    const unit=el.getAttribute('data-chatgpt-search-unit-key')||el.getAttribute('data-content-search-unit-key');if(unit)return 'unit:'+unit;
    const article=el.closest('article'),turn=article&&(article.getAttribute('data-testid')||article.id);
    return turn?'turn:'+turn:'index:'+index+':'+signature(el.innerText).slice(0,96);
  }
  function key(el, index) {
    const id=ownMessageId(el)||el.id;if(id)return 'id:'+id;
    const unit=el.getAttribute('data-chatgpt-search-unit-key')||el.getAttribute('data-content-search-unit-key');if(unit)return 'unit:'+unit;
    // messages() de-duplicates the outer turn and its body. The authoritative
    // message ID can live in the nested body; accept only one ID of this role.
    const role=el.getAttribute('data-message-author-role')||el.getAttribute('data-turn');
    if(role==='user'||role==='assistant'){
      const nested=new Set([...el.querySelectorAll('[data-message-author-role="'+role+'"]')].map(ownMessageId).filter(Boolean));
      if(nested.size===1)return 'id:'+[...nested][0];
    }
    return legacyKey(el,index);
  }
  const socketClosedNotice='网页实时连接已断开，请在原网页检查或恢复连接；软件不会自动重发。';
  const socketClosed=/Browser app server websocket closed|(?:websocket|web socket|实时连接).{0,64}(?:closed|disconnected|connection lost|断开|关闭)|(?:connection closed|connection lost).{0,64}(?:websocket|web socket)/i;
  const errorMessageSelector='[data-message-author-role],article[data-turn],[data-chatgpt-search-unit-key$=":user"],[data-chatgpt-search-unit-key$=":assistant"],[data-content-search-unit-key$=":user"],[data-content-search-unit-key$=":assistant"]';
  const errorContentSelector=errorMessageSelector+',.markdown,[data-markdown-text-style="assistant-message"],[data-is-reasoning="true"]';
  const errorTurnSelector='[data-turn="user"],[data-turn="assistant"],[data-testid^="conversation-turn-"],[data-content-search-turn-key],[data-turn-key]';
  function siteError(scope,fast=false) {
    if(!fast&&/Unable to load site|无法加载网站/.test(document.body.innerText||''))return '网站拒绝当前访问。请检查应用专用代理和出口，或查看网站状态；尚未确认登录。';
    if (document.querySelector('#main-frame-error,.neterror,#error-information-popup'))
      return '浏览器无法连接 ChatGPT。请检查可用网络或专用代理；本次未确认发送成功。';
    const root=scope || document;
    const current=messages('assistant').filter(el=>!scope||scope.contains(el)).at(-1);
    // Historical failure cards stay visible in a conversation. Only the
    // current assistant turn or a toast outside all turns is active evidence.
    const activeSurface=el=>{
      if(!rendered(el)||el.closest('[role="menu"],pre,code,[data-markdown-copy="code-block"]'))return false;
      if(el.closest('[data-message-author-role="user"],[data-turn="user"],[data-chatgpt-search-unit-key$=":user"],[data-content-search-unit-key$=":user"]'))return false;
      const message=el.closest(errorMessageSelector);
      if(message)return !!current&&(message===current||current.contains(message)||message.contains(current));
      // Older layouts put actions beside a message in an unlabelled section.
      // Use its nearest owner, without treating the shared main/body as a turn.
      for(let turn=el;turn&&!turn.matches('main,body,html');turn=turn.parentElement)
        if(turn.matches(errorTurnSelector)||turn.querySelector(errorMessageSelector))return !!current&&turn.contains(current);
      return true;
    };
    const retryContext=el=>{
      const parent=el.closest('[role="alert"]')||el.parentElement;
      if(!parent||parent.matches('main,body,html'))return '';
      if(!parent.querySelector(errorContentSelector))return parent.innerText||'';
      // A sibling retry may share a wrapper with the response. Do not read
      // ordinary or historical message bodies as if they were error text.
      return [...parent.childNodes].map(node=>node.nodeType===Node.TEXT_NODE?node.nodeValue:node.nodeType!==Node.ELEMENT_NODE||!rendered(node)||node.matches(errorContentSelector+',pre,code,[data-markdown-copy="code-block"]')||node.querySelector(errorContentSelector)?'':node.innerText||'').join('\n');
    };
    const alerts = [...root.querySelectorAll('[role="alert"]')].filter(activeSurface);
    let retryText='';
    const retry = [...root.querySelectorAll('button,[role="button"]')].find(el=>{
      if(!/^(重试|重新尝试|Retry|Try again)$/i.test((el.getAttribute('aria-label')||el.innerText||'').trim())||!activeSurface(el))return false;
      const text=retryContext(el);
      if(!el.closest('[role="alert"]')&&!/Something went wrong|network error|failed|出现错误|出了点问题|网络错误|失败/i.test(text)&&!socketClosed.test(text))return false;
      retryText=text;return true;
    });
    let text = alerts.map(el => el.innerText).join('\n');
    if (retry) text += '\n' + retryText.slice(0,1600);
    if (/Enable JavaScript and cookies|verify you are human|验证您是人类|人机验证|unusual activity|cloudflare/i.test(text))
      return '网页需要手动验证。请在浏览器处理后点击“继续检测”；软件不会自动重发。';
    if(socketClosed.test(text))return socketClosedNotice;
    if (retry || /Something went wrong|出现错误|出了点问题|已达到.*上限|reached.*limit|network error|网络错误/i.test(text))
      return 'ChatGPT 页面报告错误或使用限制，请检查浏览器。软件没有自动重发。';
    return '';
  }
  function siteObservation(scope,fast=false){
    const error=siteError(scope,fast),websiteSocketClosed=error===socketClosedNotice;
    const errorText=error&&!websiteSocketClosed?((scope||document.body).innerText||''):'';
    const recoverable=websiteSocketClosed||!!error&&!/上限|限制|额度|limit|验证|verify|captcha|unusual activity/i.test(errorText)&&/网络|连接|重试|retry|went wrong|network|出了点|出现错误/i.test(errorText);
    return {error,recoverable,...(websiteSocketClosed?{websiteSocketClosed:true,errorCode:'website_socket_closed'}:{})};
  }
  function ready() {
    const input = composer(), rawInput=composer(true), model = modelInfo();
    return { url: location.href, documentId:documentKey(), title: document.title, composer: !!input, draft: draft(input),
      userBubbleColor:(()=>{const u=messages("user").at(-1);if(!u)return "";const e=[u,...u.querySelectorAll("*")].find(e=>{const s=getComputedStyle(e);return parseFloat(s.borderRadius)>=12&&s.backgroundColor!=="rgba(0, 0, 0, 0)"&&e.getBoundingClientRect().width>20;});return e?getComputedStyle(e).backgroundColor:"";})(),model: model.text, effort:model.effort, pro: model.pro, modelKnown: model.known, busy: busy(),draftKnown:!!rawInput,draftRaw:draft(rawInput),
      userCount: messages('user').length,userKeys:messages('user').map(key), assistantCount: messages('assistant').length,conversationLoaded:messages('user').length>0,
      error: siteError(), sendEnabled: !!sendButton() && !sendButton().disabled };
  }
  function pageAllowed() {
    if (location.protocol !== 'https:' || location.hostname !== 'chatgpt.com') return false;
    if (arg && arg.expectedUrl) {
      const expected = new URL(arg.expectedUrl);
      if (expected.origin !== location.origin) return false;
    }
    return true;
  }
  function samePrompt(text, expected) {
    const a = signature(text), b = signature(expected);
    if (a === b) return true;
    if(!b&&arg&&arg.attachmentOnly)return !a||(Array.isArray(arg.attachmentNames)&&arg.attachmentNames.length>0&&arg.attachmentNames.every(n=>a.includes(signature(n))));
    // Markdown presentation may alter whitespace; require both ends and a close length.
    return b.length > 180 && a.startsWith(b.slice(0,80)) && a.endsWith(b.slice(-80)) &&
      Math.abs(a.length-b.length) < Math.max(30, b.length*0.05);
  }
  function codeBlock(root){
    const cm=root.querySelector('.cm-content'),code=cm||root.querySelector('code')||root;const header=root.querySelector('[data-markdown-copy="exclude"]');
    let lang=code.getAttribute('data-language')||(String(code.className).match(/language-([\w+-]+)/)||[])[1]||(header?header.innerText.split(/\r?\n/)[0].trim().toLowerCase():'');if(!/^[\w+#.-]*$/.test(lang))lang='';
    let text=code.textContent;
    if(cm){const view=cm.cmView&&cm.cmView.view;const doc=view&&view.state&&view.state.doc;text=doc&&typeof doc.toString==='function'?doc.toString():[...cm.querySelectorAll('.cm-line')].map(line=>line.textContent).join('\n');}
    else if(code===root){const clean=root.cloneNode(true);clean.querySelectorAll('[data-markdown-copy="exclude"],button,svg').forEach(x=>x.remove());text=clean.textContent;}
    text=text.replace(/\n$/,'');const fence='`'.repeat(Math.max(3,...(text.match(/`+/g)||[]).map(x=>x.length+1)));return fence+lang+'\n'+text+'\n'+fence;
  }
  function markdown(root) {
    function walk(node) {
      if (node.nodeType === Node.TEXT_NODE) return node.nodeValue;
      if (node.nodeType !== Node.ELEMENT_NODE) return '';
      const tag = node.tagName.toLowerCase();
      if(node.matches('[data-markdown-copy="code-block"]'))return '\n\n'+codeBlock(node)+'\n\n';
      if(node.matches('[data-markdown-copy="exclude"]'))return '';
      if (node.matches('.katex-display,.katex')) {
        const tex = node.querySelector('annotation[encoding="application/x-tex"]');
        if (tex) return node.matches('.katex-display') ? '\n\n$$\n'+tex.textContent+'\n$$\n\n' : '$'+tex.textContent+'$';
      }
      if (['button','script','style','svg','noscript'].includes(tag) || node.getAttribute('aria-hidden') === 'true') return '';
      if (tag === 'pre') {
        const code = node.querySelector('code') || node;
        const text = code.textContent.replace(/\n$/, '');
        const lang = (code.className.match(/language-([\w+-]+)/) || [,''])[1];
        const fence = '`'.repeat(Math.max(3, ...((text.match(/`+/g)||[]).map(x=>x.length+1))));
        return '\n\n'+fence+lang+'\n'+text+'\n'+fence+'\n\n';
      }
      const text = [...node.childNodes].map(walk).join('');
      if (tag === 'br') return '\n';
      if (/^h[1-6]$/.test(tag)) return '\n\n'+'#'.repeat(Number(tag[1]))+' '+text.trim()+'\n\n';
      if (tag === 'p') return '\n\n'+text.trim()+'\n\n';
      if (tag === 'li') return '\n- '+text.trim().replace(/\n\n/g,'\n  ');
      if (tag === 'ul' || tag === 'ol') return '\n'+text+'\n';
      if (tag === 'blockquote') return '\n\n'+text.trim().split('\n').map(x=>'> '+x).join('\n')+'\n\n';
      if (tag === 'strong' || tag === 'b') return '**'+text+'**';
      if (tag === 'em' || tag === 'i') return '*'+text+'*';
      if (tag === 'code') return '`'+text+'`';
      if (tag === 'a') return node.href && /^https?:/.test(node.href) ? '['+text+']('+node.href+')' : text;
      if (tag === 'hr') return '\n\n---\n\n';
      if (tag === 'tr') return '\n'+[...node.children].map(el=>walk(el).trim().replace(/\|/g,'\\|')).join(' | ')+'\n';
      return text;
    }
    return walk(root).replace(/\n[ \t]+\n/g,'\n\n').replace(/\n{3,}/g,'\n\n').trim();
  }
  if (!pageAllowed()) return {ok:false, error:'目标页面已改变，未继续操作。仅支持已绑定的 ChatGPT 页面。', reason:'目标页面已改变，未发送。',url:location.href};
  function samePage(url){try{return new URL(url).origin===location.origin&&new URL(url).pathname===location.pathname;}catch{return false;}}
  function pageScroll(){const first=document.querySelector('[data-message-author-role],article[data-turn],[data-chatgpt-search-unit-key],[data-content-search-unit-key]');for(let n=first?.parentElement;n&&n!==document.body;n=n.parentElement)if(n.scrollHeight>n.clientHeight+16&&/(auto|scroll)/.test(getComputedStyle(n).overflowY))return n;return document.scrollingElement;}
  function documentKey(){return window.__pocketDocumentId||(window.__pocketDocumentId=crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random().toString(36).slice(2));}
  function contentKey(){const nodes=messages('user').concat(messages('assistant'));return nodes.map((n,i)=>key(n,i)).join('|');}
  function pageSnapshot(){const input=composer(),scroll=pageScroll(),text=draft(input),complete=!!input&&text.length<=300000;return {ok:true,url:location.href,documentId:documentKey(),contentKey:contentKey(),draft:complete?text:null,draftComplete:complete,hasDraft:text.trim().length>0,draftLength:text.length,draftOmittedReason:!input?'composer-unavailable':complete?'':'too-long',scrollTop:Math.max(0,scroll?.scrollTop||0),selectionStart:input?.selectionStart||0,selectionEnd:input?.selectionEnd||0,gestureAt:window.__pocketWebReplyObserver?.lastGestureAt?.()||0};}
  if(action==='page-state'){if(!samePage(arg.expectedUrl))return {ok:false};return pageSnapshot();}
  if(action==='page-recover')return (async()=>{if(!samePage(arg.expectedUrl)||!composer()||busy()||siteError(null,true)||(!hasMessages()&&/\/c\//.test(location.pathname)))return {ok:false};const identity=documentKey(),controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),2500),started=performance.now();try{const response=await fetch(location.href,{method:'HEAD',credentials:'same-origin',cache:'no-cache',redirect:'error',signal:controller.signal});return {ok:response.ok&&identity===documentKey()&&samePage(arg.expectedUrl)&&!!composer()&&!busy()&&!siteError(null,true),url:location.href,probeMs:performance.now()-started};}catch{return {ok:false,probeMs:performance.now()-started};}finally{clearTimeout(timeout);}})();
  if(action==='page-content'){return {ok:true,url:location.href,contentKey:contentKey(),documentId:documentKey()};}
  if(action==='page-restore')return (async()=>{
    if(!samePage(arg.expectedUrl))return {ok:false,reason:'route'};if(!composer())return {ok:false,reason:'composer'};if(busy())return {ok:false,reason:'busy'};if(siteError(null,true))return {ok:false,reason:'page-error'};const saved=arg.state||{};if(saved.draftComplete===false)return {ok:false,reason:'incomplete-draft'};const currentGesture=window.__pocketWebReplyObserver?.lastGestureAt?.()||0;
    if((saved.documentId===documentKey()&&currentGesture!==(saved.gestureAt||0))||(saved.documentId!==documentKey()&&currentGesture>0))return {ok:false,reason:'new-gesture'};
    const input=composer(),current=draft(input);let conflict=false,restoredDraft=false;
    if(arg.allowDraft&&saved.draft&&exactText(current)!==exactText(saved.draft)){
      if(current.trim())conflict=true;
      else {input.focus({preventScroll:true});if(input.tagName==='TEXTAREA'){Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,exactText(saved.draft));input.dispatchEvent(new Event('input',{bubbles:true}));}
        else {const range=document.createRange();range.selectNodeContents(input);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);if(!document.execCommand('insertText',false,exactText(saved.draft))){input.textContent=exactText(saved.draft);input.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:exactText(saved.draft)}));}}
        // Restoring text can queue its own selection event. Compare with the
        // resulting selection, and protect newer user actions while it settles.
        const doc=document,identity=documentKey(),events=['pointerdown','keydown','beforeinput','input','compositionstart','compositionupdate','compositionend','wheel','select','selectionchange','focusin','focusout'];
        const selection=()=>{if(input.tagName==='TEXTAREA')return [input.selectionStart,input.selectionEnd,input.selectionDirection];const s=doc.defaultView?.getSelection();return [s?.anchorNode,s?.anchorOffset,s?.focusNode,s?.focusOffset];};
        const initialSelection=selection();let interacted=false;
        const changed=event=>{if(!event.isTrusted)return;if(event.type==='select'||event.type==='selectionchange'){if(selection().some((value,index)=>value!==initialSelection[index]))interacted=true;}else interacted=true;};
        try{
          for(const type of events)doc.addEventListener(type,changed,true);
          await new Promise(r=>setTimeout(r,80));
          if(document!==doc||documentKey()!==identity||!samePage(arg.expectedUrl))return {ok:false,reason:'route'};
          if(composer()!==input||input.ownerDocument!==doc||!input.isConnected)return {ok:false,reason:'composer'};
          if(busy()||siteError(null,true))return {ok:false,reason:'page-state'};
          restoredDraft=exactText(draft(input))===exactText(saved.draft);
          if(!restoredDraft||interacted||doc.activeElement!==input||selection().some((value,index)=>value!==initialSelection[index]))return {ok:true,restoredDraft,interacted:true};
        }finally{for(const type of events)doc.removeEventListener(type,changed,true);}
      }
    }
    const scroll=pageScroll();if(arg.allowScroll!==false&&scroll&&Number.isFinite(saved.scrollTop))scroll.scrollTop=Math.max(0,Math.min(saved.scrollTop,scroll.scrollHeight-scroll.clientHeight));
    if(restoredDraft&&input.tagName==='TEXTAREA')try{input.setSelectionRange(saved.selectionStart||0,saved.selectionEnd||0);}catch{}
    return {ok:true,restoredDraft,conflict};
  })();
  if(action==='page-timing'){const timing=performance.getEntriesByType('navigation')[0];if(!timing)return {ok:false};return {ok:true,fullNavigation:samePage(timing.name),responseMs:Math.max(0,timing.responseStart-timing.requestStart),dnsMs:Math.max(0,timing.domainLookupEnd-timing.domainLookupStart),tlsMs:timing.secureConnectionStart>0?Math.max(0,timing.connectEnd-timing.secureConnectionStart):0};}

  function resourceBusy(){const selectors='[data-testid="stop-button"],button[aria-label="Stop"],button[aria-label="Stop generating"],button[aria-label="Stop streaming"],button[aria-label="停止"],button[aria-label="停止生成"]';return [...document.querySelectorAll(selectors)].slice(0,32).some(rendered);}
  function uploadBusy(){const input=composer(),zone=input&&(input.closest('form')||input.parentElement?.parentElement);return !!zone&&[...zone.querySelectorAll('[data-state="uploading"],[data-upload-state="uploading"],[role="progressbar"],[aria-busy="true"]')].slice(0,64).some(visible);}
  if (action === 'observe-install') return {ok:!!window.__pocketInstallWebReplyObserver?.({composer,draft,sendButton,busy,resourceBusy,uploadBusy,messages,key,userText,hasMessages},arg.resourceBinding||'')};
  if (action === 'inspect') return ready();
  function webModelInfo(){const saved=window.__pocketModelControls||(window.__pocketModelControls={});if(!saved.model?.isConnected||!visible(saved.model))saved.model=modelControl();if(!saved.effort?.isConnected||!visible(saved.effort)){saved.effort=[...document.querySelectorAll('button[aria-label],[role="button"][aria-label]')].find(el=>el!==saved.model&&/thinking effort|reasoning effort|思考强度|推理强度|思考时间|thinking time/i.test(el.getAttribute('aria-label')||'')&&visible(el))||null;}const text=saved.model?norm(saved.model.innerText||saved.model.getAttribute('aria-valuetext')||label(saved.model)):'';return {text,effort:saved.effort?norm(saved.effort.innerText||saved.effort.getAttribute('aria-label')):'',known:!!saved.model};}
  if(action==='web-inspect'){const model=webModelInfo(),meta=window.__pocketWebPerformance?.meta();return {url:location.href,documentId:documentKey(),title:document.title,composer:!!composer(),hasMessages:hasMessages(),contentKey:arg.navigationCheck?contentKey():'',model:model.text,effort:model.effort,modelKnown:model.known,busy:busy(),...siteObservation(null,true),transcriptDirty:!meta||meta.dirty,interacting:!!meta?.interacting};}

  function assistantScope(el){return el && (el.closest('[data-turn="assistant"],[data-testid^="conversation-turn-"],[data-content-search-turn-key],[data-turn-key],article')||el.closest('[data-conversation-screenshot-content]')||el.parentElement||el);}
  function entryNodes(){return [...messages('user'),...messages('assistant')].sort((a,b)=>(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING)?-1:1);}
  function byEntry(id){const nodes=entryNodes();return nodes.find((el,i)=>key(el,i)===id);}
  const extension=/\.(?:docx?|pdf|xlsx?|pptx?|csv|txt|md|zip|png|jpe?g|webp|gif|svg|json|xml|html|py|ipynb|js|mp3|mp4)(?:$|[\s?#])/i;
  function fileControls(message){const scope=assistantScope(message);if(!scope)return [];const found=[],covered=[];const fileName=e=>norm(e.getAttribute('download')||e.getAttribute('aria-label')||e.getAttribute('title')||e.innerText);const nameFrom=e=>{const lines=[...e.querySelectorAll('[title],[aria-label],span,p,a,button')].map(fileName).filter(t=>t.length<180&&extension.test(t));return lines.find(t=>/\.(?:docx?|pdf|xlsx?|pptx?|csv|txt|md|zip|png|jpe?g|webp|gif|svg|json|xml|html|py|ipynb|js|mp3|mp4)$/i.test(t))||lines.find(t=>!/^download|^下载/i.test(t))||lines[0]||'';};
    for(const b of scope.querySelectorAll('button'))if(/^(Download file|下载文件)$/i.test(fileName(b))){let card=b.parentElement,name='';for(let i=0;card&&card!==scope&&i<5;i++,card=card.parentElement){name=nameFrom(card);if(name)break;}if(name){found.push({el:b,name});if(card)covered.push(card);}}
    for(const el of scope.querySelectorAll('a,button')){if(covered.some(p=>p.contains(el))||el.closest('pre,[data-markdown-copy="code-block"]'))continue;const raw=el.getAttribute('href')||'',name=fileName(el);if(el.tagName==='A'&&(el.hasAttribute('download')||/^sandbox:|^blob:/.test(raw)||/\/backend-api\/files\//.test(raw)||extension.test(raw))||el.tagName==='BUTTON'&&extension.test(name)){if(name&&!/^(Copy|复制)/i.test(name))found.push({el,name});}}
    let imageIndex=0;
    for(const img of scope.querySelectorAll('img')){const src=img.currentSrc||img.src||'';if(!/^(https:|blob:https:)/.test(src)||img.naturalWidth<120||img.naturalHeight<100||img.closest('button[data-testid*="avatar"],pre'))continue;imageIndex++;let card=img.parentElement,download=null;for(let depth=0;card&&card!==scope&&depth<5;depth++,card=card.parentElement){const original=e=>/^(Download original(?: image)?|Download full(?:-size| size)(?: image)?|下载原图|保存原图|原图下载)$/i.test(fileName(e)),buttons=[...card.querySelectorAll('button,a')].filter(e=>original(e)||/^(Download(?: this)? image|Save image|Download|下载(?:此)?图片|保存图片)$/i.test(fileName(e))),originals=buttons.filter(original);if(originals.length===1){download=originals[0];break;}if(buttons.length===1){download=buttons[0];break;}}const name='图片 '+imageIndex;if(!download){const explicit=img.closest('a[download]');if(explicit)download=explicit;}if(download){if(!found.some(f=>f.el===download))found.push({el:download,name,kind:'image'});}else found.push({el:img,name,kind:'image',direct:src,keySeed:'image:'+Array.from(src).reduce((n,c)=>(Math.imul(n,31)+c.charCodeAt(0))>>>0,0)});}
    const seen=new Set();return found.filter(x=>!seen.has(x.name)&&seen.add(x.name)).map((x,i)=>({...x,key:x.keySeed||x.name+'|'+i}));
  }
  function fileTarget(){const el=byEntry(arg.id);return el?fileControls(el).find(x=>x.key===arg.key):null;}
  function touch(el){const r=el.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight)return null;return {x:Math.max(1,Math.min(innerWidth-1,r.left+r.width/2)),y:Math.max(1,Math.min(innerHeight-1,r.top+r.height/2)),width:innerWidth,height:innerHeight};}
  if(action==='file-prepare'||action==='file-point'){if(arg.expectedUrl&&new URL(arg.expectedUrl).pathname!==location.pathname)return {ok:false,reason:'对话已经改变'};const f=fileTarget();if(!f)return {ok:false,reason:'文件已不在当前网页，请先加载原对话'};if(action==='file-prepare')f.el.scrollIntoView({block:'center'});return {ok:true,name:f.name,kind:f.kind||"file",direct:f.direct||"",touch:touch(f.el)};}
  if(action==='file-followup'){if(new URL(arg.expectedUrl).pathname!==location.pathname)return {ok:false};const dialogs=[...document.querySelectorAll('[role="dialog"]')].filter(visible).filter(d=>d.textContent.includes(arg.name));if(dialogs.length!==1)return {ok:false};const buttons=[...dialogs[0].querySelectorAll('button,a')].filter(visible).filter(b=>/^(Download|Download file|下载|下载文件)$/i.test(norm(b.getAttribute('aria-label')||b.innerText)));if(buttons.length!==1)return {ok:false};buttons[0].scrollIntoView({block:'center'});return {ok:true,touch:touch(buttons[0])};}
  function transcriptEntry(el,index,userSet){
      if(userSet.has(el)){const files=[];for(const n of el.querySelectorAll('[data-file-name],a[download],button[aria-label],img[alt]')){const label=n.getAttribute('aria-label')||'',match=/^Open image(?: \d+ of \d+)?: (.+)$/i.exec(label);const name=n.getAttribute('data-file-name')||n.getAttribute('download')||(match&&match[1]);if(name)files.push(name);}if(!files.length&&el.querySelector('img'))files.push('图片附件');return {id:key(el,index),role:'user',text:observedUserText(el),attachments:[...new Set(files)]};}
      const excluded='[data-testid*="reasoning"],[data-testid*="thinking"],[data-is-reasoning="true"],[data-markdown-text-style="reasoning"]';
      let bodies=[...el.querySelectorAll('.markdown,[data-markdown-text-style="assistant-message"]')].filter(x=>!x.closest(excluded));
      bodies=bodies.filter(x=>!bodies.some(other=>other!==x&&other.contains(x)));
      if(!bodies.length&&el.matches('[data-message-author-role="assistant"],article[data-turn="assistant"]')&&!el.querySelector(excluded))bodies=[el];
      return {id:key(el,index),role:'assistant',text:bodies.map(observedMarkdown).join('\n\n'),downloads:observedFiles(el).map(x=>({name:x.name,key:x.key,kind:x.kind||"file"}))};

  }
  if(action==='transcript'||action==='web-transcript'){
    if(action==='web-transcript'){if(!window.__pocketInstallWebPerformance)return {ok:false,error:'网页缓存尚未就绪'};return window.__pocketInstallWebPerformance({nodes:entryNodes,users:()=>messages('user'),key,entry:transcriptEntry,dependency:assistantScope}).snapshot(arg);}
    const users=new Set(messages('user'));const entries=entryNodes().map((el,i)=>transcriptEntry(el,i,users)).filter(x=>x.role==='user'||x.text.trim()||x.downloads?.length);
    return {ok:true,url:location.href,title:document.title,entries};
  }
  if(action==='chats') {
    const links=[...document.querySelectorAll('a[href]')].filter(visible).filter(el=>{
      try {const u=new URL(el.href);return !u.hash && u.origin===location.origin && /^\/(?:g\/[^/]+\/)?c\/[^/]+$/.test(u.pathname) && !/^(跳转到内容|Skip to content)$/i.test(norm(el.innerText));}catch{return false;}
    });
    const seen=new Set();return {ok:true,chats:links.map(el=>({title:norm(el.innerText || el.getAttribute('aria-label')) || '未命名聊天',url:new URL(el.href).origin+new URL(el.href).pathname})).filter(x=>!seen.has(x.url)&&seen.add(x.url))};
  }
  if (action === 'poll' || action === 'latest') {
    const bindingPending=reason=>({url:location.href,...siteObservation(null,!!arg.lightObservation),
      submitted:false,bindingPending:true,bindingReason:reason,pageLoading:true,contentObserved:false,busy:busy(),terminal:false});
    let assigningConversation=false;
    if (action === 'poll') {
      if (arg.kind==='web'&&!arg.confirmed) return {url:location.href,submitted:false,busy:busy(),terminal:false,
        error:arg.webSuspended?'这次网页发送缺少可核实的消息标识，请核对原网页；不会自动重发':''};
      const boundUrl=arg.confirmedUrl||arg.expectedUrl,expected=boundUrl?new URL(boundUrl):null;
      const home=path=>/^\/(?:g\/[^/]+\/?)?$/.test(path),conversation=path=>/^\/(?:g\/[^/]+\/)?c\/[^/]+\/?$/.test(path);
      if (expected&&(arg.kind==='web'||conversation(expected.pathname))&&(expected.origin !== location.origin || expected.pathname !== location.pathname)){
        // The first message can get its stable ID before the website assigns
        // /c/id. Only that exact ID and prompt may bind the assigned route.
        assigningConversation=expected.origin===location.origin&&home(expected.pathname)&&conversation(location.pathname)&&/^(id|unit):/.test(arg.userKey||'');
        if(!assigningConversation){
          if(expected.origin===location.origin&&conversation(expected.pathname)&&home(location.pathname)&&!composer(true)&&!hasMessages())return bindingPending('route-loading');
          return {url:location.href,submitted:false,bindingLost:true,conversationChanged:true,contentObserved:false,terminal:false,error:'已离开原网页对话，请返回原对话继续核对'};
        }
      }
    }
    const users=messages('user'), assistants=messages('assistant');
    let user=null, userIndex=-1;
    let boundByNewIdentity=false;
    if(action==='latest')userIndex=users.length-1;
    else if (arg.userKey) {
      userIndex=users.findIndex((el,i)=>key(el,i)===arg.userKey || (arg.kind!=='web'&&legacyKey(el,i)===arg.userKey));
      // A reload, hydration or virtualized scroll may temporarily remove the
      // bound turn. Its absence is not evidence that another question was sent.
      if(userIndex<0)return bindingPending(assigningConversation?'conversation-assigning':'message-not-rendered');
      const boundUser=users[userIndex],boundText=observedUserText(boundUser);
      if(!signature(boundText)&&signature(arg.prompt))return bindingPending('message-loading');
      const matches=assigningConversation&&signature(arg.prompt)?signature(boundText)===signature(arg.prompt):samePrompt(boundText,arg.prompt);
      if(!matches)return {url:location.href,error:'已绑定的提问正文发生变化，请检查网页。',submitted:false,bindingLost:true,contentObserved:false,text:'',terminal:false};
    }else if(Array.isArray(arg.beforeUserKeys)){
      const previous=new Set(arg.beforeUserKeys), newUsers=users.map((el,index)=>({el,index,key:key(el,index)})).filter(x=>!previous.has(x.key));
      if(newUsers.length>1)return {url:location.href,error:siteError(),submitted:false,otherQuestion:true,busy:busy(),text:'',terminal:false};
      if(newUsers.length===1 && samePrompt(observedUserText(newUsers[0].el),arg.prompt)){userIndex=newUsers[0].index;boundByNewIdentity=true;}
    }else{
      if(users.length>arg.beforeUserCount+1)return {url:location.href,error:siteError(),submitted:false,otherQuestion:true,busy:busy(),text:'',terminal:false};
      if(users.length===arg.beforeUserCount+1 && samePrompt(observedUserText(users[users.length-1]),arg.prompt))userIndex=users.length-1;
    }
    if (userIndex>=0) user=users[userIndex];
    const laterUser=user ? users.find(el=>el!==user && !!(user.compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING)) : null;
    let replies=user ? assistants.filter(el=>(user.compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING) &&
      (!laterUser || (el.compareDocumentPosition(laterUser)&Node.DOCUMENT_POSITION_FOLLOWING))) : [];
    const reply=replies[replies.length-1] || null;
    const reasoning='[data-testid*="reasoning"],[data-testid*="thinking"],[data-is-reasoning="true"],[data-markdown-text-style="reasoning"]';
    let bodies=replies.flatMap(el=>[...el.querySelectorAll('.markdown,[data-markdown-text-style="assistant-message"]')]).filter(el=>!el.closest(reasoning));
    bodies=bodies.filter(el=>!bodies.some(other=>other!==el && other.contains(el)));
    if (reply && !bodies.length && reply.matches('[data-message-author-role="assistant"],article[data-turn="assistant"]') && !reply.matches(reasoning) && !reply.querySelector(reasoning))bodies=[reply];
    // Current ChatGPT places response actions beside the message body inside a
    // section, not necessarily an article. Stay within this assistant turn so
    // an earlier response's copy button cannot complete the current response.
    const scope=reply && (reply.closest('[data-turn="assistant"],[data-testid^="conversation-turn-"],[data-content-search-turn-key],[data-turn-key],article') || reply.closest('[data-conversation-screenshot-content]') || reply.parentElement || reply);
    const terminalAction=el=>!el.closest('pre,[data-markdown-copy="code-block"]') && rendered(el) && !el.disabled &&
      (el.matches('[data-testid="copy-turn-action-button"],[data-testid="good-response-turn-action-button"],[data-testid="bad-response-turn-action-button"]') || /^(复制|复制回复|复制内容|Copy|Copy response|Copy message|Copy answer|已复制|Copied)$/i.test((el.getAttribute('aria-label')||el.innerText||'').trim()));
    let actionScope=reply,terminal=false;
    // Actions can be siblings of the body. Stop before an ancestor containing
    // another assistant or a user message, so previous replies cannot finish this one.
    for(let depth=0;actionScope&&depth<6;depth++,actionScope=actionScope.parentElement){
      if(users.some(el=>el!==user&&actionScope.contains(el))||assistants.some(el=>el!==reply&&actionScope.contains(el)))break;
      if([...actionScope.querySelectorAll('button,[role="button"]')].some(el=>terminalAction(el)&&!el.closest('[data-message-author-role="user"],[data-turn="user"]')&&(!actionScope.contains(user)||(reply.compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING)))){terminal=true;break;}
    }
    const working=!!scope && [...scope.querySelectorAll('button')].some(el=>visible(el) && /^(正在思考|正在搜索|Thinking|Searching)(\b|…|\.\.\.|$)/i.test(label(el)));
    const activeBusy=busy()||working;const liveLabels=scope?[...scope.querySelectorAll('button,[role="status"]')].filter(visible).map(label):[];const thinking=activeBusy&&liveLabels.some(t=>/^(?:Thinking|正在思考|思考中)(?:\b|…|\.\.\.|$)/i.test(t));const searching=activeBusy&&liveLabels.some(t=>/^(?:Searching|正在搜索|搜索中)(?:\b|…|\.\.\.|$)/i.test(t));
    const problem=siteObservation(scope,!!arg.lightObservation);
    // Website connection notices can sit beside, rather than inside, the
    // current assistant turn. Inspect only official alert/retry surfaces.
    const globalProblem=scope?siteObservation(null,true):problem;
    const websiteProblem=globalProblem.websiteSocketClosed?globalProblem:problem;
    const replyKey=reply?key(reply,assistants.indexOf(reply)):'';
    const incremental=!!arg.incrementalObservation&&!!window.__pocketWebPerformance;
    const contentRevision=incremental?window.__pocketWebPerformance.contentRevision([...replies,...bodies,...replies.map(assistantScope)]):'';
    const result={url:location.href,...websiteProblem,thinking,searching,busy:activeBusy,submitted:!!user,
      userKey:user?key(user,userIndex):'',userOrdinal:userIndex,boundByNewIdentity,otherQuestion:!!laterUser,
      replyKey,terminal,...(assigningConversation&&user&&!laterUser?{routeAssigned:true}:{})};
    if(incremental){
      // Generation metadata is enough to observe progress. Reading the entire
      // growing answer here competes with the site's rendering and gestures.
      result.hasReply=bodies.some(node=>node.childNodes.length>0);
      result.replyContentRevision=contentRevision;
      result.contentObserved=!activeBusy;
      if(activeBusy)return result;
      if(replyKey&&contentRevision===arg.knownReplyContentRevision&&replyKey===arg.knownReplyKey){result.contentUnchanged=true;return result;}
      const captureNodes=[...replies,...bodies,...replies.map(assistantScope)],captureUrl=location.href;
      if(window.__pocketWebPerformance.deferCapture(captureUrl+'|'+replyKey+'|'+contentRevision,()=>{
        if(location.href!==captureUrl||captureNodes.some(node=>!node.isConnected)||window.__pocketWebPerformance.contentRevision(captureNodes)!==contentRevision)return false;
        if(reply)observedFiles(reply);bodies.forEach(observedMarkdown);return true;
      })){result.contentObserved=false;result.captureDeferred=true;return result;}
      result.hasFiles=!!reply&&observedFiles(reply).length>0;
      result.markdown=arg.export?bodies.map(observedMarkdown).join('\n\n'):'';
      return result;
    }
    return {...result,hasFiles:!!reply&&observedFiles(reply).length>0,prompt:user?observedUserText(user):'',
      text:bodies.map(el=>el.innerText).join('\n\n'),markdown:arg.export?bodies.map(observedMarkdown).join('\n\n'):''};
  }
  return {ok:false,reason:'Unknown command'};
})(__ACTION__, __ARG__)

