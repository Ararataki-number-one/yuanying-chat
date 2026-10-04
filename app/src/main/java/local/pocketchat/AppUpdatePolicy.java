package local.pocketchat;

import java.io.*;
import java.net.URI;
import java.security.MessageDigest;

/** The update channel accepts only the original production package and release assets. */
final class AppUpdatePolicy {
  static final String REPO="Ararataki-number-one/yuanying-chat";
  static final String FEED="https://raw.githubusercontent.com/"+REPO+"/app-updates/latest.json";
  static final String SIGNER="f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434";
  static final long MAX_APK=512L*1024*1024, DAY=24L*60*60*1000;
  static boolean due(long now,long last,long interval){return last<=0||now<last||now-last>=interval;}
  static String asset(String version){return "https://github.com/"+REPO+"/releases/download/v"+version+"-gecko/PocketChat-"+version+"-gecko-arm64.apk";}
  static void validate(String version,long code,long bytes,String sha,String signer,String url,String pkg,String abi,int minSdk)throws IOException {
    if(version==null||!version.matches("[0-9]+[.][0-9]+[.][0-9]+")||code<=0||code>Integer.MAX_VALUE||bytes<=0||bytes>MAX_APK||sha==null||!sha.matches("[a-f0-9]{64}")||!SIGNER.equals(signer)||!asset(version).equals(url)||!"local.pocketchat".equals(pkg)||!"arm64-v8a".equals(abi)||minSdk<26||minSdk>100)throw new IOException("更新信息不完整，请稍后重新检查");
  }
  static boolean feedRedirect(String url){try{URI u=new URI(url);return "https".equals(u.getScheme())&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443)&&"raw.githubusercontent.com".equals(u.getHost())&&("/"+REPO+"/app-updates/latest.json").equals(u.getPath());}catch(Exception e){return false;}}
  static String hash(byte[] data){try{return hex(MessageDigest.getInstance("SHA-256").digest(data));}catch(Exception e){throw new IllegalStateException(e);}}
  static String hex(byte[] data){StringBuilder out=new StringBuilder();for(byte b:data)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();}
  static void copyVerified(InputStream in,File target,long bytes,String hash,java.util.function.BooleanSupplier cancelled)throws IOException {
    boolean ok=false;long count=0;
    try(FileOutputStream out=new FileOutputStream(target)){
      MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[65536];int read;
      while((read=in.read(buffer))!=-1){if(cancelled.getAsBoolean())throw new IOException("下载已取消");count+=read;if(count>bytes)throw new IOException("更新文件大小不符，请重新下载");out.write(buffer,0,read);digest.update(buffer,0,read);}
      out.getFD().sync();if(cancelled.getAsBoolean())throw new IOException("下载已取消");if(count!=bytes||!hex(digest.digest()).equals(hash))throw new IOException("更新文件不完整，请重新下载");ok=true;
    }catch(java.security.NoSuchAlgorithmException e){throw new IOException(e);}finally{if(!ok)target.delete();}
  }
}
