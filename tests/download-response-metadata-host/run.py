#!/usr/bin/env python3
"""Execute the current responseMetadata method with explicit Android naming adapters.
This tests metadata selection only, not Android parsing, wire bytes, or real sites.
"""
import argparse, hashlib, json, pathlib, subprocess, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/review-host'))
from run_deferred_browser_host import production_member
p=argparse.ArgumentParser();p.add_argument('--java-home',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
source=(ROOT/'app/src/main/java/local/pocketchat/FileDownloads.java').read_text()
method=production_member(source,'void responseMetadata(')
host=r'''import java.util.Locale;
class MetadataHost {
 String name="old.bin",mime="application/octet-stream",sourceId="",imageLabel="";
 static String guessed="server.pdf";
 static class URLUtil {static String guessFileName(String url,String disposition,String mime){return guessed;}}
 static String safeName(String name){return name;}
 static String type(String name,String fallback){return name.endsWith(".docx")?"application/vnd.openxmlformats-officedocument.wordprocessingml.document":fallback;}
 static String imageExtension(String mime){return "image/jpeg".equals(mime)?"jpg":"png";}
 __METHOD__
 static void check(boolean pass,String name){if(!pass)throw new AssertionError(name);}
 public static void main(String[] ignored){
  MetadataHost h=new MetadataHost();
  h.responseMetadata("https://files.example/signed","attachment; filename=server.pdf","APPLICATION/PDF; charset=binary");
  check(h.name.equals("server.pdf")&&h.mime.equals("application/pdf"),"final PDF type and disposition replace initial binary guess");
  h.sourceId="message";h.name="report.docx";
  h.responseMetadata("https://files.example/signed","","application/vnd.openxmlformats-officedocument.wordprocessingml.document");
  check(h.name.equals("report.docx")&&h.mime.endsWith("wordprocessingml.document"),"known message filename survives absent disposition");
  h.responseMetadata("blob:https://chatgpt.com/id","","application/pdf");
  check(h.mime.equals("application/pdf"),"blob PDF updates MIME as images already did");
  h.name="report.docx";h.responseMetadata("https://files.example/file","","application/octet-stream");
  check(h.mime.endsWith("wordprocessingml.document"),"generic stream does not erase known document type");
  h.responseMetadata("https://files.example/file","","invalid\r\nheader");
  check(h.mime.endsWith("wordprocessingml.document"),"malformed MIME cannot become saved MIME");
  h.imageLabel="图片 2";h.responseMetadata("https://files.example/image","","image/jpeg");
  check(h.name.equals("图片 2.jpg")&&h.mime.equals("image/jpeg"),"image labels remain intact");
  h.imageLabel="";h.sourceId="";h.name="old.bin";guessed="new.docx";
  h.responseMetadata("https://files.example/signed","attachment; filename=new.docx",null);
  check(h.name.equals("new.docx")&&h.mime.endsWith("wordprocessingml.document"),"disposition with no MIME resolves via filename");
  h.name="文件";h.mime="application/octet-stream";guessed="download.bin";
  h.responseMetadata("https://files.example/download.bin","","application/octet-stream");
  check(h.name.equals("download.bin"),"generic native response still obtains its initial filename");
  System.out.println("8 metadata cases passed");
 }
}'''.replace('__METHOD__',method)
with tempfile.TemporaryDirectory() as folder:
 path=pathlib.Path(folder);(path/'MetadataHost.java').write_text(host)
 subprocess.run([str(a.java_home/'bin/javac'),str(path/'MetadataHost.java')],check=True)
 completed=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(path),'MetadataHost'],check=True,text=True,capture_output=True)
report=dict(status='passed',cases=8,methodSha256=hashlib.sha256(method.encode()).hexdigest(),scope=__doc__,actualAndroidExecution=False,actualDownloadBytesVerified=False,output=completed.stdout.strip())
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
