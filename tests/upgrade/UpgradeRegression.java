package local.pocketchat.upgradeqa;

import android.app.Instrumentation;
import android.content.Context;
import android.database.sqlite.SQLiteOpenHelper;
import android.os.Bundle;
import android.webkit.CookieManager;
import org.json.*;
import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Same-certificate sidecar: exercise the installed APK before and after an actual update. */
public final class UpgradeRegression extends Instrumentation {
  Bundle args;
  final JSONArray checks=new JSONArray();
  Context root;
  @Override public void onCreate(Bundle arguments){super.onCreate(arguments);args=arguments;start();}
  @Override public void onStart(){
    Bundle result=new Bundle();String error="";
    try{
      root=getTargetContext();
      if(!"true".equals(args.getString("allowFixtureWrites")))throw new IllegalStateException("Explicit fixture mode required");
      String hardware=android.os.Build.HARDWARE;
      if(!hardware.equals("ranchu")&&!hardware.equals("goldfish"))throw new IllegalStateException("This fixture is restricted to the disposable emulator");
      if("seed".equals(args.getString("phase")))seed();else verify();
    }catch(Throwable failure){error=failure.toString();check("Upgrade fixture completed without exception",false);}
    try{
      JSONObject report=new JSONObject().put("phase",args.getString("phase")).put("baseline",args.getString("baseline")).put("checks",checks).put("error",error);
      File reportFile=new File(root.getFilesDir(),"upgrade-"+args.getString("phase")+"-results.json");
      try(FileOutputStream out=new FileOutputStream(reportFile)){out.write(report.toString(2).getBytes(StandardCharsets.UTF_8));}
      boolean passed=checks.length()>0&&error.isEmpty();for(int i=0;i<checks.length();i++)passed&=checks.getJSONObject(i).getBoolean("pass");
      result.putBoolean("passed",passed);result.putString("report",reportFile.getAbsolutePath());result.putString("results",report.toString());
      finish(passed?-1:0,result);
    }catch(Exception failure){result.putString("error",failure.getClass().getSimpleName());finish(0,result);}
  }
  void check(String name,boolean pass){try{checks.put(new JSONObject().put("name",name).put("pass",pass));}catch(Exception failure){throw new IllegalStateException(failure);}}
  Class<?> type(String name)throws Exception{return Class.forName("local.pocketchat."+name,true,root.getClassLoader());}
  Object call(Object target,String method,Class<?>[] parameters,Object... values)throws Exception{
    Class<?> owner=target instanceof Class?(Class<?>)target:target.getClass();Method m=owner.getDeclaredMethod(method,parameters);m.setAccessible(true);return m.invoke(target instanceof Class?null:target,values);
  }
  Object create(String name,Context context)throws Exception{Constructor<?> c=type(name).getDeclaredConstructor(Context.class);c.setAccessible(true);return c.newInstance(context);}
  Context profile(int id)throws Exception{return (Context)call(type("Profiles"),"context",new Class<?>[]{Context.class,int.class},root,id);}
  Object catalog()throws Exception{return call(type("ProfileCatalog"),"get",new Class<?>[]{Context.class},root);}
  String url(int id){return "https://chatgpt.com/c/upgrade-fixture-"+id;}
  void seed()throws Exception{
    Object catalog=catalog();JSONArray savedUris=new JSONArray();
    for(int id=0;id<2;id++){
      call(catalog,"created",new Class<?>[]{int.class},id);
      call(catalog,"rename",new Class<?>[]{int.class,String.class},id,"升级保留 "+id);
      call(catalog,"favorite",new Class<?>[]{int.class,boolean.class},id,id==0);
      call(catalog,"draft",new Class<?>[]{int.class,JSONObject.class},id,new JSONObject().put("name","升级配置草稿 "+id));
      Context context=profile(id);
      context.getSharedPreferences("chat",0).edit().putString("conversation",url(id)).putString("upgrade-marker","preferences-"+id).putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).putString("proxy","http://fixture.invalid:8080").commit();
      Object store=create("ConversationStore",context);
      call(store,"draft",new Class<?>[]{String.class,String.class},url(id),"升级会话草稿 "+id+"\n  保留空格  ");
      call(store,"saveMessages",new Class<?>[]{String.class,JSONArray.class},url(id),new JSONArray().put(new JSONObject().put("id","fixture-"+id).put("role","user").put("text","升级会话消息 "+id)));
      ((SQLiteOpenHelper)store).close();
      call(create("SecretStore",context),"put",new Class<?>[]{String.class,byte[].class},"upgrade-proof",("encrypted-network-"+id).getBytes(StandardCharsets.UTF_8));
      Object destination=call(type("DefaultDownloads"),"local",new Class<?>[]{Context.class,String.class},context,"upgrade-file-proof.txt");
      try(OutputStream out=(OutputStream)call(destination,"output",new Class<?>[]{})){out.write(("saved-download-"+id).getBytes(StandardCharsets.UTF_8));}
      call(destination,"publish",new Class<?>[]{});
      Field uri=destination.getClass().getDeclaredField("uri");uri.setAccessible(true);String savedUri=uri.get(destination).toString();savedUris.put(savedUri);
      Object library=call(type("DownloadLibrary"),"get",new Class<?>[]{Context.class},root);
      call(library,"add",new Class<?>[]{Context.class,JSONObject.class},context,new JSONObject().put("id","upgrade-saved-"+id).put("uri",savedUri).put("name","upgrade-file-proof.txt").put("mime","text/plain").put("state","saved"));
    }
    int schema=((SQLiteOpenHelper)catalog).getReadableDatabase().getVersion();
    if(schema>=4)for(int id=0;id<2;id++)call(catalog,"details",new Class<?>[]{int.class,String.class,String.class},id,"升级分组 "+id,"升级备注 "+id);
    call(type("AppSettings"),"defaultSlot",new Class<?>[]{Context.class,int.class},root,1);
    call(type("AppSettings"),"put",new Class<?>[]{Context.class,String.class,String.class},root,"brandSeen","true");
    call(type("AppSettings"),"put",new Class<?>[]{Context.class,String.class,String.class},root,"startupDirect","false");
    CountDownLatch stored=new CountDownLatch(1);
    runOnMainSync(()->CookieManager.getInstance().setCookie("https://chatgpt.com/","upgrade_fixture=retained; Path=/; Secure; HttpOnly",ok->stored.countDown()));
    if(!stored.await(90,TimeUnit.SECONDS))throw new IllegalStateException("Cookie write timed out");
    runOnMainSync(()->CookieManager.getInstance().flush());
    JSONObject expected=new JSONObject().put("schema",schema).put("uid",root.getApplicationInfo().uid).put("package",root.getPackageName()).put("downloadUris",savedUris);
    try(FileOutputStream out=new FileOutputStream(new File(root.getFilesDir(),"upgrade-expected.json"))){out.write(expected.toString().getBytes(StandardCharsets.UTF_8));}
    check("Baseline fixture stores a real WebView cookie",String.valueOf(CookieManager.getInstance().getCookie("https://chatgpt.com/")).contains("upgrade_fixture=retained"));
    check("Baseline has the expected installed package",root.getPackageName().equals("local.pocketchat"));
  }
  void verify()throws Exception{
    JSONObject expected=new JSONObject(new String(java.nio.file.Files.readAllBytes(new File(root.getFilesDir(),"upgrade-expected.json").toPath()),StandardCharsets.UTF_8));
    check("Update keeps the same Android UID",root.getApplicationInfo().uid==expected.getInt("uid"));
    check("Update keeps the production package",root.getPackageName().equals(expected.getString("package")));
    check("Update installs the newer version code",root.getPackageManager().getPackageInfo(root.getPackageName(),0).versionCode==27);
    Object catalog=catalog();
    check("Updated catalog opens at schema v4",((SQLiteOpenHelper)catalog).getReadableDatabase().getVersion()==4);
    for(int id=0;id<2;id++){
      JSONObject row=(JSONObject)call(catalog,"item",new Class<?>[]{int.class},id);
      check("Environment "+id+" retains creation, name, and favorite",row.getBoolean("created")&&row.getString("name").equals("升级保留 "+id)&&row.getBoolean("favorite")== (id==0));
      check("Environment "+id+" retains editor draft",row.getString("draft").contains("升级配置草稿 "+id));
      check("Environment "+id+" migrates or preserves group and notes",row.getString("group").equals(expected.getInt("schema")>=4?"升级分组 "+id:"")&&row.getString("notes").equals(expected.getInt("schema")>=4?"升级备注 "+id:""));
      Context context=profile(id);
      check("Environment "+id+" retains conversation and network preferences",context.getSharedPreferences("chat",0).getString("conversation","").equals(url(id))&&context.getSharedPreferences("chat",0).getString("proxy","").equals("http://fixture.invalid:8080")&&context.getSharedPreferences("chat",0).getString("upgrade-marker","").equals("preferences-"+id));
      Object store=create("ConversationStore",context);
      check("Environment "+id+" retains exact multiline conversation draft",call(store,"draft",new Class<?>[]{String.class},url(id)).equals("升级会话草稿 "+id+"\n  保留空格  "));
      check("Environment "+id+" retains cached conversation messages",((JSONArray)call(store,"messages",new Class<?>[]{String.class},url(id))).getJSONObject(0).getString("text").equals("升级会话消息 "+id));
      ((SQLiteOpenHelper)store).close();
      byte[] plaintext=(byte[])call(create("SecretStore",context),"get",new Class<?>[]{String.class},"upgrade-proof");
      check("Environment "+id+" still decrypts its existing sealed record",new String(plaintext,StandardCharsets.UTF_8).equals("encrypted-network-"+id));
      String savedUri=expected.getJSONArray("downloadUris").getString(id);
      try(InputStream in=root.getContentResolver().openInputStream(android.net.Uri.parse(savedUri))){
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[1024];int read;
        while((read=in.read(buffer))!=-1)bytes.write(buffer,0,read);
        check("Environment "+id+" opens preserved saved file through production provider",new String(bytes.toByteArray(),StandardCharsets.UTF_8).equals("saved-download-"+id));
      }
      Object library=call(type("DownloadLibrary"),"get",new Class<?>[]{Context.class},root);
      JSONArray files=(JSONArray)call(library,"list",new Class<?>[]{});boolean indexed=false;
      for(int index=0;index<files.length();index++){JSONObject file=files.getJSONObject(index);if(file.optInt("slot")==id&&file.optString("uri").equals(savedUri))indexed=true;}
      check("Environment "+id+" preserves the saved-file index",indexed);
    }
    check("Update retains chosen startup environment",(Integer)call(type("AppSettings"),"defaultSlot",new Class<?>[]{Context.class},root)==1);
    check("Update retains the chosen native-manager startup mode",!(Boolean)call(type("AppSettings"),"bool",new Class<?>[]{Context.class,String.class,boolean.class},root,"startupDirect",true));
    final String[] cookie={null};runOnMainSync(()->cookie[0]=CookieManager.getInstance().getCookie("https://chatgpt.com/"));
    check("Update retains the real WebView cookie without recreating login storage",String.valueOf(cookie[0]).contains("upgrade_fixture=retained"));
  }
}
