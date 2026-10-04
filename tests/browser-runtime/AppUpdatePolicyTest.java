package local.pocketchat;

import java.io.*;
import java.nio.file.Files;

/** Real streamed bytes, including interruption and tampering; no network or Android doubles. */
public class AppUpdatePolicyTest {
  static int checks;
  static void ok(boolean value){if(!value)throw new AssertionError();checks++;}
  static void invalid(String version,long code,long bytes,String hash,String signer,String url,String pkg,String abi,int sdk)throws Exception {try{AppUpdatePolicy.validate(version,code,bytes,hash,signer,url,pkg,abi,sdk);throw new AssertionError("Accepted invalid release");}catch(IOException expected){checks++;}}
  public static void main(String[] args)throws Exception {
    String v="1.5.12",url=AppUpdatePolicy.asset(v),hash="a".repeat(64),signer=AppUpdatePolicy.SIGNER;
    AppUpdatePolicy.validate(v,38,120000000,hash,signer,url,"local.pocketchat","arm64-v8a",26);checks++;
    invalid(v,0,10,hash,signer,url,"local.pocketchat","arm64-v8a",26);
    invalid(v,38,AppUpdatePolicy.MAX_APK+1,hash,signer,url,"local.pocketchat","arm64-v8a",26);
    invalid("../x",38,10,hash,signer,url,"local.pocketchat","arm64-v8a",26);
    invalid(v,38,10,"z".repeat(64),signer,url,"local.pocketchat","arm64-v8a",26);
    invalid(v,38,10,hash,"b".repeat(64),url,"local.pocketchat","arm64-v8a",26);
    invalid(v,38,10,hash,signer,url.replace("https:","http:"),"local.pocketchat","arm64-v8a",26);
    invalid(v,38,10,hash,signer,url+"?redirect=https://evil.invalid","local.pocketchat","arm64-v8a",26);
    invalid(v,38,10,hash,signer,url,"other.app","arm64-v8a",26);
    invalid(v,38,10,hash,signer,url,"local.pocketchat","x86_64",26);
    ok(AppUpdatePolicy.feedRedirect(AppUpdatePolicy.FEED));ok(!AppUpdatePolicy.feedRedirect(AppUpdatePolicy.FEED.replace("https:","http:")));
    ok(!AppUpdatePolicy.feedRedirect(AppUpdatePolicy.FEED.replace("raw.githubusercontent.com","raw.githubusercontent.com.evil.invalid")));
    ok(!AppUpdatePolicy.feedRedirect(AppUpdatePolicy.FEED.replace("raw.githubusercontent.com","evil@raw.githubusercontent.com")));
    ok(AppUpdatePolicy.due(200,300,100));ok(!AppUpdatePolicy.due(200,100,101));ok(AppUpdatePolicy.due(201,100,101));
    byte[] bytes="synthetic verified APK bytes".getBytes(java.nio.charset.StandardCharsets.UTF_8);File file=Files.createTempFile("app-update-test",".apk").toFile();
    try{
      AppUpdatePolicy.copyVerified(new ByteArrayInputStream(bytes),file,bytes.length,AppUpdatePolicy.hash(bytes),()->false);ok(java.util.Arrays.equals(bytes,Files.readAllBytes(file.toPath())));
      for(int mode=0;mode<5;mode++){
        final int selected=mode;InputStream in=mode==4?new InputStream(){public int read()throws IOException{throw new IOException("interrupted");}}:new ByteArrayInputStream(mode==1?java.util.Arrays.copyOf(bytes,bytes.length-1):bytes);
        try{AppUpdatePolicy.copyVerified(in,file,mode==2?bytes.length-1:bytes.length,mode==0?hash:AppUpdatePolicy.hash(bytes),()->selected==3);throw new AssertionError("Corrupt/cancelled/interrupted file retained");}catch(IOException expected){ok(!file.exists());}
      }
    }finally{file.delete();}
    System.out.println("{\"checks\":"+checks+",\"status\":\"passed\"}");
  }
}
