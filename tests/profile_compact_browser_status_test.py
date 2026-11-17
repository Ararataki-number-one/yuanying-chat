"""Execute the current browser status and compact-fixture checks on host doubles.

These positive/negative controls are not Android layout or execution evidence.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('compact_status_java_members',
    ROOT / 'tests/runtime-origin-adapter-host/run.py')
members = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(members)

HOST = r'''
import android.text.TextUtils;

public final class CompactBrowserStatusHost {
  static class View {static final int VISIBLE=0,GONE=8;}
  static class DesignUi {static final int RED=1,MUTED=2;}
  static class ChatService {static boolean running;}
  static class Preferences {boolean pending;boolean contains(String key){return pending&&key.equals("pending");}}
  static class Session {
    Object pending;final Preferences prefs=new Preferences();String activeDeliveryId="",status="",pageError="",networkIssue="";
    boolean submitting,websiteConnectionIssue,offline,networkReady,connecting;int resourceFilePreparations;
  }
  static class AppHub {static final int CHAT=0;int page=CHAT;void feedback(String value,boolean error){throw new AssertionError("Chat fixture left its page");}}
  static class StatusView {
    int visibility=View.GONE;boolean clickable;String text="",fault="";Runnable onText;
    int getVisibility(){return visibility;}boolean isClickable(){return clickable;}String getText(){return text;}
    void setText(String value){text=fault.equals("wrong-error-text")?"different error":value;if(onText!=null)onText.run();}
    void setTextColor(int color){}void setContentDescription(String value){}
    void setClickable(boolean value){clickable=!fault.equals("unclickable-error")&&value;}
    void setVisibility(int value){visibility=fault.equals("visible-idle")?View.VISIBLE:fault.equals("hidden-error")?View.GONE:value;}
  }
  static class Fixture {
    String lastUiStatus="";final Session session=new Session();final StatusView status=new StatusView();final AppHub hub=new AppHub();
    /* ACTUAL_STATUS */
    /* ACTUAL_BROWSER_STATUS_REGRESSION */
    /* ACTUAL_NO_NATIVE_REPLY_TASK */
  }
  static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
  public static void main(String[] args){
    String mode=args[0];Fixture fixture=new Fixture();String expected="";
    switch(mode){
      case "normal":break;
      case "pending":fixture.session.pending=new Object();expected="native reply task";break;
      case "stored-pending":fixture.session.prefs.pending=true;expected="native reply task";break;
      case "delivery":fixture.session.activeDeliveryId="old-result";expected="native reply task";break;
      case "submitting":fixture.session.submitting=true;expected="native reply task";break;
      case "reply-service":ChatService.running=true;expected="native reply task";break;
      case "task-created-during-status":fixture.status.onText=()->fixture.session.pending=new Object();expected="native reply task";break;
      case "visible-idle":fixture.status.fault=mode;expected="Normal browser connection";break;
      case "hidden-error":case "unclickable-error":case "wrong-error-text":fixture.status.fault=mode;expected="Real browser errors";break;
      case "retired-text-has-no-special-case":
        fixture.status("对话已改变，请检查上次发送；不会自动重发");
        require(fixture.status.getVisibility()==View.VISIBLE&&fixture.status.isClickable(),"Retired result text gained a production special case");
        fixture.assertNoNativeReplyTask();break;
      default:throw new AssertionError("Unknown control "+mode);
    }
    boolean rejected=false;
    try{fixture.browserStatusRegression();}
    catch(AssertionError error){
      if(expected.isEmpty()||!String.valueOf(error.getMessage()).contains(expected))throw error;
      rejected=true;
    }
    require(rejected==!expected.isEmpty(),"Fault escaped the actual compact fixture: "+mode);
    if(!rejected){require(fixture.status.getVisibility()==View.GONE&&!fixture.status.isClickable(),"Final browser status remained noisy");fixture.assertNoNativeReplyTask();}
    System.out.println("{\"mode\":\""+mode+"\",\"passed\":true}");
  }
}
'''


class CompactBrowserStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not cls.java:
            raise RuntimeError('JDK 17+ is required for the browser status controls')
        cls.temp = tempfile.TemporaryDirectory(prefix='compact-browser-status-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        production = (ROOT / 'app/src/main/java/local/pocketchat/MainActivity.java').read_text()
        fixture = (ROOT / 'tests/gecko/CompactChromeIntegrationActivity.java').read_text()
        selected = HOST.replace('/* ACTUAL_STATUS */', members.member(production, 'void status(String value)'))
        selected = selected.replace('/* ACTUAL_BROWSER_STATUS_REGRESSION */', members.member(fixture, 'void browserStatusRegression()'))
        selected = selected.replace('/* ACTUAL_NO_NATIVE_REPLY_TASK */', members.member(fixture, 'void assertNoNativeReplyTask()'))
        host = cls.directory / 'CompactBrowserStatusHost.java'; host.write_text(selected)
        text_utils = cls.directory / 'android/text/TextUtils.java'; text_utils.parent.mkdir(parents=True)
        text_utils.write_text('package android.text; public final class TextUtils {public static boolean equals(CharSequence a,CharSequence b){return a==null?b==null:a.toString().contentEquals(b==null?"":b);}}')
        compiled = subprocess.run([cls.java, '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                                   '-encoding', 'UTF-8', '-d', str(cls.directory), str(host), str(text_utils)],
                                  text=True, capture_output=True, timeout=45)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def exercise(self, mode):
        completed = subprocess.run([self.java, '-cp', str(self.directory), 'CompactBrowserStatusHost', mode],
                                   text=True, capture_output=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {'mode': mode, 'passed': True})

    def test_actual_browser_status_is_quiet_actionable_then_cleared(self):
        self.exercise('normal')

    def test_each_native_result_state_is_rejected(self):
        for mode in ('pending', 'stored-pending', 'delivery', 'submitting', 'reply-service'):
            with self.subTest(mode=mode): self.exercise(mode)

    def test_status_cannot_create_a_native_result_task(self):
        self.exercise('task-created-during-status')

    def test_visible_idle_hidden_unclickable_or_wrong_error_is_rejected(self):
        for mode in ('visible-idle', 'hidden-error', 'unclickable-error', 'wrong-error-text'):
            with self.subTest(mode=mode): self.exercise(mode)

    def test_production_does_not_restore_retired_result_text_filtering(self):
        self.exercise('retired-text-has-no-special-case')


if __name__ == '__main__': unittest.main()
