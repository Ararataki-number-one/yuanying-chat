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
url_name=production_member(source,'static String urlFileName(')
format_source=ROOT/'app/src/main/java/local/pocketchat/DownloadFileFormat.java'
host=r'''package local.pocketchat;
import java.net.URI;
import java.net.URLDecoder;
import java.io.UnsupportedEncodingException;
import java.util.Arrays;
class MetadataHost {
 String name="old.bin",mime="application/octet-stream",sourceId="",imageLabel="";
 static String guessed="server.pdf";
 static class URLUtil {static String guessFileName(String url,String disposition,String mime){return guessed;}}
 static String safeName(String name){return name;}
 static String type(String name,String fallback){return DownloadFileFormat.mimeForName(name,fallback,ext->ext.equals("jpg")?"image/jpeg":"");}
 static String imageExtension(String mime){return "image/jpeg".equals(mime)?"jpg":"png";}
 __METHOD__
 __URL_NAME__
 static void check(boolean pass,String name){if(!pass)throw new AssertionError(name);}
 public static void main(String[] ignored){
  MetadataHost h=new MetadataHost();
  h.responseMetadata("https://files.example/signed","attachment; filename=server.pdf","APPLICATION/PDF; charset=binary");
  check(h.name.equals("server.pdf")&&h.mime.equals("application/pdf"),"final PDF type and disposition replace initial binary guess");
  h.sourceId="message";h.name="report.docx";
  h.responseMetadata("https://files.example/signed","","application/vnd.openxmlformats-officedocument.wordprocessingml.document");
  check(h.name.equals("report.docx")&&h.mime.endsWith("wordprocessingml.document"),"known message filename survives absent disposition");
  h.name="文件";h.mime="application/octet-stream";guessed="preview.pdf";
  h.responseMetadata("blob:https://chatgpt.com/id","","application/octet-stream");
  h.responseMetadata("blob:https://chatgpt.com/id","","application/pdf");
  check(h.name.equals("preview.pdf")&&h.mime.equals("application/pdf"),"opaque blob can recover its PDF extension once content is recognized");
  h.name="report.docx";h.responseMetadata("https://files.example/file","","application/octet-stream");
  check(h.mime.endsWith("wordprocessingml.document"),"generic stream does not erase known document type");
  h.responseMetadata("https://files.example/file","","invalid\r\nheader");
  check(h.mime.endsWith("wordprocessingml.document"),"malformed MIME cannot become saved MIME");
  h.name="图片 2";h.imageLabel="图片 2";h.responseMetadata("https://files.example/image","","image/jpeg");
  check(h.name.equals("图片 2.jpg")&&h.mime.equals("image/jpeg"),"image labels remain intact");
  h.responseMetadata("https://files.example/image","","image/jpeg");
  check(h.name.equals("图片 2.jpg"),"resolving the same image twice never appends a second extension");
  h.responseMetadata("https://files.example/image","attachment;filename=original.jpg","image/png");
  check(h.name.equals("original.jpg")&&h.mime.equals("image/jpeg"),"an original image filename wins over label and inconsistent MIME");
  h.imageLabel="";h.sourceId="";h.name="old.bin";guessed="new.docx";
  h.responseMetadata("https://files.example/signed","attachment; filename=new.docx",null);
  check(h.name.equals("new.docx")&&h.mime.endsWith("wordprocessingml.document"),"disposition with no MIME resolves via filename");
  h.name="文件";h.mime="application/octet-stream";guessed="download.bin";
  h.responseMetadata("https://files.example/download.bin","","application/octet-stream");
  check(h.name.equals("download.bin"),"generic native response still obtains its initial filename");
  h.name="文件";h.responseMetadata("https://files.example/%E6%8A%A5%E5%91%8A.xlsx?download=true","","application/zip");
  check(h.name.equals("报告.xlsx")&&h.mime.endsWith("spreadsheetml.sheet"),"URL filename and MIME retain the advertised document suffix");
  h.name="文件";guessed="download.pdf";
  h.responseMetadata("https://files.example/download.php","","application/pdf");
  check(h.name.equals("download.pdf")&&h.mime.equals("application/pdf"),"server script suffix is not used as the downloaded file format");
  System.out.println("12 metadata cases passed");
 }
}'''.replace('__METHOD__',method).replace('__URL_NAME__',url_name)
with tempfile.TemporaryDirectory() as folder:
 path=pathlib.Path(folder);(path/'MetadataHost.java').write_text(host)
 subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-d',str(path),str(path/'MetadataHost.java'),str(format_source)],check=True)
 completed=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(path),'local.pocketchat.MetadataHost'],check=True,text=True,capture_output=True)
report=dict(status='passed',cases=12,methodSha256=hashlib.sha256(method.encode()).hexdigest(),scope=__doc__,actualAndroidExecution=False,actualDownloadBytesVerified=False,output=completed.stdout.strip())
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
