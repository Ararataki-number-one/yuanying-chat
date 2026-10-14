"""Host regression of the actual attachment Promise and immediate Gecko bridge.

JSDOM observes the browser-side protocol only; this is not Android execution.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "6" * 40
NONCE = "d" * 32
KEY = "__pocketResourceAttachment_" + NONCE + "_host"
URL = "http://127.0.0.1:33037/resource?run=" + NONCE + "&phase=parent&spa=1"


def fixture_expression(name, driver=""):
    """Render the fixture's Java string fragments with its safe hex arguments."""
    fixture = (ROOT / "tests/gecko/ResourcePressureIntegrationActivity.java").read_text()
    line = next(row.strip() for row in fixture.splitlines()
                if row.strip().startswith("String " + name + "="))
    expression = line.split("=", 1)[1].removesuffix(";")
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|JSONObject\.quote\((key|source|run)\)|\bcode\b|\+')
    values = {"key": KEY, "source": SOURCE, "run": NONCE}
    output = []
    offset = 0
    for match in tokens.finditer(expression):
        if expression[offset:match.start()].strip():
            raise AssertionError("Unsupported fixture Java string expression")
        token = match.group()
        if token.startswith('"'):
            output.append(json.loads(token))
        elif match.group(1):
            output.append(json.dumps(values[match.group(1)]))
        elif token == "code":
            output.append(driver)
        offset = match.end()
    if expression[offset:].strip():
        raise AssertionError("Trailing unsupported fixture Java expression")
    return "".join(output)


