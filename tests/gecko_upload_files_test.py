"""Actual production SAF-to-file preparation on host streams, not Android acceptance."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

STUBS = {
    'android/content/Context.java': '''package android.content; import java.io.File;
      public abstract class Context { public abstract File getCacheDir(); public abstract ContentResolver getContentResolver(); }''',
    'android/content/ContentResolver.java': '''package android.content; import java.io.*; import android.net.Uri; import android.database.Cursor;
      public abstract class ContentResolver { public abstract Cursor query(Uri u,String[] p,String s,String[] a,String sort); public abstract String getType(Uri u); public abstract InputStream openInputStream(Uri u)throws IOException; }''',
    'android/database/Cursor.java': '''package android.database; public interface Cursor extends AutoCloseable {boolean moveToFirst();int getColumnIndex(String name);boolean isNull(int i);String getString(int i);void close();}''',
    'android/provider/OpenableColumns.java': '''package android.provider; public class OpenableColumns {public static final String DISPLAY_NAME="_display_name";}''',
    'android/net/Uri.java': '''package android.net; import java.io.File; public class Uri {private final java.net.URI value; private Uri(java.net.URI v){value=v;} public static Uri parse(String v){return new Uri(java.net.URI.create(v));} public static Uri fromFile(File f){return new Uri(f.toURI());} public String getScheme(){return value.getScheme();}public String getPath(){return value.getPath();}public String toString(){return value.toString();}}''',
    'android/webkit/MimeTypeMap.java': '''package android.webkit; public final class MimeTypeMap {public static MimeTypeMap getSingleton(){return new MimeTypeMap();}public String getExtensionFromMimeType(String m){return "image/png".equals(m)?"png":"image/jpeg".equals(m)?"jpg":"text/plain".equals(m)?"txt":null;}public String getMimeTypeFromExtension(String e){return "png".equals(e)?"image/png":"jpg".equals(e)?"image/jpeg":"txt".equals(e)?"text/plain":null;}}''',
    'local/pocketchat/GeckoUploadFilesHostTest.java': r'''package local.pocketchat;
import android.content.*;import android.database.Cursor;import android.net.Uri;import java.io.*;import java.nio.file.*;import java.util.*;
public final class GeckoUploadFilesHostTest {
  static int checks,opened,closed;static File root;static Map<String,Doc> docs=new HashMap<>();
  static final class Doc {String name,mime,data;boolean badQuery,badMime,brokenStream,nullStream;Doc(String n,String m,String d){name=n;mime=m;data=d;}}
  static final ContentResolver resolver=new ContentResolver(){
    public Cursor query(Uri uri,String[] p,String s,String[] a,String order){Doc doc=docs.get(uri.toString());if(doc.badQuery)throw new SecurityException("metadata not granted");return new Cursor(){public boolean moveToFirst(){return true;}public int getColumnIndex(String name){return 1;}public boolean isNull(int i){return i!=1||doc.name==null;}public String getString(int i){return i==1?doc.name:"ignored metadata column";}public void close(){}};}
    public String getType(Uri uri){Doc doc=docs.get(uri.toString());if(doc.badMime)throw new IllegalArgumentException("MIME unavailable");return doc.mime;}
    public InputStream openInputStream(Uri uri)throws IOException {if("file".equals(uri.getScheme()))return new FileInputStream(new File(uri.getPath()));Doc doc=docs.get(uri.toString());if(doc.nullStream)return null;opened++;return new ByteArrayInputStream(doc.data.getBytes(java.nio.charset.StandardCharsets.UTF_8)){public synchronized int read(byte[] b,int o,int n){if(doc.brokenStream)throw new IllegalStateException("cloud document unavailable");return super.read(b,o,n);}public void close()throws IOException{closed++;super.close();}};}
  };
  static final Context context=new Context(){public File getCacheDir(){return root;}public ContentResolver getContentResolver(){return resolver;}};
  static Uri doc(String id,Doc doc){Uri uri=Uri.parse("content://external.provider/"+id);docs.put(uri.toString(),doc);return uri;}
  static void check(String label,boolean ok){if(!ok)throw new AssertionError(label);checks++;}
  static String name(GeckoUploadFiles.Selection selected,int i){return new File(selected.files[i].getPath()).getName();}
  static String body(GeckoUploadFiles.Selection selected,int i)throws IOException{return Files.readString(new File(selected.files[i].getPath()).toPath());}
  static void fail(String label,Uri[] uris)throws Exception{Set<String> before=directories();try{GeckoUploadFiles.prepare(context,uris);throw new AssertionError(label);}catch(IOException expected){check(label,!expected.getMessage().isEmpty()&&directories().equals(before));}}
  static Set<String> directories(){File[] all=new File(root,"gecko-uploads").listFiles();Set<String> names=new HashSet<>();if(all!=null)for(File f:all)names.add(f.getName());return names;}
  public static void main(String[] args)throws Exception {root=Path.of(args[0]).toFile();
    GeckoUploadFiles.Selection selection=GeckoUploadFiles.prepare(context,new Uri[]{doc("normal",new Doc("sample.txt","text/plain","original-text"))});check("readable SAF stream and filename",name(selection,0).equals("sample.txt")&&body(selection,0).equals("original-text"));selection.delete();
    Doc badName=new Doc("unused","image/png","image-bytes");badName.badQuery=true;selection=GeckoUploadFiles.prepare(context,new Uri[]{doc("name-denied",badName)});check("missing metadata does not deny granted stream",name(selection,0).equals("附件.png")&&body(selection,0).equals("image-bytes"));selection.delete();
    Doc badMime=new Doc("scan.png","image/png","retained-bytes");badMime.badMime=true;selection=GeckoUploadFiles.prepare(context,new Uri[]{doc("type-denied",badMime)});check("MIME lookup failure preserves filename and bytes",name(selection,0).equals("scan.png")&&body(selection,0).equals("retained-bytes"));selection.delete();
    selection=GeckoUploadFiles.prepare(context,new Uri[]{doc("first",new Doc("image.jpg","image/jpeg","first")),doc("second",new Doc("image.jpg","image/jpeg","second")),doc("third",new Doc("image (2).jpg","image/jpeg","third"))});check("duplicate photo names preserve every selection",name(selection,0).equals("image.jpg")&&name(selection,1).equals("image (2).jpg")&&name(selection,2).equals("image (2) (2).jpg")&&body(selection,0).equals("first")&&body(selection,1).equals("second")&&body(selection,2).equals("third"));selection.delete();
    selection=GeckoUploadFiles.prepare(context,new Uri[]{doc("bare",new Doc("photo-123","image/png","png")),doc("empty",new Doc(null,"text/plain","text"))});check("photo MIME receives extension",name(selection,0).equals("photo-123.png"));check("missing name retains readable text document",name(selection,1).equals("附件.txt")&&body(selection,1).equals("text"));selection.delete();
    selection=GeckoUploadFiles.prepare(context,new Uri[]{doc("unsafe",new Doc("../../ bad\nname.txt","text/plain","safe"))});check("provider names cannot traverse private directory",new File(selection.files[0].getPath()).getCanonicalFile().getParentFile().equals(selection.directory.getCanonicalFile())&&name(selection,0).indexOf('/')<0&&name(selection,0).indexOf('\n')<0);selection.delete();
    File original=new File(root,"local.txt");Files.writeString(original.toPath(),"local-bytes");selection=GeckoUploadFiles.prepare(context,new Uri[]{Uri.fromFile(original)});check("existing local input remains supported",name(selection,0).equals("local.txt")&&body(selection,0).equals("local-bytes"));selection.delete();
    Doc broken=new Doc("broken.txt","text/plain","never");broken.brokenStream=true;fail("failed stream removes partially prepared selection",new Uri[]{doc("good-before-error",new Doc("good.txt","text/plain","good")),doc("broken",broken)});
    Doc absent=new Doc("missing.txt","text/plain","");absent.nullStream=true;fail("null provider stream fails visibly and cleans up",new Uri[]{doc("null",absent)});
    fail("remote URLs cannot become upload paths",new Uri[]{Uri.parse("https://example.org/upload")});fail("null selection is rejected cleanly",null);fail("empty selection is rejected cleanly",new Uri[0]);fail("null selected URI is rejected cleanly",new Uri[]{null});
    Thread.currentThread().interrupt();try{fail("interrupted stream preparation leaves no private copy",new Uri[]{doc("interrupted",new Doc("stop.txt","text/plain","stop"))});}finally{Thread.interrupted();}
    check("all selected document streams are closed",opened==closed);check("completed private selections are removable",directories().isEmpty());
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false,\"realChatGptUploadAcceptance\":false}");
  }
}''',
}


class UploadPreparationTest(unittest.TestCase):
    def test_production_preparation_on_real_host_streams(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertIsNotNone(java, 'JDK 17+ is required')
        with tempfile.TemporaryDirectory(prefix='gecko-upload-host-') as folder:
            temp = Path(folder)
            files = []
            for relative, source in STUBS.items():
                path = temp / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
                files.append(path)
            classes = temp / 'classes'
            classes.mkdir()
            compile_result = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-d', str(classes), *map(str, files), str(ROOT / 'app/src/main/java/local/pocketchat/GeckoUploadFiles.java')], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            cache = temp / 'private-cache'
            cache.mkdir()
            run = subprocess.run([java, '-cp', str(classes), 'local.pocketchat.GeckoUploadFilesHostTest', str(cache)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('"status":"passed"', run.stdout)
            print(run.stdout.strip())


if __name__ == '__main__':
    unittest.main()
