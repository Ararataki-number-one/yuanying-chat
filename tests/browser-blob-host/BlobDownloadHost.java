package local.pocketchat;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;
import java.util.regex.*;
import org.json.*;

public final class BlobDownloadHost {
  static final String PAGE="https://example.com/editor",BLOB="blob:https://example.com/export-123",KEY="__testBlob";
  static int checks;
  static void check(String label,boolean value){if(!value)throw new AssertionError(label);checks++;}
  static class Page implements BrowserBlobDownload.Page {
    final byte[] bytes;boolean current=true,returnNull,invalidBase64,wrongChunk,stall;Object size;
    String mime="application/pdf",after="";BrowserBlobDownload task;int chunks,discards,calls;long start,end;
    Page(byte[] bytes){this.bytes=bytes;size=bytes.length;}
    public boolean current(){return current;}
    public void evaluate(String script,Consumer<String> done){
      calls++;if(stall)return;if(returnNull){done.accept(null);return;}
      if(script.contains("fetch(")){done.accept("{\"started\":true}");change("prepare");return;}
      if(script.contains("size:f.size")){done.accept(J.obj("ready",true,"size",size,"mime",mime).toString());change("metadata");return;}
      Matcher slice=Pattern.compile("\\.blob\\.slice\\((\\d+),(\\d+)\\)").matcher(script);
      if(slice.find()){start=Long.parseLong(slice.group(1));end=Long.parseLong(slice.group(2));chunks++;done.accept("{\"started\":true}");change("slice");return;}
      if(script.contains("chunk:value")){
        byte[] piece=Arrays.copyOfRange(bytes,(int)start,(int)end-(wrongChunk?1:0));String encoded=invalidBase64?"not_base64!":Base64.getEncoder().encodeToString(piece);
        done.accept(J.obj("ready",true,"chunk",encoded).toString());change("chunk");return;
      }
      throw new AssertionError("Unexpected production script");
    }
    void change(String stage){if(after.equals(stage))current=false;if(after.equals("cancel-"+stage))task.cancel();}
    public void discard(String script){check("cleanup deletes only the task key",script.contains("delete window[")&&script.contains("f.document===document"));discards++;}
  }
  interface Attempt {void run()throws Exception;}
  static void rejects(String label,Attempt run)throws Exception{try{run.run();throw new AssertionError(label);}catch(IOException expected){checks++;}}
  static BrowserBlobDownload.Result fetch(Page page,Path directory)throws Exception {
    page.task=new BrowserBlobDownload();return page.task.fetch(PAGE,BLOB,directory.toFile(),page,Runnable::run,(received,total)->check("bounded progress",received>=0&&received<=total));
  }
  static void cleanDirectory(Path path)throws Exception{try(java.util.stream.Stream<Path> files=Files.list(path)){check("partial file cleanup",files.findAny().isEmpty());}}
  static byte[] bytes(){byte[] result=new byte[BrowserBlobDownload.CHUNK_BYTES*2+37];for(int i=0;i<result.length;i++)result[i]=(byte)(i*71);return result;}
  public static void main(String[] args)throws Exception {
    Path directory=Files.createTempDirectory("blob-download-host-");byte[] data=bytes();
    try{
      Page normal=new Page(data);BrowserBlobDownload.Result saved=fetch(normal,directory);
      check("all bytes preserved",Arrays.equals(data,Files.readAllBytes(saved.file.toPath())));
      check("whole length and MIME preserved",saved.bytes==data.length&&saved.mime.equals(normal.mime));
      check("bounded chunks",normal.chunks==3);
      check("script state released",normal.discards==1);Files.delete(saved.file.toPath());cleanDirectory(directory);
      Page empty=new Page(new byte[0]);empty.mime="application/octet-stream";saved=fetch(empty,directory);
      check("empty non-document transfer supported",saved.bytes==0&&saved.file.length()==0&&empty.chunks==0);Files.delete(saved.file.toPath());
      for(Object size:Arrays.asList(-1,BrowserDownloadTransfer.MAX_BYTES+1,4.5,"1024")){
        Page bad=new Page(data);bad.size=size;rejects("invalid advertised blob size",()->fetch(bad,directory));cleanDirectory(directory);
      }
      for(String stage:Arrays.asList("prepare","metadata","slice","chunk","cancel-prepare","cancel-metadata","cancel-slice","cancel-chunk")){
        Page bad=new Page(data);bad.after=stage;rejects("lost document/route or cancel at "+stage,()->fetch(bad,directory));check("released local blob after failure",bad.discards==1);cleanDirectory(directory);
      }
      Page malformed=new Page(data);malformed.invalidBase64=true;rejects("reject malformed byte encoding",()->fetch(malformed,directory));cleanDirectory(directory);
      Page shortChunk=new Page(data);shortChunk.wrongChunk=true;rejects("reject incomplete chunk",()->fetch(shortChunk,directory));cleanDirectory(directory);
      Page gone=new Page(data);gone.returnNull=true;rejects("retired WebView response",()->fetch(gone,directory));cleanDirectory(directory);
      Page unavailable=new Page(data);unavailable.current=false;rejects("no source authority",()->fetch(unavailable,directory));check("no read after source lost",unavailable.calls==0);
      BrowserBlobDownload task=new BrowserBlobDownload();Page foreign=new Page(data);
      rejects("cross-origin Blob cannot borrow current document",()->task.fetch(PAGE,"blob:https://other.example.com/export",directory.toFile(),foreign,Runnable::run,(n,total)->{}));check("cross-origin rejects before evaluation",foreign.calls==0);
      BrowserBlobDownload blocked=new BrowserBlobDownload();Page stalled=new Page(data);stalled.stall=true;
      Thread cancel=new Thread(()->{try{Thread.sleep(150);}catch(InterruptedException ignored){}blocked.cancel();});cancel.start();
      long began=System.nanoTime();rejects("cancel interrupted pending WebView callback",()->blocked.fetch(PAGE,BLOB,directory.toFile(),stalled,Runnable::run,(n,total)->{}));cancel.join();
      check("cancel does not wait for full callback deadline",System.nanoTime()-began<2_000_000_000L);cleanDirectory(directory);
      if(args.length>0){
        JSONArray chunks=new JSONArray();for(long offset=0;offset<data.length;offset+=BrowserBlobDownload.CHUNK_BYTES){long end=Math.min(data.length,offset+BrowserBlobDownload.CHUNK_BYTES);chunks.put(BrowserBlobDownload.chunkScript(KEY,PAGE,offset,end));}
        JSONObject scripts=J.obj("source",PAGE,"target",BLOB,"key",KEY,"bytes",Base64.getEncoder().encodeToString(data),"prepare",BrowserBlobDownload.prepareScript(KEY,PAGE,BLOB),"metadata","(()=>{"+BrowserBlobDownload.guard(KEY,PAGE)+"return {ready:f.ready===true,error:f.error===true,size:f.size,mime:f.mime};})()","chunkRead","(()=>{"+BrowserBlobDownload.guard(KEY,PAGE)+"if(f.error)return {error:true};if(!f.chunkReady)return {ready:false};const value=f.chunk;delete f.chunk;f.chunkReady=false;return {ready:true,chunk:value};})()","chunks",chunks);
        Files.writeString(Path.of(args[0]),scripts.toString());
      }
      System.out.println(J.obj("status","passed","checks",checks,"actualAndroidExecution",false,"actualWebViewExecution",false));
    }finally{try(java.util.stream.Stream<Path> files=Files.list(directory)){for(Path file:(Iterable<Path>)files::iterator)Files.deleteIfExists(file);}Files.deleteIfExists(directory);}
  }
}
