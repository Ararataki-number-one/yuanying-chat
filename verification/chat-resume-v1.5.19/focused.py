"""Real Chromium, locked before/current sources, paired page-thread workloads.

This deliberately measures specific helper overhead, not app/Android FPS or
live-network timing. All content is local, no account or credentials are read.
"""
import asyncio
import json
import pathlib
import subprocess
import statistics
from playwright.async_api import async_playwright

ROOT = pathlib.Path('/workspace/yuanying-chat')
BASE = 'e2eb37a'
ASSETS = ['page-driver.js', 'web-performance.js', 'web-reply-observer.js']
SOURCES = {
    'before': {name: subprocess.check_output(
        ['git', 'show', f'{BASE}:app/src/main/assets/{name}'], cwd=ROOT, text=True
    ) for name in ASSETS},
    'after': {name: (ROOT / 'app/src/main/assets' / name).read_text() for name in ASSETS}
}
HTML = '''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;font:16px sans-serif}main{height:580px;overflow:auto;contain:layout}
article,section{padding:12px}button{min-height:25px}.markdown p{margin:8px}
textarea{height:55px;width:90%}.pulse0{opacity:.999}.pulse1{opacity:1}</style>
<main></main><textarea id="prompt-textarea">preserve unsent draft</textarea>
<button data-testid="send-button" aria-label="Send">Send</button>
<button data-testid="model-switcher-dropdown-button" aria-label="Select model">Select model</button>
<aside></aside>'''
SETUP = r'''() => {
 const main=document.querySelector('main');
 for(let i=0;i<240;i++){
  const role=i%2?'assistant':'user';
  main.insertAdjacentHTML('beforeend',`<article data-message-author-role="${role}" data-message-id="h${i}">${role==='user'?'history question '+i:'<div class="markdown"><p>'+('history content '.repeat(25))+'</p></div>'}${Array.from({length:4},(_,j)=>'<button aria-label="Historical action '+j+'">action</button>').join('')}</article>`);
 }
 main.insertAdjacentHTML('beforeend','<article data-message-author-role="user" data-message-id="bound-user"><div data-user-message-bubble>bound question</div></article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="bound-answer"><div class="markdown"><p id="stream">'+('long answer '.repeat(10000))+'</p><pre><code class="language-js">const keep = 1;</code></pre></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button>'+Array.from({length:16},(_,i)=>'<span id="decor-'+i+'">metadata</span>').join('')+'</section>');
 const sidebar=document.querySelector('aside');sidebar.insertAdjacentHTML('beforeend',Array.from({length:128},(_,i)=>'<span id="sidebar-'+i+'">sidebar</span>').join(''));
 main.scrollTop=main.scrollHeight;
 window.focused={observers:{},gestures:[],rects:0,styles:0,started:0,events:[]};
 document.addEventListener('click',event=>{if(event.isTrusted){focused.started=performance.now();focused.rects=focused.styles=0;}},true);
 const nativeRects=Element.prototype.getClientRects,nativeStyles=getComputedStyle;
 Element.prototype.getClientRects=function(...args){focused.rects++;return nativeRects.apply(this,args);};
 window.getComputedStyle=function(...args){focused.styles++;return nativeStyles.apply(this,args);};
 const NativeObserver=MutationObserver;
 window.MutationObserver=class extends NativeObserver{constructor(callback){const label=window.observerLabel||'unknown';super((records,self)=>{const start=performance.now();callback(records,self);const saved=focused.observers[label]||(focused.observers[label]={durationMs:0,batches:0,records:0,maxMs:0});const duration=performance.now()-start;saved.durationMs+=duration;saved.maxMs=Math.max(saved.maxMs,duration);saved.batches++;saved.records+=records.length;});}};
 window.PocketWebReply={postMessage:value=>focused.events.push(JSON.parse(value))};
}'''
MUTATE = r'''async () => {
 focused.observers={};
 const stream=document.querySelector('#stream').firstChild;
 const decor=Array.from({length:16},(_,i)=>document.getElementById('decor-'+i));
 const sidebar=Array.from({length:128},(_,i)=>document.getElementById('sidebar-'+i));
 const start=performance.now();
 for(let batch=0;batch<80;batch++){
  for(let i=0;i<32;i++)stream.nodeValue+=' '+batch+':'+i;
  for(const element of decor)element.className='pulse'+batch%2;
  for(const element of sidebar)element.className='pulse'+batch%2;
  await new Promise(resolve=>setTimeout(resolve,0));
 }
 const elapsedMs=performance.now()-start;
 const observed=JSON.parse(JSON.stringify(focused.observers)),stats=__pocketWebPerformance.stats();
 const reply=driver('poll',{kind:'web',confirmed:true,userKey:'id:bound-user',prompt:'bound question',expectedUrl:location.href,confirmedUrl:location.href,export:true,incrementalObservation:true,lightObservation:true});
 return {elapsedMs,observed,stats,fullFinalTextPreserved:reply.markdown?.includes('79:31')&&reply.markdown?.includes('```js\nconst keep = 1;')&&reply.markdown?.startsWith('long answer'),finalBodyChars:reply.markdown?.length};
}'''

