package local.pocketchat;

import java.io.*;
import java.util.Base64;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.json.*;

/** Reads a temporary file inside its original document, without a public JS bridge. */
final class BrowserBlobDownload {
  static final int CHUNK_BYTES=192*1024;
  interface Page {
    /** Thread-safe native lifetime and route admission, without WebView calls. */
    boolean current();
    /** Invoked only on the UI thread; rechecks the original WebView URL. */
    void evaluate(String script,Consumer<String> done);
    /** Removes only this task's local Blob state, even after a route is lost. */
    default void discard(String script){evaluate(script,ignored->{});}
  }
  interface Main {void post(Runnable task);}
  interface Progress {void update(long received,long total);}
  static final class Result {
    final File file;final String mime;final long bytes;
    Result(File file,String mime,long bytes){this.file=file;this.mime=mime;this.bytes=bytes;}
  }
  volatile boolean cancelled;
  void cancel(){cancelled=true;}
  void check(Page page)throws IOException {
    if(cancelled||Thread.currentThread().isInterrupted())throw new IOException("下载已取消");
    if(!page.current())throw new IOException("原网页或连接已变化，请在原网页重新下载");
  }
  String evaluate(Page page,Main main,String code)throws IOException {
    check(page);CountDownLatch completed=new CountDownLatch(1);String[] result={null};
    main.post(()->{
      if(cancelled||!page.current()){completed.countDown();return;}
      try{page.evaluate(code,value->{result[0]=value;completed.countDown();});}
      catch(RuntimeException unavailable){completed.countDown();}
    });
    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
    try{
      while(!completed.await(100,TimeUnit.MILLISECONDS)){check(page);if(System.nanoTime()>=deadline)throw new IOException("读取网页文件超时，请重试");}
    }catch(InterruptedException stopped){Thread.currentThread().interrupt();throw new IOException("下载已取消",stopped);}
    check(page);if(result[0]==null)throw new IOException("原网页无法提供文件，请重新下载");return result[0];
  }
  JSONObject poll(Page page,Main main,String code,long seconds)throws IOException {
    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(seconds);
    while(true){
      String raw=evaluate(page,main,code);
      if(raw.length()>CHUNK_BYTES*2)throw new IOException("网页文件片段过大，未保存");
      final JSONObject result;try{result=new JSONObject(raw);}catch(JSONException invalid){throw new IOException("网页返回的文件信息无效",invalid);}
      if(result.optBoolean("error"))throw new IOException("临时文件已失效，请在原网页重新生成或下载");
      if(result.optBoolean("ready"))return result;
      if(System.nanoTime()>=deadline)throw new IOException("读取网页文件超时，请重试");
      try{Thread.sleep(80);}catch(InterruptedException stopped){Thread.currentThread().interrupt();throw new IOException("下载已取消",stopped);}
      check(page);
    }
  }
  static String guard(String key,String source){return "const f=window["+JSONObject.quote(key)+"];if(!f||f.document!==document||location.href!=="+JSONObject.quote(source)+")return {error:true};";}
  static String prepareScript(String key,String source,String target){
    return "(()=>{if(location.href!=="+JSONObject.quote(source)+")return {error:true};const f={document,ready:false};window["+JSONObject.quote(key)+"]=f;"
        +"fetch("+JSONObject.quote(target)+").then(r=>{if(!r.ok)throw Error();return r.blob();}).then(b=>{if(window["+JSONObject.quote(key)+"]===f&&f.document===document){f.blob=b;f.size=b.size;f.mime=b.type;f.ready=true;}}).catch(()=>{f.error=true;});return {started:true};})()";
  }
  static String chunkScript(String key,String source,long start,long end){
    return "(()=>{"+guard(key,source)+"if(!f.blob||f.size<"+end+")return {error:true};delete f.chunk;f.chunkReady=false;"
        +"f.blob.slice("+start+","+end+").arrayBuffer().then(value=>{const bytes=new Uint8Array(value);let text='';for(let i=0;i<bytes.length;i+=8192)text+=String.fromCharCode(...bytes.subarray(i,i+8192));f.chunk=btoa(text);f.chunkReady=true;}).catch(()=>{f.error=true;});return {started:true};})()";
  }
  Result fetch(String source,String target,File cache,Page page,Main main,Progress progress)throws IOException {
    if(!GeckoDownloadNavigation.sameOriginBlob(source,target))throw new IOException("临时文件不属于当前网页，请回原网页下载");
    String key="__pocketBrowserBlob"+UUID.randomUUID().toString().replace("-","");File partial=null;boolean delivered=false;
    try{
      evaluate(page,main,prepareScript(key,source,target));
      JSONObject metadata=poll(page,main,"(()=>{"+guard(key,source)+"return {ready:f.ready===true,error:f.error===true,size:f.size,mime:f.mime};})()",15);
      Object length=metadata.opt("size");if(!(length instanceof Number))throw new IOException("网页文件长度无效");
      double rawLength=((Number)length).doubleValue();long total=((Number)length).longValue();
      if(!Double.isFinite(rawLength)||rawLength!=total||total<0||total>BrowserDownloadTransfer.MAX_BYTES)throw new IOException("文件超过 512 MB 下载限额，或长度无效");
      if(cache.getUsableSpace()<BrowserDownloadTransfer.RESERVE_BYTES+total)throw new IOException("可用存储空间不足");
      String mime=DownloadFileInfo.mime(metadata.optString("mime"));partial=File.createTempFile("browser-blob-",".part",cache);
      try(FileOutputStream output=new FileOutputStream(partial)){
        for(long offset=0;offset<total;){
          check(page);long end=Math.min(total,offset+CHUNK_BYTES);
          evaluate(page,main,chunkScript(key,source,offset,end));
          JSONObject block=poll(page,main,"(()=>{"+guard(key,source)+"if(f.error)return {error:true};if(!f.chunkReady)return {ready:false};const value=f.chunk;delete f.chunk;f.chunkReady=false;return {ready:true,chunk:value};})()",10);
          Object encoded=block.opt("chunk");if(!(encoded instanceof String)||((String)encoded).length()>((CHUNK_BYTES+2)/3)*4)throw new IOException("网页文件片段无效");
          byte[] bytes;try{bytes=Base64.getDecoder().decode((String)encoded);}catch(IllegalArgumentException invalid){throw new IOException("网页文件片段无效",invalid);}
          if(bytes.length!=end-offset)throw new IOException("网页文件片段不完整，请重新下载");
          check(page);if(cache.getUsableSpace()<BrowserDownloadTransfer.RESERVE_BYTES)throw new IOException("可用存储空间不足");
          output.write(bytes);offset=end;progress.update(offset,total);
        }
        check(page);output.getFD().sync();
      }
      if(partial.length()!=total)throw new IOException("网页文件未读取完整，未保存");
      check(page);delivered=true;return new Result(partial,mime,total);
    }finally{
      main.post(()->{try{page.discard("(()=>{const f=window["+JSONObject.quote(key)+"];if(f&&f.document===document)delete window["+JSONObject.quote(key)+"];})()");}catch(RuntimeException ignored){}});
      if(!delivered&&partial!=null)partial.delete();
    }
  }
}
