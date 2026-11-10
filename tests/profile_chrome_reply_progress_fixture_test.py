"""Host controls for the actual test-only reply-progress script, not Android acceptance."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReplyProgressFixtureTests(unittest.TestCase):
    def test_owned_paragraph_progress_and_retirement_controls(self):
        source = (ROOT / 'tests/gecko/ChromeCollapseIntegration.java').read_text()
        declaration = re.search(
            r'REPLY_PROGRESS_SCRIPT\s*=\s*((?:"(?:[^"\\]|\\.)*"\s*\+?\s*)+);', source)
        self.assertIsNotNone(declaration)
        script = ''.join(json.loads(value) for value in re.findall(
            r'"(?:[^"\\]|\\.)*"', declaration.group(1)))
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required to exercise the actual fixture script')
        harness = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const program=__PROGRAM__,marker='d'.repeat(32),target='http://127.0.0.1:8765/c/reload-collapse';
let assertions=0;
function check(value,message){assert.ok(value,message);assertions++;}
function fixture(){
  const root={dataset:{reloadDocument:marker,chromeInputEvidence:JSON.stringify({schema:1,realm:'page-main-world',document:marker})}};
  const user={textContent:'already sent fixture question',style:{fontFamily:'sans-serif'}},reply={textContent:'Preserved controlled reply body.',isConnected:true,style:{fontFamily:'sans-serif',fontSize:'18px',width:'auto',lineHeight:'normal'}};
  const controls={stop:{},draft:{value:'unsent controlled browser draft'},sendCount:{textContent:'0'}};
  const timers=new Map(),listeners=new Map();let next=0;
  const document={documentElement:root,cookie:'session=synthetic-reload',querySelector(selector){
    if(selector==='[data-user-message-bubble]')return user;
    if(selector==='[data-message-id="reload-reply"] .markdown p')return reply;
    if(selector==='[data-testid="stop-button"]')return controls.stop;
    throw new Error('Unexpected fixture selector '+selector);
  }};
  const window={addEventListener(name,callback,options){check(name==='pagehide'&&options.once===true,'only page retirement listener');listeners.set(name,callback);}};
  const location={href:target};
  const context=vm.createContext({window,document,location,setInterval(callback,delay){check(delay===30000,'progress interval remains 30s');const id=++next;timers.set(id,callback);return id;},clearInterval(id){timers.delete(id);}});
  const install=vm.runInContext('('+program+')',context);
  return {root,user,reply,controls,document,window,location,timers,listeners,install,
    tick(){for(const callback of [...timers.values()])callback();}};
}
const f=fixture(),original=f.reply.textContent,retained=JSON.stringify([f.controls,f.document.cookie,f.root.dataset,f.location.href]);
check(f.install(marker).installed,'owned fixture installs');
check(JSON.stringify(f.reply.style)===JSON.stringify({fontFamily:'monospace',fontSize:'18px',width:'auto',lineHeight:'normal'})&&f.user.style.fontFamily==='sans-serif','only owned paragraph font family changes before the first snapshot');
check(f.install(marker).installed&&f.timers.size===1,'repeated preparation does not duplicate timer');
check(f.reply.textContent===original,'setup preserves initial paragraph');
for(let step=1;step<=20;step++){
  const prior=f.reply.textContent;f.tick();
  check(f.reply.textContent!==prior,'real paragraph advances throughout ten minutes');
  check(f.reply.textContent.length===original.length,'progress text retains character count');
  check(JSON.stringify(f.reply.style)===JSON.stringify({fontFamily:'monospace',fontSize:'18px',width:'auto',lineHeight:'normal'}),'progress preserves prepared font size width and line height');
  check(JSON.stringify([f.controls,f.document.cookie,f.root.dataset,f.location.href])===retained,'draft login input telemetry controls and route remain unchanged');
}
for(const [name,change] of [
  ['foreign URL',x=>x.location.href='https://chatgpt.com/c/real'],
  ['different document',x=>x.root.dataset.reloadDocument='e'.repeat(32)],
  ['wrong telemetry owner',x=>x.root.dataset.chromeInputEvidence=JSON.stringify({schema:1,realm:'page-main-world',document:'e'.repeat(32)})],
  ['wrong telemetry realm',x=>x.root.dataset.chromeInputEvidence=JSON.stringify({schema:1,realm:'foreign',document:marker})],
  ['malformed telemetry',x=>x.root.dataset.chromeInputEvidence='broken'],
  ['different question',x=>x.user.textContent='another question'],
  ['different reply',x=>x.reply.textContent='another answer'],
  ['completed reply',x=>x.controls.stop=null],
]){
  const x=fixture();change(x);const before=x.reply.textContent;
  check(x.install(marker).installed===false&&x.timers.size===0&&x.reply.textContent===before,name+' cannot start progress');
  check(x.reply.style.fontFamily==='sans-serif',name+' cannot change paragraph styling');
}
{const x=fixture();check(x.install('invalid').installed===false&&x.timers.size===0,'invalid document marker rejected');}
for(const [name,change] of [
  ['navigation',x=>x.location.href='https://chatgpt.com/c/other'],
  ['document replacement',x=>x.document.documentElement={dataset:{reloadDocument:marker}}],
  ['document marker change',x=>x.root.dataset.reloadDocument='e'.repeat(32)],
  ['reply detached',x=>x.reply.isConnected=false],
  ['independent reply edit',x=>x.reply.textContent='actual other progress'],
  ['reply completed',x=>x.controls.stop=null],
]){
  const x=fixture();check(x.install(marker).installed,'retirement fixture installs');change(x);const before=x.reply.textContent;x.tick();
  check(x.timers.size===0&&x.reply.textContent===before&&x.window.__chromeCollapseReplyProgress.active===false,name+' retires without modifying the new state');
}
{const x=fixture();x.install(marker);x.listeners.get('pagehide')();check(x.timers.size===0,'pagehide clears timer');check(x.install(marker).installed===false,'retired owner is not silently restarted');}
console.log(JSON.stringify({scope:'Actual test-only script in Node VM; not Android acceptance',assertions}));
'''.replace('__PROGRAM__', json.dumps(script))
        result = subprocess.run([node, '-'], input=harness, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertGreaterEqual(receipt['assertions'], 100)


if __name__ == '__main__':
    unittest.main()