async def run(browser, variant):
    context = await browser.new_context(viewport={'width': 390, 'height': 740})
    await context.route('**/*', lambda route: route.fulfill(
        status=200, content_type='text/html', body=HTML))
    page = await context.new_page()
    await page.goto('https://chatgpt.com/c/focused')
    cdp = await context.new_cdp_session(page)
    await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    await page.evaluate(SETUP)
    source = SOURCES[variant]
    await page.evaluate(source['web-performance.js'])
    await page.evaluate(source['web-reply-observer.js'])
    await page.evaluate('window.driver=(action,arg)=>' + source['page-driver.js'].replace(
        '__ACTION__', 'action').replace('__ARG__', 'arg'))
    await page.evaluate('''() => {
      window.observerLabel='reply';driver('observe-install',{});
      window.observerLabel='performance';driver('web-transcript',{});
      document.addEventListener('click',event=>{if(event.isTrusted)focused.gestures.push({delayMs:performance.now()-focused.started,rects:focused.rects,styles:focused.styles});},true);
    }''')
    await page.wait_for_timeout(100)
    for _ in range(20):
        await page.locator('[aria-label="Select model"]').click()
    clicks = await page.evaluate('''() => ({gestures:focused.gestures,
      buttonCount:document.querySelectorAll('button').length,
      noSendIntents:!focused.events.some(event=>event.type==='intent')})''')
    mutation = await page.evaluate(MUTATE)
    preserved = await page.evaluate('document.querySelector("textarea").value')
    await context.close()
    return {'variant': variant, 'clicks': clicks, 'mutation': mutation,
            'draftPreserved': preserved == 'preserve unsent draft'}

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path='/usr/bin/chromium',
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            # Interleaving avoids treating cold browser or instance drift as a gain.
            results = [await run(browser, variant) for variant in
                       ['before', 'after', 'after', 'before', 'before', 'after']]
            summary = {}
            for variant in ['before', 'after']:
                chosen = [result for result in results if result['variant'] == variant]
                gestures = [gesture for result in chosen for gesture in result['clicks']['gestures']]
                summary[variant] = {
                    'clickSamples': len(gestures),
                    'medianClickDelayMs': statistics.median(g['delayMs'] for g in gestures),
                    'maxClickDelayMs': max(g['delayMs'] for g in gestures),
                    'medianClickRectReads': statistics.median(g['rects'] for g in gestures),
                    'medianClickStyleReads': statistics.median(g['styles'] for g in gestures),
                    'medianMutationObserverMs': statistics.median(
                        r['mutation']['observed']['performance']['durationMs'] for r in chosen),
                    'medianReplyObserverMs': statistics.median(
                        r['mutation']['observed']['reply']['durationMs'] for r in chosen),
                    'medianWorkloadElapsedMs': statistics.median(r['mutation']['elapsedMs'] for r in chosen),
                    'recordsPerRun': chosen[0]['mutation']['observed']['performance']['records'],
                    'batchesPerRun': chosen[0]['mutation']['observed']['performance']['batches'],
                    'fullBodiesAndDraftsPreserved': all(r['mutation']['fullFinalTextPreserved'] and r['draftPreserved'] for r in chosen),
                    'noSendIntents': all(r['clicks']['noSendIntents'] for r in chosen),
                }
            output = {'scope': 'Real Chromium 4x CPU, offline controlled DOM, fixed workload, paired locked before/current assets; helper overhead only, not Android/Gecko FPS or live-network performance',
                      'browser': browser.version, 'baseCommit': BASE,
                      'summary': summary, 'runs': results}
            (ROOT / 'work/browser-interaction-audit/focused-results.json').write_text(json.dumps(output, indent=2))
            print(json.dumps({k:v for k,v in output.items() if k != 'runs'}, indent=2))
        finally:
            await browser.close()

asyncio.run(main())
