package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.webkit.*;
import android.widget.*;
import android.view.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Downloads keep the configured route and save automatically to an app-owned destination. */
class FileDownloads {
  static final int SAVE=83;static final long MAX=512L*1024*1024;
  final MainActivity a;final ExecutorService worker=Executors.newSingleThreadExecutor();
  volatile InputStream nativeInput;volatile boolean cancelled;volatile HttpURLConnection connection;volatile File temp;volatile boolean active,destroyed;String imageLabel="",name="文件",mime="application/octet-stream",sourceId="",sourceKey="",sourceUrl="",retryUrl="",agent="",blobKey="",blobPage="";volatile long ticket=0;long blobSize,offset,ignoreUntil=0;Dialog dialog;AlertDialog noticeDialog;TextView progress;
  final SavedFileActions savedActions;final DownloadTasks tasks;JSONObject task;boolean resumeRequested=false,minimized=false,completeFile=false,awaitingPicker=false,retiringPartial=false,persistenceBlocked=false;long pickerTicket=-1,lastProgressSaved;static final long PROGRESS_SAVE_INTERVAL=2000;volatile Uri savingDestination;AlertDialog manager;String resumeValidator="",resumeAddress="";volatile long receivedBytes=0,totalBytes=-1;
  FileDownloads(MainActivity a){this.a=a;savedActions=new SavedFileActions(a);tasks=new DownloadTasks(a);a.remote.setDownloadListener((url,ua,cd,type,size)->accept(url,ua,cd,type,size));a.remote.responseDownload=this::acceptResponse;}
  void acceptResponse(org.mozilla.geckoview.WebResponse response){
    InputStream input=response.body;
    if(input==null){a.status("网页未提供文件内容，请重新点按下载");return;}
    if(destroyed||retiringPartial||active&&!retryUrl.isEmpty()||awaitingPicker||System.currentTimeMillis()<ignoreUntil){try{input.close();}catch(IOException ignored){}a.status("请先完成当前下载，再下载这个文件");return;}
    try{AppPrefs.requireDownloadNetwork(a);if(!a.session.guard.allowed())throw new IOException("受保护连接已中断，下载已暂停");}catch(IOException error){try{input.close();}catch(IOException ignored){}a.status(error.getMessage());return;}
    if(!active){newTask("","",a.conversation);if(persistenceBlocked){try{input.close();}catch(IOException ignored){}return;}sourceId="";sourceKey="";sourceUrl=a.conversation;imageLabel="";active=true;a.session.transferActive=true;a.session.updateBrowserActivity();cancelled=false;++ticket;}
    DownloadTasks.put(task,"transferKind","gecko-response");retryUrl=response.uri;String proposed=GeckoWebView.header(response,"Content-Type"),disposition=GeckoWebView.header(response,"Content-Disposition");
    if(sourceId.isEmpty()||name.equals("文件"))name=safeName(URLUtil.guessFileName(response.uri,disposition,proposed));mime=type(name,proposed);mark("downloading","");if(persistenceBlocked){try{input.close();}catch(IOException ignored){}return;}
    response.setReadTimeoutMillis(25000);nativeInput=input;long attempt=ticket;showProgress("正在下载 "+name+"…");
    worker.execute(()->{try(InputStream stream=input){
      if(response.statusCode>=400)throw new IOException("网页未能提供文件（HTTP "+response.statusCode+"），请在原网页重新点按下载");
      long expected=-1;try{if(GeckoWebView.header(response,"Content-Encoding").isEmpty()||"identity".equalsIgnoreCase(GeckoWebView.header(response,"Content-Encoding")))expected=Long.parseLong(GeckoWebView.header(response,"Content-Length"));}catch(Exception ignored){}
      if(expected>MAX)throw new IOException("文件超过 512 MB");
      if(!valid(attempt))throw new IOException("下载已暂停");File file=File.createTempFile("download-",".part",a.getCacheDir());if(!valid(attempt)){file.delete();throw new IOException("下载已暂停");}temp=file;totalBytes=expected;receivedBytes=0;
      a.handler.post(()->{if(valid(attempt)){DownloadTasks.put(task,"partial",file.getName());saveTask();}});
      SealedFileIo.lease(file,()->{if(!valid(attempt))throw new IOException("下载已暂停");
        try(OutputStream output=new FileOutputStream(file)){byte[] buffer=new byte[65536];int count;long reported=0;
          while((count=stream.read(buffer))!=-1){AppPrefs.requireDownloadNetwork(a);if(!valid(attempt)||!a.session.guard.allowed())throw new IOException("下载已暂停");if(receivedBytes+count>MAX||a.getCacheDir().getUsableSpace()<64L*1024*1024)throw new IOException("文件过大或剩余空间不足");output.write(buffer,0,count);receivedBytes+=count;if(System.currentTimeMillis()-reported>400){reported=System.currentTimeMillis();a.handler.post(()->{if(valid(attempt))transferProgress();});}}
        }return null;
      });
      if(expected>=0&&receivedBytes!=expected)throw new IOException("文件未下载完整，请在原网页重新下载");
      a.handler.post(()->{if(valid(attempt)){transferProgress();choose(attempt);}});
    }catch(Exception error){fail(attempt,error.getMessage());}finally{if(nativeInput==input)nativeInput=null;}});
  }
  static boolean https(String url){try{Uri u=Uri.parse(url);return "https".equals(u.getScheme())&&u.getHost()!=null&&u.getUserInfo()==null&&!url.matches("(?s).*[\\x00-\\x20\\\\].*");}catch(Exception e){return false;}}
  static String safeName(String value){String clean=(value==null?"文件":value).replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]","_").trim();return clean.isEmpty()?"文件":clean.length()>160?clean.substring(clean.length()-160):clean;}
  static String type(String name,String proposed){String ext=name.lastIndexOf('.')>=0?name.substring(name.lastIndexOf('.')+1).toLowerCase(Locale.ROOT):"";String known=MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);return known!=null?known:proposed==null||proposed.isEmpty()?"application/octet-stream":proposed.split(";")[0];}
  boolean intercept(String url){if(!active||!retryUrl.isEmpty()||sourceId.isEmpty()||!https(url))return false;Uri u=Uri.parse(url);String path=u.getPath()==null?"":u.getPath();if(MainActivity.chatUrl(url)&&!path.contains("/files/")&&!path.matches("(?i).*[.](docx?|pdf|xlsx?|pptx?|zip|csv|txt)$"))return false;accept(url,a.remote.getSettings().getUserAgentString(),"",type(name,null),-1);return true;}
  boolean sameSource(){return sourceUrl.equals(a.conversation)&&!a.session.navigating&&MainActivity.chatUrl(a.remote.getUrl());}
  void open(String id,String key){if(retiringPartial){a.status("正在清理旧的未完成副本，请稍后再试");return;}try{AppPrefs.requireDownloadNetwork(a);}catch(IOException e){a.status(e.getMessage());return;}if(awaitingPicker){a.status("请先关闭文件保存窗口");return;}if(active){a.status("请先完成或取消当前下载");return;}if(a.session.offline||!a.session.networkReady||a.session.navigating){a.status("请联网并等待对话加载后再下载");return;}if(!resumeRequested){newTask(id,key,a.conversation);if(persistenceBlocked)return;}resumeRequested=false;retryUrl="";ignoreUntil=0;sourceId=id;sourceKey=key;sourceUrl=a.conversation;active=true;a.session.transferActive=true;a.session.updateBrowserActivity();cancelled=false;long attempt=++ticket;showProgress("正在获取文件下载链接…");a.runDriver("file-prepare",J.obj("id",id,"key",key,"expectedUrl",sourceUrl),r->{if(!valid(attempt))return;if(!r.optBoolean("ok")){fail(attempt,r.optString("reason","文件链接暂不可用"));return;}name=safeName(r.optString("name","文件"));imageLabel="image".equals(r.optString("kind"))?name:"";a.handler.postDelayed(()->point(attempt,false),120);});}
  void point(long attempt,boolean followup){if(!valid(attempt)||!sameSource()){fail(attempt,"对话已改变，请返回原对话下载");return;}a.runDriver(followup?"file-followup":"file-point",J.obj("id",sourceId,"key",sourceKey,"name",name,"expectedUrl",sourceUrl),r->{if(!valid(attempt))return;JSONObject point=r.optJSONObject("touch");if(point!=null){float x=(float)(point.optDouble("x")*a.remote.getWidth()/point.optDouble("width",1)),y=(float)(point.optDouble("y")*a.remote.getHeight()/point.optDouble("height",1));long time=android.os.SystemClock.uptimeMillis();a.remote.requestFocus();MotionEvent down=MotionEvent.obtain(time,time,MotionEvent.ACTION_DOWN,x,y,0);down.setSource(InputDevice.SOURCE_TOUCHSCREEN);a.remote.dispatchTouchEvent(down);down.recycle();a.handler.postDelayed(()->{if(!valid(attempt))return;MotionEvent up=MotionEvent.obtain(time,android.os.SystemClock.uptimeMillis(),MotionEvent.ACTION_UP,x,y,0);up.setSource(InputDevice.SOURCE_TOUCHSCREEN);a.remote.dispatchTouchEvent(up);up.recycle();},60);}if(!followup)a.handler.postDelayed(()->{if(valid(attempt)&&retryUrl.isEmpty())point(attempt,true);},1200);else a.handler.postDelayed(()->{if(valid(attempt)&&retryUrl.isEmpty())fail(attempt,"网页未提供下载，请重试或查看原网页");},8000);});}
  boolean valid(long attempt){return active&&!cancelled&&!destroyed&&attempt==ticket&&tasks.owns(task);}
  void accept(String url,String ua,String disposition,String proposed,long length){if(awaitingPicker||retiringPartial)return;if(System.currentTimeMillis()<ignoreUntil)return;if(active&&!retryUrl.isEmpty())return;if(!https(url)&&!url.startsWith("blob:https://")){a.status("这个下载地址暂不支持，请查看原网页");return;}if(!active){if(!resumeRequested){newTask("","",a.conversation);if(persistenceBlocked)return;}resumeRequested=false;imageLabel="";sourceId="";sourceKey="";sourceUrl=a.conversation;active=true;a.session.transferActive=true;a.session.updateBrowserActivity();cancelled=false;++ticket;name=safeName(URLUtil.guessFileName(url,disposition,proposed));}if(length>MAX||length>a.getCacheDir().getUsableSpace()-64L*1024*1024){fail(ticket,"文件超过本机下载限额或可用空间，请使用浏览器另行下载");return;}if(name.equals("文件")||sourceId.isEmpty()||name.matches("图片 [0-9]+"))name=safeName(URLUtil.guessFileName(url,disposition,proposed));mime=type(name,proposed);if(!imageLabel.isEmpty()&&mime.startsWith("image/"))name=imageLabel+"."+imageExtension(mime);DownloadTasks.put(task,"transferKind",url.startsWith("blob:")?"blob":"http-range");retryUrl=url;agent=ua;mark("downloading","");if(persistenceBlocked)return;long attempt=ticket;showProgress("正在下载 "+name+"…");if(url.startsWith("blob:"))startBlob(attempt,url);else worker.execute(()->download(attempt,url,ua));}
  static String imageExtension(String type){String ext=MimeTypeMap.getSingleton().getExtensionFromMimeType(type);return ext==null?"png":ext;}
  Proxy route()throws Exception{AppPrefs.requireDownloadNetwork(a);if(!a.session.guard.allowed())throw new IOException("受保护连接已中断，下载已暂停");if(a.session.internalNetwork()){NativeNetwork n=NativeNetwork.get(a);if(!n.connectionAdmission().usable())throw new IOException("应用代理未连接，请恢复连接后重试");Uri u=Uri.parse(n.proxy());return new Proxy(Proxy.Type.HTTP,new InetSocketAddress(u.getHost(),u.getPort()));}String proxy=a.prefs.getString("proxy","");if(proxy.isEmpty())return Proxy.NO_PROXY;if(!MainActivity.validProxy(proxy))throw new IOException("代理配置无效");Uri u=Uri.parse(proxy);if("https".equals(u.getScheme()))throw new IOException("当前代理类型请使用原网页下载");return new Proxy("socks".equals(u.getScheme())?Proxy.Type.SOCKS:Proxy.Type.HTTP,new InetSocketAddress(u.getHost(),u.getPort()));}
  HttpURLConnection connect(String url,Proxy proxy)throws Exception{return (HttpURLConnection)new URL(url).openConnection(proxy);}
  void download(long attempt,String initial,String ua){
    File local=temp;
    try{
      if(local==null||!local.isFile()){if(!valid(attempt))throw new IOException("下载已暂停");local=File.createTempFile("download-",".part",a.getCacheDir());if(!valid(attempt)){local.delete();throw new IOException("下载已暂停");}temp=local;}
      File partial=local;a.handler.post(()->{if(valid(attempt)){DownloadTasks.put(task,"partial",partial.getName());saveTask();}});
      try(NativeDownloadRoute frozen=new NativeDownloadRoute(a.session,route())){String url=initial;
      for(int redirects=0;redirects<=5;redirects++){
        if(!valid(attempt))throw new IOException("下载已取消");AppPrefs.requireDownloadNetwork(a);if(!https(url)||!BrowserNetworkGuard.publicHttps(Uri.parse(url)))throw new IOException("下载地址或重定向不受支持");if(!a.session.guard.allowed())throw new IOException("受保护连接已中断，下载已暂停");
        HttpURLConnection c=frozen.open(url,this::connect);connection=c;c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(25000);c.setRequestProperty("Accept-Encoding","identity");
        if(ua!=null)c.setRequestProperty("User-Agent",ua);String cookie=a.remote.downloadCookies(url);if(cookie!=null)c.setRequestProperty("Cookie",cookie);
        long base=local.length();String expected=resumeValidator;
        if(base>0&&!expected.isEmpty()&&resumeAddress.equals(DownloadRange.resource(url))){c.setRequestProperty("Range","bytes="+base+"-");c.setRequestProperty("If-Range",expected);}else base=0;
        try{
          frozen.check();int code=c.getResponseCode();frozen.check();if(!valid(attempt))throw new IOException("下载已暂停，受保护连接不可用");if(code>=300&&code<400){String next=c.getHeaderField("Location");if(next==null)throw new IOException("下载重定向缺少地址");url=new URL(new URL(url),next).toString();continue;}
          if(code!=200&&code!=206){if(code==416){resumeValidator="";resumeAddress="";}throw new IOException(code==401||code==403?"链接已过期，点继续重新获取文件":"下载失败（HTTP "+code+"）");}
          long total;try{total=DownloadRange.total(c,base,expected);}catch(IOException invalid){resumeValidator="";resumeAddress="";File resetFile=local;SealedFileIo.lease(resetFile,()->{if(!valid(attempt))throw new IOException("下载已暂停");try(RandomAccessFile reset=new RandomAccessFile(resetFile,"rw")){reset.setLength(0);}return null;});receivedBytes=0;throw invalid;}
          if(code==200)base=0;
          if(total>MAX||total-base>a.getCacheDir().getUsableSpace()-64L*1024*1024)throw new IOException("文件超过本机 512 MB 限额或剩余空间不足");
          String encoding=c.getContentEncoding();if(encoding!=null&&!encoding.equalsIgnoreCase("identity"))throw new IOException("文件编码不支持安全续传，请使用原网页下载");
          String nextValidator=DownloadRange.validator(c.getHeaderField("ETag"),c.getHeaderField("Last-Modified")),nextAddress=DownloadRange.resource(url);
          String contentType=c.getContentType();if(contentType!=null&&contentType.startsWith("image/")){mime=contentType.split(";")[0];name=imageLabel.isEmpty()?safeName(URLUtil.guessFileName(url,c.getHeaderField("Content-Disposition"),mime)):imageLabel+"."+imageExtension(mime);}if(contentType!=null&&contentType.startsWith("text/html")&&!mime.equals("text/html"))throw new IOException("文件链接返回了登录网页，请在原网页检查");
          receivedBytes=base;totalBytes=total;final long initialBytes=base;final File target=local;
          long received=SealedFileIo.lease(target,()->{if(!valid(attempt))throw new IOException("下载已暂停");if(code==206&&(!target.isFile()||target.length()!=initialBytes))throw new IOException("本机部分文件已变化，请重新获取下载链接后重试");long copied=initialBytes,reported=0;
            try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(target,code==206)){
              resumeValidator=nextValidator;resumeAddress=nextAddress;
              byte[] bytes=new byte[65536];int size;
              while((size=in.read(bytes))!=-1){frozen.check();if(!valid(attempt))throw new IOException("下载已暂停，受保护连接不可用");if(a.getCacheDir().getUsableSpace()<64L*1024*1024)throw new IOException("本机剩余空间不足，请清理后继续");copied+=size;if(copied>MAX)throw new IOException("文件超过 512 MB");out.write(bytes,0,size);receivedBytes=copied;
                if(System.currentTimeMillis()-reported>400){reported=System.currentTimeMillis();a.handler.post(()->{if(valid(attempt))transferProgress();});}
              }
            }return copied;
          });
          frozen.check();if(total>=0&&received!=total)throw new IOException("文件未下载完整，可继续下载");
          a.handler.post(()->{if(valid(attempt)){transferProgress();choose(attempt);}});return;
        }finally{frozen.released(c);c.disconnect();if(connection==c)connection=null;}
      }
      throw new IOException("文件重定向次数过多");}
    }catch(Exception e){fail(attempt,e.getMessage());}
  }
  void startBlob(long attempt,String url){try{Uri origin=Uri.parse(a.remote.getUrl()),blobOrigin=Uri.parse(url.substring(5));if(!Objects.equals(origin.getScheme(),blobOrigin.getScheme())||!Objects.equals(origin.getHost(),blobOrigin.getHost())||origin.getPort()!=blobOrigin.getPort())throw new IOException("文件页面已改变，请重试");if(temp!=null)temp.delete();temp=File.createTempFile("download-",".part",a.getCacheDir());DownloadTasks.put(task,"partial",temp.getName());if(!saveTask())return;resumeValidator="";blobPage=a.remote.getUrl();blobKey="__pocketFile"+UUID.randomUUID().toString().replace("-","");String key=JSONObject.quote(blobKey);a.remote.evaluateJavascript("void(fetch("+JSONObject.quote(url)+").then(r=>r.blob()).then(b=>window["+key+"]={blob:b,size:b.size,mime:b.type,ready:true}).catch(()=>window["+key+"]={error:true}))",r->pollBlob(attempt,System.currentTimeMillis()+15000));}catch(Exception e){fail(attempt,e.getMessage());}}
  boolean blobValid(long attempt){return valid(attempt)&&Objects.equals(blobPage,a.remote.getUrl());}
  void pollBlob(long attempt,long deadline){if(!blobValid(attempt)){fail(attempt,"文件页面已改变，请重试");return;}a.remote.evaluateJavascript("(()=>{const f=window["+JSONObject.quote(blobKey)+"];return f?{ready:f.ready,size:f.size,mime:f.mime,error:f.error}:{};})()",raw->{if(!valid(attempt))return;JSONObject f=J.parse(raw);if(f.optBoolean("error")){fail(attempt,"文件链接已失效，请重试获取");return;}if(f.optBoolean("ready")){blobSize=f.optLong("size");totalBytes=blobSize;receivedBytes=0;if(f.optString("mime").startsWith("image/")){mime=f.optString("mime");name=imageLabel.isEmpty()?safeName(URLUtil.guessFileName(retryUrl,"",mime)):imageLabel+"."+imageExtension(mime);}if(blobSize>MAX||blobSize>a.getCacheDir().getUsableSpace()-64L*1024*1024){fail(attempt,"文件超过 512 MB 或剩余空间不足");return;}offset=0;chunk(attempt);}else if(System.currentTimeMillis()<deadline)a.handler.postDelayed(()->pollBlob(attempt,deadline),120);else fail(attempt,"读取文件超时，请重试");});}
  void chunk(long attempt){if(!blobValid(attempt)){fail(attempt,"文件页面已改变，请重试");return;}if(offset>=blobSize){clearBlob();choose(attempt);return;}long end=Math.min(blobSize,offset+192*1024);String key=JSONObject.quote(blobKey);a.remote.evaluateJavascript("void((async()=>{const f=window["+key+"];if(!f)return;try{const bytes=new Uint8Array(await f.blob.slice("+offset+","+end+").arrayBuffer());let text='';for(let i=0;i<bytes.length;i+=8192)text+=String.fromCharCode(...bytes.subarray(i,i+8192));f.chunk=btoa(text);}catch{f.error=true;}})())",r->readChunk(attempt,end,System.currentTimeMillis()+10000));}
  void readChunk(long attempt,long end,long deadline){if(!blobValid(attempt)){fail(attempt,"文件页面已改变，请重试");return;}a.remote.evaluateJavascript("(()=>{const f=window["+JSONObject.quote(blobKey)+"];if(!f||f.error)return {error:true};if(typeof f.chunk!=='string')return {};const chunk=f.chunk;delete f.chunk;return {chunk};})()",raw->{if(!valid(attempt))return;JSONObject f=J.parse(raw);if(f.optBoolean("error")){fail(attempt,"读取文件失败");return;}if(!f.has("chunk")){if(System.currentTimeMillis()<deadline)a.handler.postDelayed(()->readChunk(attempt,end,deadline),100);else fail(attempt,"读取文件超时");return;}File file=temp;worker.execute(()->{try{byte[] bytes=android.util.Base64.decode(f.getString("chunk"),android.util.Base64.DEFAULT);if(bytes.length!=end-offset)throw new IOException();SealedFileIo.lease(file,()->{if(!valid(attempt))throw new IOException();try(OutputStream out=new FileOutputStream(file,true)){out.write(bytes);}return null;});offset=end;receivedBytes=end;totalBytes=blobSize;a.handler.post(()->{if(valid(attempt)){transferProgress();chunk(attempt);}});}catch(Exception e){fail(attempt,"文件片段保存失败，请重试");}});});}
  void chooseManually(long attempt){if(!valid(attempt))return;if(!task.optString("pendingDestination").isEmpty()){a.status("上次保存结果待确认，请先在下载记录中重试核验");return;}completeFile=true;mark("choosing","");if(persistenceBlocked)return;dismiss();pickerTicket=attempt;awaitingPicker=true;try{a.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,name),SAVE);}catch(ActivityNotFoundException e){awaitingPicker=false;fail(attempt,"设备没有文件保存器");}}
  boolean validSave(long attempt,JSONObject chosenTask){if(!valid(attempt)||task!=chosenTask||!tasks.owns(chosenTask))return false;JSONObject environment=ProfileCatalog.get(a).item(Profiles.slot(a));return environment.optBoolean("created")&&!environment.optBoolean("deleting")&&!environment.optBoolean("resetting")&&a.session.environmentId.equals(environment.optString("environmentId"))&&a.session.environmentGeneration==environment.optInt("generation");}
  void commitSaved(long attempt,JSONObject chosenTask,String generation,Uri uri,String savedName,String location,long savedBytes,JSONObject facts){
    if(!validSave(attempt,chosenTask))throw new IllegalStateException("保存已取消");
    if(savedBytes<0)throw new IllegalStateException("保存字节数尚未确认");
    tasks.requirePending(chosenTask,uri,generation);long published;try{published=DownloadLibrary.get(a).publicationTime(uri);}catch(RuntimeException error){throw new DownloadTasks.PersistenceFailure(error);}name=savedName;
    tasks.finishSave(chosenTask,uri,generation,()->{updateTask("saved","");DownloadTasks.put(chosenTask,"uri",uri.toString(),"location",location,"time",published);if(facts!=null)for(String key:new String[]{"actualName","actualMime"})if(facts.has(key))DownloadTasks.put(chosenTask,key,facts.opt(key));DownloadMetadataValues.checked(chosenTask,savedBytes,"published-copy","known");});
    lastProgressSaved=android.os.SystemClock.elapsedRealtime();savingDestination=null;active=false;retryUrl="";tasks.release();
    // The legacy history is secondary. Its failure cannot roll back committed bytes.
    try{remember(uri);}catch(RuntimeException ignored){}
  }
  void finishSaved(JSONObject chosenTask,File file,String savedName){
    SavedFilePublication.complete(tasks,chosenTask,file,()->a.handler.post(()->{
      // Publication already committed. Notification or view failures must never
      // roll back a durable saved file, and a later transfer keeps its own state.
      if(task==chosenTask&&!active){if(temp==file)temp=null;a.session.transferActive=false;a.session.updateBrowserActivity();dismiss();}
      ChatService.downloaded(a,chosenTask.optString("id"),savedName);if(a.hub!=null&&a.hub.page==1)a.hub.refresh();
    }));
  }
  void pauseUnconfirmed(long attempt,JSONObject chosenTask){
    a.handler.post(()->{
      if(task!=chosenTask||attempt!=ticket||destroyed)return;
      active=false;ticket++;savingDestination=null;updateTask("paused","文件已下载，保存记录尚未完成；可稍后重试保存。");
      if(!saveTask())return;tasks.release();
      a.session.transferActive=false;a.session.updateBrowserActivity();dismiss();if(a.hub!=null&&a.hub.page==1)a.hub.refresh();
    });
  }
  void choose(long attempt){
    if(!valid(attempt))return;if(!task.optString("pendingDestination").isEmpty()){a.status("上次保存结果待确认，请先在下载记录中重试核验");return;}completeFile=true;mark("saving","");if(persistenceBlocked)return;showProgress("正在保存到默认下载位置…");
    File file=temp;String chosenName=name,chosenMime=mime,generation=UUID.randomUUID().toString();JSONObject chosenTask=task;
    worker.execute(()->{
      DefaultDownloads.Target target=null;final long[] savedBytes={-1};final JSONObject[] facts={null};
      try{
        target=DefaultDownloads.create(a,chosenName,chosenMime);DefaultDownloads.Target destination=target;
        SavedFilePublication.run(a,target.uri,a.handler,()->{
          if(!validSave(attempt,chosenTask))throw new IllegalStateException("保存已取消");
          tasks.beginSave(chosenTask,destination.uri,destination.location,destination.name,generation);savingDestination=destination.uri;
        },()->{
          try(InputStream in=new FileInputStream(file);OutputStream out=destination.output()){
            savedBytes[0]=SavedFileBytes.copy(in,out,()->valid(attempt));
          }
          if(!valid(attempt))throw new IOException("保存已暂停");destination.publish();facts[0]=SavedDownloadMetadata.describe(a,destination.uri);return null;
        },()->commitSaved(attempt,chosenTask,generation,destination.uri,destination.name,destination.location,savedBytes[0],facts[0]),()->{
          if(!tasks.published(chosenTask,destination.uri))destination.abort();
        });
        finishSaved(chosenTask,file,target.name);
      }catch(Exception error){
        if(SavedFilePublication.unconfirmed(error)){pauseUnconfirmed(attempt,chosenTask);return;}
        DefaultDownloads.Target destination=target;
        if(destination!=null)a.handler.post(()->{if(destination.uri.equals(savingDestination))savingDestination=null;try{tasks.clearPending(chosenTask,destination.uri,generation);}catch(DownloadTasks.PersistenceFailure failure){persistenceFailed(failure);}});
        fail(attempt,"默认保存失败，文件已下载。可重试或从下载管理另存为。");
      }
    });
  }
  void result(int code,Intent data){
    long chosen=pickerTicket;awaitingPicker=false;pickerTicket=-1;
    if(!valid(chosen)){if(data!=null&&data.getData()!=null){Uri unused=data.getData();new Thread(()->{try{SavedFileDeletion.lease(a,unused,()->{if(!DownloadLibrary.get(a).indexed(unused))deleteIncomplete(unused);return null;});}catch(Exception ignored){}},"download-picker-cleanup").start();}return;}
    if(code!=Activity.RESULT_OK||data==null||data.getData()==null){pause();return;}
    long attempt=ticket;Uri uri=data.getData();String generation=UUID.randomUUID().toString(),chosenName=name;JSONObject chosenTask=task;savingDestination=uri;
    try{boolean read=(data.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0,write=(data.getFlags()&Intent.FLAG_GRANT_WRITE_URI_PERMISSION)!=0;int grants=read?(write?Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION:Intent.FLAG_GRANT_READ_URI_PERMISSION):(write?Intent.FLAG_GRANT_WRITE_URI_PERMISSION:0);a.getContentResolver().takePersistableUriPermission(uri,grants);}catch(Exception ignored){}
    File file=temp;mark("saving","");if(persistenceBlocked)return;showProgress("正在保存文件…");worker.execute(()->{final long[] savedBytes={-1};final JSONObject[] facts={null};
      // Reject an existing indexed destination before the publication helper owns
      // cleanup, so a failed overwrite never deletes that earlier saved file.
      try{SavedFileDeletion.lease(a,uri,()->{
        if(DownloadLibrary.get(a).indexed(uri))throw new IOException("请保存为新的文件名，已有下载文件已保留");
        SavedFilePublication.run(a,uri,a.handler,()->{
          if(!validSave(attempt,chosenTask))throw new IllegalStateException("保存已取消");
          tasks.beginSave(chosenTask,uri,"你选择的保存位置",chosenName,generation);
        },()->{
          try(InputStream in=new FileInputStream(file);OutputStream out=a.getContentResolver().openOutputStream(uri,"wt")){
            savedBytes[0]=SavedFileBytes.copy(in,out,()->valid(attempt));
          }
          facts[0]=SavedDownloadMetadata.describe(a,uri);return null;
        },()->commitSaved(attempt,chosenTask,generation,uri,chosenName,"你选择的保存位置",savedBytes[0],facts[0]),()->{if(!tasks.published(chosenTask,uri))deleteIncomplete(uri);});return null;
      });finishSaved(chosenTask,file,chosenName);
      }catch(Exception error){if(SavedFilePublication.unconfirmed(error)){pauseUnconfirmed(attempt,chosenTask);return;}a.handler.post(()->{if(uri.equals(savingDestination))savingDestination=null;try{tasks.clearPending(chosenTask,uri,generation);}catch(DownloadTasks.PersistenceFailure failure){persistenceFailed(failure);}});fail(attempt,error.getMessage()!=null&&error.getMessage().contains("新的文件名")?error.getMessage():"保存失败，请选择可写入的位置后重试");}
    });
  }
  void deleteIncomplete(Uri uri){try{if(android.provider.DocumentsContract.isDocumentUri(a,uri))android.provider.DocumentsContract.deleteDocument(a.getContentResolver(),uri);else a.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}}
  void remember(Uri uri){long published=task.optLong("time");JSONArray previous=J.parse(a.prefs.getString("downloadHistory","{}")).optJSONArray("files"),files=new JSONArray();JSONObject remembered=J.obj("slot",Profiles.slot(a),"id",task.optString("id"),"name",name,"mime",mime,"uri",uri.toString(),"location",task.optString("location"),"time",published);DownloadMetadataValues.copy(task,remembered);files.put(remembered);if(previous!=null)for(int i=0;i<Math.min(49,previous.length());i++)if(!uri.toString().equals(previous.optJSONObject(i).optString("uri")))files.put(previous.optJSONObject(i));a.prefs.edit().putString("downloadHistory",J.obj("files",files).toString()).apply();}
  void openSaved(Uri uri,String type){openSaved(uri,type,name);}
  void openSaved(Uri uri,String type,String title){openSaved(uri,type,title,true);}
  void openSaved(Uri uri,String type,String title,boolean confirmed){try{if("application/pdf".equals(type)||type.startsWith("image/")){a.startActivity(new Intent(a,Profiles.preview(a)).putExtra("uri",uri.toString()).putExtra("name",title).putExtra("mime",type));return;}a.startActivity(new Intent(Intent.ACTION_VIEW).setDataAndType(uri,type).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));}catch(ActivityNotFoundException e){a.status(confirmed?"文件已保存；手机尚未安装支持此格式的查看器":"保存结果仍待确认；手机尚未安装支持此格式的查看器");}catch(Exception e){a.status(confirmed?"文件已移动或访问失效，请重新下载":"保存结果仍待确认；无法访问原保存位置，请检查文件权限后重试核验");}}
  void showProgress(String text){if(destroyed||minimized)return;if(dialog==null){LinearLayout box=new LinearLayout(a);box.setGravity(Gravity.CENTER_VERTICAL);box.setPadding(a.dp(24),a.dp(20),a.dp(24),a.dp(20));box.addView(new ProgressBar(a),new LinearLayout.LayoutParams(a.dp(26),a.dp(26)));progress=a.label(text,15,Ui.INK);progress.setPadding(a.dp(16),0,0,0);box.addView(progress,new LinearLayout.LayoutParams(0,-2,1));AlertDialog d=AppAppearance.dialog(a).setTitle("下载文件").setView(box).setPositiveButton("收起",(x,w)->{minimized=true;dismiss();}).setNeutralButton("暂停",(x,w)->pause()).setNegativeButton("取消下载",(x,w)->requestCancel()).create();d.setCanceledOnTouchOutside(false);d.setOnCancelListener(x->{minimized=true;dialog=null;});dialog=d;d.show();}progress.setText(text);}
  void retry(){if(active||awaitingPicker||retiringPartial)return;
    if(task!=null&&!task.optString("pendingDestination").isEmpty()){
      if(tasks.recovering){a.status("正在恢复下载记录，请稍后再试");return;}
      JSONObject pending=task;File source=temp;
      tasks.recoverPending(pending,()->{
        JSONObject recovered=tasks.recoveredRow(pending);
        if(recovered!=null&&task==pending){task=recovered;name=recovered.optString("name",name);tasks.release();}
        if(recovered!=null&&"saved".equals(recovered.optString("state"))&&tasks.published(recovered,Uri.parse(recovered.optString("uri")))){
          finishSaved(recovered,source,recovered.optString("name","文件"));
        }else if(task==pending||task==recovered)a.status("保存记录仍未完成，已下载的文件仍保留，请稍后再试");
      });return;
    }
    if(task!=null&&!claimTask(task)){if(!persistenceBlocked)a.status("下载记录已变化，请重新打开下载菜单");return;}minimized=true;ignoreUntil=0;cancelled=false;resumeRequested=false;if(completeFile&&temp!=null&&temp.isFile()){active=true;a.session.transferActive=true;a.session.updateBrowserActivity();choose(++ticket);return;}String id=sourceId,key=sourceKey,url=retryUrl;if(!id.isEmpty()&&!sameSource()){a.status("请返回原对话后重新下载");return;}if(a.session.offline||!a.session.networkReady){a.status("请恢复连接后继续下载");return;}if(id.isEmpty()&&url.isEmpty()){a.status("请回原网页再次点按下载");return;}if(GeckoWebView.active(a.remote)&&id.isEmpty()){a.status("请在原网页再次点按下载，临时文件会使用当前登录状态重新获取");return;}resumeRequested=true;retryUrl="";if(!id.isEmpty())open(id,key);else accept(url,agent,"",mime,-1);resumeRequested=false;}
  boolean requestAvailable(JSONObject row){return !row.optString("source").isEmpty()||!GeckoWebView.active(a.remote)&&row==task&&!retryUrl.isEmpty();}
  String continuationAction(JSONObject row){return DownloadResumePolicy.action(row,tasks.partial(row)!=null,requestAvailable(row));}
  void requestRedownload(JSONObject selected){
    if(active||awaitingPicker||retiringPartial){a.status("请先暂停或完成当前文件操作");return;}
    if(!DownloadResumePolicy.incomplete(selected)||tasks.retirementFile(selected)==null){a.status("请回原网页重新下载；已有文件和下载记录已保留");return;}
    AppAppearance.dialog(a).setTitle("重新下载？").setMessage("这个文件无法续传。将清理本任务未完成的部分，请回原网页再次点按下载。").setPositiveButton("清理旧副本并重新下载",(d,w)->{
      if(active||awaitingPicker||retiringPartial||destroyed){a.status("文件操作已变化，请重新打开下载菜单");return;}
      try{if(!loadTask(selected))return;discardForRedownload(selected);}catch(RuntimeException error){a.status("下载记录尚未写入存储，旧副本已保留，请稍后重试");}
    }).setNegativeButton("保留副本",null).show();
  }
  void discardForRedownload(JSONObject selected){
    if(active||awaitingPicker||retiringPartial||destroyed||task!=selected||!DownloadResumePolicy.RESTART.equals(continuationAction(selected)))return;
    File file=tasks.retirementFile(selected);if(file==null){a.status("请回原网页重新下载；已有文件和下载记录已保留");return;}
    final String generation=selected.optString("taskGeneration"),partial=file.getName();final long attempt=ticket;
    worker.execute(()->{
      final boolean[] retired={false},allowed={false},removed={false};String failure="";
      try{
        // This worker is queued after the paused stream. Main never waits for I/O.
        SavedFileDeletion.onMain(a.handler,()->{
          if(destroyed||active||awaitingPicker||retiringPartial||task!=selected||ticket!=attempt)return;
          if(!DownloadResumePolicy.RESTART.equals(continuationAction(selected)))return;
          retiringPartial=true;
          try{retired[0]=tasks.beginPartialRetirement(selected,generation,partial);if(retired[0]){if(temp!=null&&temp.getName().equals(partial))temp=null;receivedBytes=0;totalBytes=-1;}}
          finally{if(!retired[0])retiringPartial=false;}
        });
        if(!retired[0])return;
        SealedFileIo.lease(file,()->{
          SavedFileDeletion.onMain(a.handler,()->{allowed[0]=!destroyed&&!active&&!awaitingPicker&&retiringPartial&&task==selected&&ticket==attempt&&tasks.retiredPartialCurrent(selected,generation,partial);});
          File current=tasks.retirementFile(selected);
          if(!allowed[0]||current==null||!current.equals(file))return null;
          if(!file.delete()&&file.exists())throw new IOException("旧副本未能清理，请稍后再试；原网页仍可重新下载");removed[0]=true;return null;
        });
        if(!removed[0])return;
        SavedFileDeletion.onMain(a.handler,()->tasks.finishPartialRetirement(selected,generation,partial));
      }catch(Exception error){failure="旧副本清理尚未完成，请重新下载时重试";}
      finally{final String issue=failure;a.handler.post(()->{
        if(task!=selected||ticket!=attempt)return;retiringPartial=false;
        if(retired[0])tasks.release();
        if(!destroyed)a.status(!issue.isEmpty()?issue:removed[0]?"旧副本已清理，请回原网页重新下载":"下载记录已变化，旧副本已保留");
      });}
    });
  }
  void clearBlob(){if(!blobKey.isEmpty()&&Objects.equals(blobPage,a.remote.getUrl()))a.remote.evaluateJavascript("delete window["+JSONObject.quote(blobKey)+"]",null);blobKey="";}
  void dismiss(){if(dialog!=null){dialog.dismiss();dialog=null;}}
  void destroy(){if(active)pause();if(manager!=null)manager.dismiss();if(noticeDialog!=null)noticeDialog.dismiss();destroyed=true;tasks.release();savedActions.close();worker.shutdown();}
  void newTask(String id,String key,String url){try{JSONObject created=tasks.add(id,key,url);task=created;persistenceBlocked=false;name="文件";mime="application/octet-stream";imageLabel="";completeFile=false;temp=null;resumeValidator="";resumeAddress="";receivedBytes=0;totalBytes=-1;minimized=true;}catch(DownloadTasks.PersistenceFailure failure){persistenceBlocked=true;a.status(failure.getMessage());}}
  void updateTask(String state,String reason){if(task==null)return;DownloadTasks.put(task,"state",state,"reason",reason==null?"":reason,"name",name,"mime",mime,"received",receivedBytes,"total",totalBytes,"validator",resumeValidator,"resource",resumeAddress,"complete",completeFile&&!"cancelled".equals(state));if(temp!=null)DownloadTasks.put(task,"partial",temp.getName());}
  boolean saveTask(){
    try{tasks.save();persistenceBlocked=false;return true;}
    catch(DownloadTasks.PersistenceFailure failure){persistenceFailed(failure);return false;}
  }
  boolean claimTask(JSONObject selected){
    try{persistenceBlocked=false;return tasks.claim(selected);}
    catch(DownloadTasks.PersistenceFailure failure){persistenceBlocked=true;a.status(failure.getMessage());return false;}
  }
  void persistenceFailed(DownloadTasks.PersistenceFailure failure){
    // Invalidate the transfer before any recovery write. Storage can remain
    // unavailable: this boundary must not recursively call mark()/pause().
    persistenceBlocked=true;ignoreUntil=System.currentTimeMillis()+1500;cancelled=true;active=false;ticket++;
    a.session.transferActive=false;a.session.updateBrowserActivity();
    HttpURLConnection current=connection;connection=null;if(current!=null)try{current.disconnect();}catch(RuntimeException ignored){}
    InputStream input=nativeInput;nativeInput=null;if(input!=null)new Thread(()->{try{input.close();}catch(Exception ignored){}},"download-close").start();
    try{clearBlob();}catch(RuntimeException ignored){blobKey="";}dismiss();savingDestination=null;
    String retained=temp!=null&&temp.isFile()?"本地下载副本已保留；":"";
    String reason=task!=null&&!task.optString("pendingDestination").isEmpty()?"保存结果待确认；"+retained+"下载记录未能写入，请稍后重试。":retained+"下载记录未能写入，已暂停，请稍后重试。";
    updateTask("paused",reason);
    // One bounded attempt can retain the paused state after a transient failure.
    // Repeated failure remains unconfirmed in DownloadTasks and in the UI.
    try{tasks.save();}catch(DownloadTasks.PersistenceFailure stillUnavailable){}
    a.status(reason);
  }
  void mark(String state,String reason){if(task==null)return;updateTask(state,reason);if(saveTask())lastProgressSaved=android.os.SystemClock.elapsedRealtime();}
  void transferProgress(){
    if(task==null)return;updateTask("downloading","");long now=android.os.SystemClock.elapsedRealtime();
    // Keep live bytes local; terminal states still use mark() and synchronously retain every byte.
    if(lastProgressSaved==0||now-lastProgressSaved>=PROGRESS_SAVE_INTERVAL){if(!saveTask())return;lastProgressSaved=now;}
    showProgress(name+"\n"+DownloadTasks.progress(task));
  }
  void fail(long attempt,String reason){a.handler.post(()->{if(!valid(attempt))return;mark(reason!=null&&reason.startsWith("仅 Wi-Fi")?"paused":"failed",reason);if(persistenceBlocked)return;active=false;a.session.transferActive=false;a.session.updateBrowserActivity();dismiss();clearBlob();if(a.hub!=null&&a.hub.page==1)a.hub.refresh();});}
  void pause(){if(!active)return;ignoreUntil=System.currentTimeMillis()+1500;cancelled=true;active=false;a.session.transferActive=false;a.session.updateBrowserActivity();ticket++;if(connection!=null)connection.disconnect();InputStream nativeStream=nativeInput;nativeInput=null;if(nativeStream!=null)new Thread(()->{try{nativeStream.close();}catch(IOException ignored){}},"download-close").start();clearBlob();dismiss();savingDestination=null;mark("paused",DownloadResumePolicy.paused(task,temp!=null&&temp.isFile(),requestAvailable(task)));}
  void requestCancel(){if(destroyed||retiringPartial||task==null||"saved".equals(task.optString("state")))return;JSONObject chosen=task;AppAppearance.dialog(a).setTitle("取消下载？").setMessage(DownloadResumePolicy.RESUME.equals(continuationAction(chosen))?"会清理已下载的部分。只想稍后继续，可以暂停下载。":completeFile?"会清理尚未保存的完整文件。也可保留，稍后继续保存。":"会清理本任务未完成的部分；重新下载需要回原网页再次点按。").setPositiveButton("取消并清理",(d,w)->{if(task==chosen&&!"saved".equals(chosen.optString("state")))cancel();}).setNeutralButton("暂停下载",(d,w)->{if(task==chosen)pause();}).setNegativeButton("保留下载",null).show();}
  void cancel(){if(retiringPartial)return;pause();ignoreUntil=System.currentTimeMillis()+3000;mark("cancelled","你已取消下载");if(persistenceBlocked)return;completeFile=false;retryUrl="";File file=temp;temp=null;if(file!=null&&!worker.isShutdown())worker.execute(()->file.delete());}
  boolean loadTask(JSONObject row){if(retiringPartial){a.status("正在清理旧的未完成副本，请稍后再试");return false;}if(!claimTask(row)){if(!persistenceBlocked)a.status("下载记录已变化，请重新打开下载菜单");return false;}task=row;name=row.optString("name","文件");mime=row.optString("mime","application/octet-stream");sourceId=row.optString("source");sourceKey=row.optString("key");sourceUrl=row.optString("conversation");retryUrl="";temp=tasks.partial(row);resumeValidator=row.optString("validator");resumeAddress=row.optString("resource");completeFile=row.optBoolean("complete")&&temp!=null;receivedBytes=temp==null?0:temp.length();totalBytes=row.optLong("total",-1);imageLabel="";return true;}
  void history(){if(manager!=null&&manager.isShowing())return;LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));ListView list=new ListView(a);box.addView(list,new LinearLayout.LayoutParams(-1,a.dp(360)));List<JSONObject> rows=new ArrayList<>();JSONArray known=DownloadLibrary.get(a).prune(tasks.rows);for(int i=0;i<known.length();i++)rows.add(known.optJSONObject(i));JSONArray old=J.parse(a.prefs.getString("downloadHistory","{}")).optJSONArray("files");if(old!=null)old=DownloadLibrary.get(a).prune(old);if(old!=null)for(int i=0;i<old.length();i++){JSONObject r=old.optJSONObject(i);boolean duplicate=false;for(JSONObject item:rows)if(item.optString("uri").equals(r.optString("uri")))duplicate=true;if(!duplicate){JSONObject copy=J.parse(r.toString());DownloadTasks.put(copy,"state","saved");rows.add(copy);}}ArrayAdapter<String> adapter=new ArrayAdapter<>(a,android.R.layout.simple_list_item_1,new ArrayList<>());list.setAdapter(adapter);Runnable refresh=new Runnable(){public void run(){if(manager==null||!manager.isShowing())return;JSONArray live=new JSONArray();for(JSONObject row:rows)live.put(row);live=DownloadLibrary.get(a).prune(live);rows.clear();for(int i=0;i<live.length();i++)rows.add(live.optJSONObject(i));adapter.clear();for(JSONObject r:rows){String state=r.optString("state");adapter.add(r.optString("name")+"\n"+DownloadTasks.label(state)+(state.equals("saved")?"":" · "+DownloadTasks.progress(r))+(r.optString("reason").isEmpty()?"":"\n"+r.optString("reason")));}if(rows.isEmpty())adapter.add("还没有下载记录");adapter.notifyDataSetChanged();a.handler.postDelayed(this,700);}};list.setOnItemClickListener((p,v,n,id)->{if(n<rows.size())taskActions(rows.get(n));});manager=AppAppearance.dialog(a).setTitle("下载管理").setView(box).setNegativeButton("关闭",null).create();manager.show();refresh.run();}
  void taskActions(JSONObject r){if(retiringPartial){a.status("正在清理旧的未完成副本，请稍后再试");return;}if(tasks.recovering&&!r.optString("pendingDestination").isEmpty()){a.status("正在恢复下载记录，请稍后再试");return;}if(r.optString("state").equals("saved")){savedActions.show(r);return;}boolean current=task!=null&&task.optString("id").equals(r.optString("id"));if(active&&current){AppAppearance.dialog(a).setTitle(r.optString("name")).setItems(new String[]{"查看进度","暂停","取消下载"},(d,n)->{if(n==0){minimized=false;showProgress(DownloadTasks.progress(r));}else if(n==1)pause();else requestCancel();}).show();return;}LinearLayout detail=new LinearLayout(a);detail.setOrientation(LinearLayout.VERTICAL);TextView reason=a.label(r.optString("reason")+"\n"+DownloadTasks.progress(r),14,Ui.MUTED);reason.setPadding(a.dp(20),a.dp(10),a.dp(20),a.dp(10));detail.addView(reason);if(!r.optString("pendingDestination").isEmpty()){Button inspect=new Button(a);inspect.setText("查看待确认文件");detail.addView(inspect);inspect.setOnClickListener(v->openSaved(Uri.parse(r.optString("pendingDestination")),r.optString("mime","application/octet-stream"),r.optString("pendingName",r.optString("name","文件")),false));}if(r.optString("pendingDestination").isEmpty()&&r.optBoolean("complete")&&tasks.partial(r)!=null){Button save=new Button(a);save.setText("另存为已下载文件");detail.addView(save);save.setOnClickListener(v->{if(active||awaitingPicker){a.status("请先完成当前下载");return;}if(!loadTask(r))return;cancelled=false;active=true;a.session.transferActive=true;a.session.updateBrowserActivity();chooseManually(++ticket);});}AppAppearance.dialog(a).setTitle(r.optString("name")).setView(detail).setPositiveButton(continuationAction(r),(d,w)->{if(DownloadResumePolicy.RESTART.equals(continuationAction(r))){requestRedownload(r);return;}if(active){a.status("请先暂停或完成当前下载");return;}String liveUrl=current?retryUrl:"";if(!loadTask(r))return;retryUrl=liveUrl;if(!completeFile&&sourceId.isEmpty()&&retryUrl.isEmpty()){a.status("请回原网页再次点按下载，临时链接不会长期保存");return;}if(!completeFile&&!sourceId.isEmpty()&&!sameSource()){a.status("请返回该文件所在对话，再从下载管理继续");return;}retry();}).setNeutralButton("取消并清理",(d,w)->{if(active){a.status("请先暂停当前下载");return;}if(!loadTask(r))return;requestCancel();}).setNegativeButton("关闭",null).show();}

}
