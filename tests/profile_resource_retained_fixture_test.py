"""Actual fixture origin adapter and complete production JS on the host.

Java helpers are extracted from the integration Activity and executed on a JVM.
JSDOM uses explicit geometry/timer adapters. These checks do not execute Android,
Gecko, real ChatGPT, real uploads, or trusted physical gestures.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / 'tests/gecko/ResourcePressureIntegrationActivity.java'
ASSETS = ROOT / 'app/src/main/assets'
PINNED_JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')
ORIGIN = 'http://127.0.0.1:44157'
NONCE = 'a' * 32
OBSERVER_GUARD = "location.origin !== 'https://chatgpt.com'"
DRIVER_GUARD = "location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'"


def java_method(source, name):
    match = re.search(r'\bstatic\s+String\s+' + re.escape(name) + r'\s*\([^)]*\)\s*(?:throws\s+IOException\s*)?\{', source)
    if match is None:
        raise AssertionError('Actual fixture helper is absent: ' + name)
    cursor, depth, quote = match.end(), 1, None
    while cursor < len(source):
        char = source[cursor]
        if quote:
            if char == '\\':
                cursor += 2
                continue
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif source.startswith('//', cursor):
            end = source.find('\n', cursor)
            cursor = len(source) if end < 0 else end
            continue
        elif source.startswith('/*', cursor):
            end = source.find('*/', cursor + 2)
            if end < 0:
                raise AssertionError('Unterminated Java helper comment')
            cursor = end + 2
            continue
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if not depth:
                return source[match.start():cursor + 1]
        cursor += 1
    raise AssertionError('Incomplete Java fixture helper: ' + name)


JAVA_MAIN = r'''
  interface Work { void run() throws Exception; }
  static void rejected(Work call) throws Exception {
    try { call.run(); } catch(IOException expected) { return; }
    throw new AssertionError("Fixture adapter accepted an invalid owner/source");
  }
  public static void main(String[] args) throws Exception {
    String script=Files.readString(Path.of(args[1])),origin=args[3],nonce=args[4];
    switch(args[0]) {
      case "adapt":
        Files.writeString(Path.of(args[2]),resourceFixtureObserverScript(script,origin,nonce));
        break;
      case "owner-policy":
        for(String invalid:new String[]{null,"","https://127.0.0.1:44157","http://localhost:44157",
            "http://127.0.0.1","http://127.0.0.1:0","http://127.0.0.1:65536",
            "http://127.0.0.1:44157/","http://127.0.0.1:44157/resource",
            "http://127.0.0.1:44157?owner=other","http://127.0.0.1:44157#other",
            "http://127.0.0.1:44157@foreign.example"})
          rejected(()->resourceFixtureObserverScript(script,invalid,nonce));
        for(String invalid:new String[]{null,"","a".repeat(31),"a".repeat(33),"g".repeat(32),"A".repeat(32)})
          rejected(()->resourceFixtureObserverScript(script,origin,invalid));
        break;
      case "source-guards": {
        String observer="location.origin !== 'https://chatgpt.com'";
        String driver="location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'";
        for(String invalid:new String[]{null,"","not a guarded observer",script.replace(observer,"false"),
            script.replace(driver,"false"),script+observer,script+driver})
          rejected(()->resourceFixtureObserverScript(invalid,origin,nonce));
        rejected(()->replaceResourceFixtureGuard(script,"missing guard","false"));
        rejected(()->replaceResourceFixtureGuard(script+observer,observer,"false"));
        rejected(()->replaceResourceFixtureGuard(null,observer,"false"));
        rejected(()->replaceResourceFixtureGuard(script,null,"false"));
        rejected(()->replaceResourceFixtureGuard(script,"","false"));
        rejected(()->replaceResourceFixtureGuard(script,observer,null));
        String replaced=replaceResourceFixtureGuard("left SENTINEL right","SENTINEL","kept");
        if(!replaced.equals("left kept right"))throw new AssertionError("Exact replacement changed unrelated bytes");
        break;
      }
      default: throw new AssertionError("Unknown JVM host control");
    }
    System.out.println("PASS "+args[0]+"; host Java only");
  }
'''


NODE_MAIN = r'''
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const [mode,originalPath,adaptedPath,origin,nonce]=process.argv.slice(2);
const original=fs.readFileSync(originalPath,'utf8'),adapted=fs.readFileSync(adaptedPath,'utf8');
const observerGuard="location.origin !== 'https://chatgpt.com'";
const legacy=original.replace(observerGuard,'location.origin !== '+JSON.stringify(origin))+
  '\nwindow.__pocketFixtureResourceEvents=[];window.PocketWebReply={postMessage:text=>{const value=JSON.parse(text);if(value.type===\'resource-work\')window.__pocketFixtureResourceEvents.push(value);}};';
const html='<!doctype html><body data-sent="0"><form><textarea id="prompt-textarea">retained-resource-draft</textarea><button id="stop" data-testid="stop-button">Stop</button><div id="first" data-upload-state="uploading"></div></form><textarea id="other-draft">independent draft</textarea></body>';
const windows=[];
function fixture(url) {
  const w=new JSDOM(html,{url,runScripts:'outside-only',pretendToBeVisual:true}).window;
  windows.push(w);
  // Explicit host geometry and timer adapters, not measured browser geometry.
  Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
  w.Element.prototype.getClientRects=()=>[{}];
  w.getComputedStyle=()=>({display:'block',visibility:'visible'});
  const timers=new Map(),posts=[];let serial=0,now=1700000000000;
  w.setTimeout=(callback,delay)=>{const id=++serial;timers.set(id,{callback,delay});return id;};
  w.clearTimeout=id=>timers.delete(id);w.Date.now=()=>now;
  w.PocketWebReply={postMessage:value=>posts.push(JSON.parse(value))};
  w.document.cookie='resourceRetained=preserved;path=/';
  const flush=delay=>{
    const batch=[...timers].filter(([,item])=>item.delay===delay);
    assert.ok(batch.length<=8,'The controlled timer queue is bounded');
    now+=delay;
    for(const [id,item] of batch){timers.delete(id);item.callback();}
  };
  const install=(source,binding)=>w.eval(source+'\nwindow.__pocketReadDriver(\'observe-install\','+
    JSON.stringify({resourceBinding:binding})+');');
  const read=()=>({events:(w.__pocketFixtureResourceEvents||[]),documentId:w.__pocketWebReplyObserver?.documentId||''});
  return {w,posts,flush,install,read,timers};
}
function first(f,binding) {
  assert.equal(f.install(adapted,binding).ok,true,'Complete actual driver must install the observer');
  f.flush(250);
  const value=f.read();
  assert.match(value.documentId,/^[a-zA-Z0-9-]{16,80}$/);
  assert.equal(value.events.length,1);
  const event=value.events[0];
  assert.equal(event.documentId,value.documentId);
  assert.equal(event.resourceBinding,binding);
  assert.equal(event.type,'resource-work');
  assert.equal(event.busy,true);assert.equal(event.uploading,true);
  assert.equal(event.resourceSequence,1);assert.equal(event.url,f.w.location.href);
  return event;
}
async function run() {
  const parentUrl=origin+'/resource?run='+nonce+'&phase=parent';
  switch(mode) {
    case 'legacy-refusal': {
      for(const source of [original,legacy]) {
        const f=fixture(parentUrl);
        assert.equal(f.install(source,'initial-binding').ok,false);
        f.flush(250);
        assert.equal(f.read().documentId,'');
        assert.equal(f.read().events.length,0);
      }
      break;
    }
    case 'adapted-emission': {
      const f=fixture(parentUrl),before=f.w.document.body.innerHTML;
      const input=f.w.document.getElementById('prompt-textarea');
      input.setSelectionRange(3,7,'backward');
      const event=first(f,'parent-binding');
      assert.equal(f.w.document.body.innerHTML,before);
      assert.equal(input.value,'retained-resource-draft');
      assert.equal(input.selectionStart,3);assert.equal(input.selectionEnd,7);
      assert.equal(input.selectionDirection,'backward');
      assert.equal(f.w.document.activeElement,f.w.document.body);
      assert.equal(f.w.document.getElementById('other-draft').value,'independent draft');
      assert.match(f.w.document.cookie,/resourceRetained=preserved/);
      assert.equal(Number(f.w.document.body.dataset.sent),0);
      assert.equal(event.capturedAt,1700000000250);
      assert.equal(f.posts.length,0,'Actual fixture collector replaces the production transport stub');
      f.w.PocketWebReply.postMessage(JSON.stringify({type:'ready'}));
      assert.equal(f.read().events.length,1,'Collector retains resource-work events only');
      for(let index=1;index<=35;index++) {
        assert.equal(f.install(adapted,'bounded-refresh-'+index).ok,true);
        f.flush(250);
      }
      assert.equal(f.read().events.length,32,'Actual collector bounds retained resource bytes');
      assert.equal(f.read().events[0].resourceSequence,5);
      assert.equal(f.read().events.at(-1).resourceSequence,36);
      assert.ok(f.read().events.every(value=>value.documentId===event.documentId));
      break;
    }
    case 'retained-popup-parent': {
      const parent=fixture(parentUrl),initial=first(parent,'parent-initial');
      parent.w.history.pushState({},'',parentUrl+'&spa=1');
      assert.equal(parent.install(adapted,'parent-spa').ok,true);
      parent.flush(250);
      const spa=parent.read().events.at(-1);
      assert.equal(spa.documentId,initial.documentId);
      assert.equal(spa.resourceSequence,2);assert.equal(spa.resourceBinding,'parent-spa');
      assert.equal(spa.url,parentUrl+'&spa=1');
      const popup=fixture(origin+'/resource?run='+nonce+'&phase=popup');
      const popupEvent=first(popup,'popup-binding');
      assert.notEqual(popupEvent.documentId,initial.documentId);
      assert.equal(parent.install(adapted,'parent-returned').ok,true);
      parent.flush(250);
      const returned=parent.read().events.at(-1);
      assert.equal(returned.documentId,initial.documentId);
      assert.equal(returned.resourceSequence,3);assert.equal(returned.resourceBinding,'parent-returned');
      const delivered=parent.read().events.filter(event=>event.resourceBinding==='parent-returned');
      assert.equal(JSON.stringify(delivered),JSON.stringify([returned]),
        'Compare actual JSON message bytes across the host and document realms');
      assert.equal(popup.read().events.length,1);
      assert.equal(Number(parent.w.document.body.dataset.sent),0);
      break;
    }
    case 'foreign-owner-refusal': {
      const urls=[
        'http://localhost:44157/resource?run='+nonce+'&phase=parent',
        origin+'/foreign?run='+nonce+'&phase=parent',
        origin+'/resource?run='+'b'.repeat(32)+'&phase=parent',
        origin+'/resource?phase=parent',origin+'/resource?run='+nonce,
        origin+'/resource?run='+nonce+'&phase=foreign',
        origin+'/resource?run='+nonce+'&phase=parent&run='+nonce,
        origin+'/resource?run='+nonce+'&phase=parent&run='+'b'.repeat(32),
        origin+'/resource?run='+nonce+'&phase=parent&phase=popup',
        origin+'/resource?run='+nonce+'&phase=parent&phase=parent',
        'https://chatgpt.com/resource?run='+nonce+'&phase=parent',
      ];
      for(const url of urls) {
        const f=fixture(url);
        assert.equal(f.install(adapted,'foreign-binding').ok,false,'Foreign controlled URL must not install: '+url);
        f.flush(250);assert.equal(f.read().documentId,'');assert.equal(f.read().events.length,0);
      }
      break;
    }
    case 'original-policy': {
      const localhost=fixture(parentUrl);
      assert.equal(localhost.install(original,'original-localhost').ok,false);
      const syntheticAllowedOrigin=fixture('https://chatgpt.com/resource');
      assert.equal(syntheticAllowedOrigin.install(original,'original-policy-control').ok,true);
      syntheticAllowedOrigin.flush(250);
      assert.ok(syntheticAllowedOrigin.w.__pocketWebReplyObserver);
      assert.ok(syntheticAllowedOrigin.posts.some(event=>event.type==='resource-work'));
      const foreign=fixture('https://foreign.example/resource');
      assert.equal(foreign.install(original,'original-foreign').ok,false);
      break;
    }
    default:throw Error('Unknown JSDOM host control');
  }
  console.log('PASS '+mode+'; JSDOM host only');
}
run().then(()=>{for(const w of windows)w.close();}).catch(error=>{
  for(const w of windows)w.close();console.error(error.stack);process.exitCode=1;
});
'''


class ResourceRetainedFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or (str(PINNED_JAVA) if PINNED_JAVA.exists() else shutil.which('java'))
        cls.node = shutil.which('node')
        if not cls.java or not cls.node:
            raise RuntimeError('Host JDK and Node are required; no Android execution is substituted')
        cls.temporary = tempfile.TemporaryDirectory(prefix='resource-retained-fixture-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.asset_before = {name:(ASSETS/name).read_bytes() for name in ('web-performance.js','web-reply-observer.js','page-driver.js')}
        driver = cls.asset_before['page-driver.js'].decode().replace('__ACTION__','action').replace('__ARG__','arg')
        assembled = cls.asset_before['web-performance.js'].decode() + '\n' + cls.asset_before['web-reply-observer.js'].decode() + '\nwindow.__pocketReadDriver=(action,arg)=>' + driver + ';'
        if assembled.count(OBSERVER_GUARD) != 1 or assembled.count(DRIVER_GUARD) != 1:
            raise AssertionError('Actual production assembly no longer has one of each origin guard')
        cls.original = cls.directory / 'original-production-script.js'
        cls.adapted = cls.directory / 'actual-adapted-fixture-script.js'
        cls.original.write_text(assembled)
        source = ACTIVITY.read_text()
        helpers = '\n'.join(java_method(source,name) for name in ('replaceResourceFixtureGuard','resourceFixtureObserverScript'))
        harness = 'import java.io.*; import java.net.*; import java.nio.file.*; import java.util.*;\npublic final class ResourceFixtureHost {\n' + helpers + '\n' + JAVA_MAIN + '\n}\n'
        java_path = cls.directory / 'ResourceFixtureHost.java'
        java_path.write_text(harness)
        compiled = subprocess.run([cls.java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8',str(java_path)],
                                  text=True,capture_output=True,timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual Java fixture helpers failed to compile:\n' + compiled.stdout + compiled.stderr)
        adapted = cls.java_control('adapt')
        if adapted.returncode:
            raise AssertionError('Actual Java adapter rejected production assembly:\n' + adapted.stdout + adapted.stderr)
        cls.node_script = cls.directory / 'complete-production-driver-host.cjs'
        cls.node_script.write_text(NODE_MAIN)

    @classmethod
    def java_control(cls, mode):
        return subprocess.run([cls.java,'-cp',str(cls.directory),'ResourceFixtureHost',mode,str(cls.original),str(cls.adapted),ORIGIN,NONCE],
                              text=True,capture_output=True,timeout=30)

    def java_check(self, mode):
        result = self.java_control(mode)
        self.assertEqual(result.returncode,0,result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(),'PASS ' + mode + '; host Java only')

    def node_check(self, mode):
        result = subprocess.run([self.node,str(self.node_script),mode,str(self.original),str(self.adapted),ORIGIN,NONCE],
                                cwd=ROOT,text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(),'PASS ' + mode + '; JSDOM host only')
        for name,before in self.asset_before.items():
            self.assertEqual((ASSETS/name).read_bytes(),before,'Fixture adaptation must preserve production asset: ' + name)

    def test_actual_java_owner_policy_rejects_malformed_origin_and_nonce(self):
        self.java_check('owner-policy')

    def test_actual_java_replacement_requires_exactly_one_of_each_source_guard(self):
        self.java_check('source-guards')

    def test_original_and_legacy_observer_only_adapter_fail_complete_install(self):
        self.node_check('legacy-refusal')

    def test_actual_adapter_installs_complete_driver_and_preserves_dom(self):
        self.node_check('adapted-emission')

    def test_retained_parent_refresh_preserves_document_and_monotonic_sequence(self):
        self.node_check('retained-popup-parent')

    def test_adapted_complete_driver_rejects_foreign_document_owners(self):
        self.node_check('foreign-owner-refusal')

    def test_original_production_origin_policy_is_preserved(self):
        self.node_check('original-policy')


if __name__ == '__main__':
    unittest.main()
