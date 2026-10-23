(async function(action,arg){
 'use strict';
 if(action!=='attachment-state')return {ok:false,reason:'请在 ChatGPT 原网页中操作'};
 if(location.protocol!=='https:'||location.hostname!=='chatgpt.com')return {ok:false,reason:'请先完成 ChatGPT 登录'};
 if(arg.url&&new URL(arg.url).pathname!==location.pathname)return {ok:false,reason:'对话已经改变，未继续操作'};
 const norm=s=>String(s||'').replace(/\s+/g,' ').trim();
 const editor=document.querySelector('#prompt-textarea,[data-composer-markdown],[contenteditable="true"].ProseMirror');
 const zone=editor&&(editor.closest('form')||editor.parentElement.parentElement)||document;
 const documentId=window.__pocketAttachmentDocumentId||(window.__pocketAttachmentDocumentId=crypto.randomUUID?crypto.randomUUID():[...crypto.getRandomValues(new Uint8Array(16))].map(n=>n.toString(16).padStart(2,'0')).join(''));
 if(arg.documentId&&arg.documentId!==documentId)return {ok:false,reason:'附件所属网页已改变',documentId};
 const removeButtons=root=>[...root.querySelectorAll('button,[role="button"]')].filter(b=>/^(Remove (?:file|attachment|image)|Remove$|移除|删除附件|删除文件)/i.test(norm(b.getAttribute('aria-label')||b.getAttribute('title')||b.innerText)));
 function cards(name){const liveEditor=document.querySelector('#prompt-textarea,[data-composer-markdown],[contenteditable="true"].ProseMirror'),zone=liveEditor&&(liveEditor.closest('form')||liveEditor.parentElement.parentElement);if(!zone)return [];const nodes=[...zone.querySelectorAll('[data-file-name],[title],[aria-label],img[alt],span,p,div')].filter(e=>e.getAttribute('data-file-name')===name||e.getAttribute('title')===name||e.getAttribute('aria-label')===name||e.getAttribute('alt')===name||(e.children.length===0&&norm(e.textContent)===name));const found=[];
   for(const e of nodes){let root=e;for(let i=0;root&&root!==zone&&i<7;i++,root=root.parentElement){if(removeButtons(root).length===1){found.push(root);break;}}}
   return [...new Set(found)].filter(e=>!found.some(other=>other!==e&&e.contains(other)));
 }
 function fileState(name){const list=cards(name);if(list.length!==1)return {name,state:'unknown',matches:list.length,progress:-1,reason:list.length>1?'同名附件无法唯一识别':'网页中未确认这个附件'};const root=list[0],text=norm(root.textContent),bars=[...root.querySelectorAll('[role="progressbar"],[aria-busy="true"],[class*="animate-spin"],[data-state="uploading"]')].filter(e=>e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden');let state=root.getAttribute('data-upload-state'),progress=-1;for(const b of bars){const v=b.getAttribute('aria-valuenow'),min=Number(b.getAttribute('aria-valuemin')||0),max=Number(b.getAttribute('aria-valuemax')||100);if(v!==null&&Number.isFinite(Number(v))&&max>min)progress=Math.max(0,Math.min(100,Math.round((Number(v)-min)*100/(max-min))));}if(state==='error'||/upload failed|failed to upload|上传失败|处理失败|error uploading/i.test(text))state='error';else if(bars.length||state==='uploading'||/uploading|processing|正在上传|正在处理/i.test(text))state='uploading';else state='ready';return {name,state,matches:1,progress,reason:state==='ready'?'网页附件卡片已就绪':state==='error'?'网页报告上传失败':'等待网页完成上传或处理'};}
 window.__pocketCheckAttachments=names=>(names||[]).map(fileState);
 if(action==='attachment-state'){
   const visible=e=>e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
   const composerAvailable=document.visibilityState!=='hidden'&&!!editor&&visible(editor)&&zone!==document;
   const uploading=!!composerAvailable&&[...zone.querySelectorAll('[data-state="uploading"],[data-upload-state="uploading"],[role="progressbar"],[aria-busy="true"],[class*="animate-spin"]')].some(visible);
   const batches=Array.isArray(arg.batches)?arg.batches:[],kept=new Set(batches.map(batch=>batch.batchId));
   const nameUses=new Map();for(const batch of batches)if(Array.isArray(batch.names))for(const name of batch.names)nameUses.set(name,(nameUses.get(name)||0)+1);
   const records=window.__pocketAttachmentBatches||(window.__pocketAttachmentBatches=new Map());
   // Legacy attachment checks do not own native selection batches.
   if(Array.isArray(arg.batches))for(const key of records.keys())if(!kept.has(key))records.delete(key);
   const observed=batches.map(batch=>{
     if(typeof batch.batchId!=='string'||!Array.isArray(batch.names)||batch.documentId&&batch.documentId!==documentId)return {batchId:batch.batchId,sequence:0,files:[]};
     let record=records.get(batch.batchId);if(!record){record={seen:new Set(),sequence:0};records.set(batch.batchId,record);}
     const files=batch.names.map(name=>{
       const file=fileState(name);
       if(!composerAvailable||file.matches>0&&!cards(name).every(visible))return {...file,state:'unknown',reason:'当前输入区或附件不可见，等待网页重新核对'};
       if(nameUses.get(name)>1)return {...file,state:'unknown',reason:'多次选择了同名附件，无法安全区分每一批文件'};
       if(file.matches>0)record.seen.add(name);
       if(file.state!=='unknown'||file.matches!==0||!composerAvailable||uploading)return file;
       const evidence=window.__pocketWebReplyObserver?.attachmentEvidence?.(name,batch.selectedAt)||{};
       if(evidence.sent)return {...file,state:'sent',reason:'网页已确认发送，输入区已无此附件或上传任务'};
       if(evidence.removed||record.seen.has(name))return {...file,state:'removed',reason:'附件已离开输入区，网页未显示上传任务'};
       return file;
     });
     return {batchId:batch.batchId,sequence:++record.sequence,files};
   });
   return {ok:true,documentId,composerAvailable,uploading,files:(arg.names||[]).map(fileState),batches:observed};
 }
 return {ok:false,reason:'未知附件操作'};
})(__ACTION__,__ARG__)

