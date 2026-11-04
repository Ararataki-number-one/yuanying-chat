#!/usr/bin/env python3
"""Execute exact recovery/search policies with explicit in-memory DB/profile adapters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'

def member(source,signature):
    start=source.index(signature)
    opening=source.index('{',start)
    depth=1
    end=opening+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--java-home',type=Path,required=True)
    parser.add_argument('--json-jar',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-continuity-host.json')
    args=parser.parse_args()
    sources=[PROD/name for name in ['LocalContinuityPolicy.java','LocalContinuityStore.java','LocalMessageIndex.java','J.java']]+[HERE/'ContinuityHost.java',HERE/'PerformanceCases.java']+list((HERE/'stubs').rglob('*.java'))
    copy_member=member((PROD/'LocalHistoryUi.java').read_text(),'void copyConversation()')
    with tempfile.TemporaryDirectory(prefix='local-continuity-') as raw:
        classes=Path(raw)/'classes'
        wrapper=Path(raw)/'ReaderCopyHost.java'
        wrapper.write_text('''package local.pocketchat;
import java.util.*;
final class ReaderCopyHost {
 final MainActivity a=new MainActivity();final ChatSession owner=new ChatSession();final HostFeedback feedback=new HostFeedback();LocalContinuityStore.Conversation conversation;
 /* PRODUCTION MEMBER */
 static void verify(){
  ReaderCopyHost fixture=new ReaderCopyHost();
  fixture.conversation=new LocalContinuityStore.Conversation("https://chatgpt.com/c/1","title",1,Arrays.asList(new LocalContinuityPolicy.Message("assistant","x".repeat(180001),1)),"");
  LocalContinuityUi.copied=0;fixture.copyConversation();
  ContinuityHost.check("Actual reader copy action rejects oversized source before clipboard",LocalContinuityUi.copied==0&&fixture.feedback.text.contains("较长"));
  fixture.conversation=new LocalContinuityStore.Conversation("https://chatgpt.com/c/1","title",1,Arrays.asList(new LocalContinuityPolicy.Message("assistant","full answer",1)),"");
  fixture.copyConversation();ContinuityHost.check("Actual reader copy action preserves full valid transcript",LocalContinuityUi.copied==1&&LocalContinuityUi.text.equals("title\\n\\nChatGPT\\nfull answer"));
  LocalContinuityUi.valid=false;fixture.copyConversation();ContinuityHost.check("Actual reader copy action rejects stale owner",LocalContinuityUi.copied==1);
 }
}
class ChatSession{}
class HostFeedback{String text="";void setText(String value){text=value;}}
class LocalContinuityUi {static boolean valid=true;static int copied;static String text;static boolean current(MainActivity a,ChatSession owner){return valid;}static void copy(MainActivity a,ChatSession owner,String label,String value,HostFeedback feedback){copied++;text=value;}}
'''.replace('/* PRODUCTION MEMBER */',copy_member))
        compiled=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(classes),*map(str,sources),str(wrapper)],text=True,capture_output=True,timeout=40)
        assert compiled.returncode==0,compiled.stdout+compiled.stderr
        executed=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(args.json_jar),'local.pocketchat.ContinuityHost'],text=True,capture_output=True,timeout=40)
        assert executed.returncode==0,executed.stdout+executed.stderr
        result=json.loads(executed.stdout)
    result.update(scope='Exact production LocalContinuityPolicy, LocalContinuityStore and Reader.copyConversation method; deterministic profile preferences, Cursor and clipboard-boundary adapters, no Android or SQLite runtime.',readerCopyMemberSha256=hashlib.sha256(copy_member.encode()).hexdigest(),sourceSha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ['status','passed','actualAndroidExecution','actualSqliteExecution']}))

if __name__=='__main__':main()
