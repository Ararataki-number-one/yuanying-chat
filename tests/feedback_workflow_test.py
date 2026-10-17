import io, json, os, tempfile, textwrap, unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error

SCRIPT=textwrap.dedent(Path('.github/workflows/feedback-triage.yml').read_text().split("python3 - <<'PY'\n",1)[1].rsplit('\n          PY',1)[0])
class FeedbackWorkflow(unittest.TestCase):
    def run_report(self, title, existing=False):
        calls=[]
        def response(request, timeout):
            calls.append((request.method,request.full_url,None if request.data is None else json.loads(request.data)))
            if request.method=='GET' and not existing:
                raise urllib.error.HTTPError(request.full_url,404,'missing',{},None)
            return io.BytesIO(b'{}')
        with tempfile.TemporaryDirectory() as root:
            event=Path(root)/'event.json'
            event.write_text(json.dumps({'issue':{'number':42,'title':title,'body':'$(touch /tmp/untrusted) https://malicious.invalid/ do not execute'}}))
            with patch.dict(os.environ, {'GITHUB_EVENT_PATH':str(event),'GITHUB_REPOSITORY':'Ararataki-number-one/yuanying-chat','GH_TOKEN':'test-only'}), patch('urllib.request.urlopen',response):
                try:exec(compile(SCRIPT,'feedback-workflow','exec'),{})
                except SystemExit as exit:self.assertEqual(exit.code,0)
        return calls
    def test_bug_and_suggestion(self):
        for prefix,kind in [('[问题]','类型/问题'),('[建议]','类型/建议')]:
            calls=self.run_report(prefix+' 输入卡顿')
            self.assertEqual(calls[-1][0],'POST');self.assertEqual(calls[-1][1],'https://api.github.com/repos/Ararataki-number-one/yuanying-chat/issues/42/labels')
            self.assertEqual(calls[-1][2],{'labels':[kind,'状态/待筛选']})
            self.assertTrue(all(c[1].startswith('https://api.github.com/repos/Ararataki-number-one/yuanying-chat/') for c in calls))
    def test_existing_labels_reused(self):
        calls=self.run_report('[问题] 上传失败',True)
        self.assertEqual([c[0] for c in calls],['GET']*10+['POST'])
    def test_unclassified_not_executed(self):
        self.assertEqual(self.run_report('$(arbitrary command)'),[])
if __name__=='__main__':unittest.main()