HOST = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const cfg=JSON.parse(fs.readFileSync(0,'utf8'));
const {JSDOM}=require(cfg.jsdom);
function document(){
  const dom=new JSDOM('<form><textarea id=prompt-textarea></textarea><div id=first data-file-name=first.txt data-upload-state=uploading><button aria-label="Remove file">Remove</button></div><div id=second data-file-name=second.txt data-upload-state=ready><button aria-label="Remove file">Remove</button></div></form>',
    {url:cfg.url,runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,messages=[];let receive=null,id=0;
  Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
  w.visualViewport=null;
  w.browser={runtime:{connectNative:()=>({postMessage:value=>messages.push(value),
    onMessage:{addListener:value=>receive=value}})}};
  w.eval(cfg.bridge);
  function evaluate(code){
    const number=++id;receive({kind:'evaluate',id:number,code});
    const result=messages.findLast(value=>value.kind==='result'&&value.id===number);
    assert.ok(result,'Production bridge must reply to each evaluation');
    return result.result;
  }
  return {dom,w,evaluate};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const first=document();
  assert.equal(first.evaluate(cfg.driver),'null',
    'The production async attachment driver has no immediate JSON result');
  const armed=JSON.parse(first.evaluate(cfg.wrapper));
  assert.equal(armed.state,'armed');assert.equal(armed.sourceCommit,cfg.source);
  assert.equal(armed.runNonce,cfg.nonce);assert.equal(armed.key,cfg.key);
  assert.equal(armed.documentUrl,cfg.url);assert.ok(armed.timeOrigin>0);
  await flush();
  const observed=JSON.parse(first.evaluate(cfg.poll));
  assert.equal(observed.documentUrl,cfg.url);assert.equal(observed.timeOrigin,armed.timeOrigin);
  assert.equal(observed.result.state,'fulfilled');
  assert.equal(observed.result.sourceCommit,cfg.source);
  assert.equal(observed.result.runNonce,cfg.nonce);
  assert.equal(observed.result.key,cfg.key);
  assert.equal(observed.result.documentUrl,cfg.url);
  assert.equal(observed.result.timeOrigin,armed.timeOrigin);
  assert.equal(observed.result.value.ok,true);
  assert.deepEqual(observed.result.value.files.map(value=>[value.name,value.state]),
    [['first.txt','uploading'],['second.txt','ready']]);
  assert.deepEqual(JSON.parse(first.evaluate(cfg.cleanup)),{removed:true});
  assert.equal(Object.hasOwn(first.w,cfg.key),false);
  first.w.document.getElementById('first').dataset.uploadState='ready';
  first.evaluate(cfg.wrapper);await flush();
  const terminal=JSON.parse(first.evaluate(cfg.poll));
  assert.deepEqual(terminal.result.value.files.map(value=>[value.name,value.state]),
    [['first.txt','ready'],['second.txt','ready']]);
  first.evaluate(cfg.cleanup);first.dom.window.close();

  const rejection=document();
  rejection.evaluate(cfg.rejected);await flush();
  const rejected=JSON.parse(rejection.evaluate(cfg.poll));
  assert.equal(rejected.result.state,'rejected');
  assert.match(rejected.result.error,/fixture-negative-control/);
  assert.equal(Object.hasOwn(rejected.result,'value'),false);
  rejection.dom.window.close();
  const empty=document();
  empty.evaluate(cfg.empty);await flush();
  const absent=JSON.parse(empty.evaluate(cfg.poll));
  assert.equal(absent.result.state,'fulfilled');assert.equal(absent.result.value,null);
  empty.dom.window.close();

  const stale=document();
  stale.w[cfg.key]={sourceCommit:'old',runNonce:'old'};
  assert.equal(stale.evaluate(cfg.wrapper),'null','A preexisting result key must fail to arm');
  assert.equal(stale.w[cfg.key].sourceCommit,'old');
  delete stale.w[cfg.key];stale.evaluate(cfg.wrapper);await flush();
  stale.w.history.pushState({},'','/different-document-route');
  const moved=JSON.parse(stale.evaluate(cfg.poll));
  assert.notEqual(moved.documentUrl,armed.documentUrl);
  assert.equal(moved.result.documentUrl,cfg.url,
    'The result keeps its original document identity for native rejection');
  stale.dom.window.close();
  process.stdout.write(JSON.stringify({immediatePromiseRejected:true,actualDriverStates:true,
    fulfilledEnvelopeBound:true,explicitRejection:true,emptyObservationPreserved:true,
    staleKeyRejected:true,changedDocumentExposed:true,actualAndroidExecution:false,
    actualGeckoExecution:false}));
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
"""


class ResourceAttachmentPromiseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        driver = (ROOT / "app/src/main/assets/attachment-driver.js").read_text()
        if not driver.startswith("(async function"):
            raise AssertionError("Exercise the unchanged async production attachment driver")
        driver = driver.replace(
            "location.protocol!=='https:'||location.hostname!=='chatgpt.com'",
            "location.origin!==" + json.dumps("http://127.0.0.1:33037"))
        driver = driver.replace("__ACTION__", json.dumps("attachment-state"))
        driver = driver.replace("__ARG__", json.dumps(
            {"names": ["first.txt", "second.txt"], "url": URL}))
        config = {
            "jsdom": os.environ.get("JSDOM_MODULE", str(
                ROOT / "work/browser-perf-host/node_modules/jsdom")),
            "source": SOURCE, "nonce": NONCE, "key": KEY, "url": URL,
            "driver": driver,
            "bridge": (ROOT / "app/src/main/assets/gecko/content.js").read_text(),
            "wrapper": fixture_expression("wrapper", driver),
            "poll": fixture_expression("pollScript"),
            "cleanup": fixture_expression("cleanupScript"),
            "rejected": fixture_expression(
                "wrapper", "(async()=>{throw new Error('fixture-negative-control')})()"),
            "empty": fixture_expression("wrapper", "(async()=>null)()"),
        }
        result = subprocess.run(["node", "-e", HOST], input=json.dumps(config),
                                text=True, capture_output=True, timeout=20, cwd=ROOT)
        if result.returncode:
            raise AssertionError(result.stderr or result.stdout)
        cls.observed = json.loads(result.stdout)

    def test_async_driver_uses_owned_resolved_values(self):
        self.assertTrue(self.observed["immediatePromiseRejected"])
        self.assertTrue(self.observed["actualDriverStates"])
        self.assertTrue(self.observed["fulfilledEnvelopeBound"])

    def test_rejected_and_empty_promises_do_not_fabricate_observations(self):
        self.assertTrue(self.observed["explicitRejection"])
        self.assertTrue(self.observed["emptyObservationPreserved"])

    def test_stale_result_key_and_document_changes_remain_visible(self):
        self.assertTrue(self.observed["staleKeyRejected"])
        self.assertTrue(self.observed["changedDocumentExposed"])

if __name__ == "__main__":
    unittest.main()
