package local.pocketchat;

import java.io.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
import java.security.MessageDigest;
import org.json.JSONObject;
import org.json.JSONTokener;

/** Two owned TLS keys only, before the sole native runtime can revive a profile.
 * The existing closed-route CPU startup config is preserved byte for byte. */
final class GeckoTlsProfile {
  static final String MIN="security.tls.version.min",MAX="security.tls.version.max";
  static final int MAX_BYTES=4*1024*1024;
  private static final Pattern OWNED=Pattern.compile("^\\s*user_pref\\(\"security\\.tls\\.version\\.(?:min|max)\",\\s*[0-9]{1,9}\\);\\s*$");
  private GeckoTlsProfile(){}
  static final class Reconciliation {
    final int beforeBytes,afterBytes;final String beforeNonTlsSha256,afterNonTlsSha256;
    Reconciliation(byte[] before,byte[] plannedNonTls,byte[] committed)throws Exception{
      if(!Arrays.equals(plannedNonTls,committed))throw new IOException("TLS profile changed after write");
      beforeBytes=before.length;afterBytes=committed.length;beforeNonTlsSha256=sha(plannedNonTls);afterNonTlsSha256=sha(committed);
    }
  }
  static final class Preparation {
    final Reconciliation profile;final String mode,configBeforeSha256,configAfterSha256;
    Preparation(Reconciliation profile,GeckoTlsSpec spec,byte[] before,byte[] committed)throws Exception{
      byte[] expected=spec.isDefault()?before:(decode(before)+"  "+MIN+": 4\n  "+MAX+": 4\n").getBytes(StandardCharsets.UTF_8);
      if(!Arrays.equals(expected,committed))throw new IOException("TLS config changed after write");
      this.profile=profile;mode=spec.mode;configBeforeSha256=sha(before);configAfterSha256=sha(committed);
    }
    JSONObject evidence(){return J.obj("schema",1,"status","verified","scope","offline-two-owned-tls-preferences","mode",mode,
      "profileBytesBefore",profile.beforeBytes,"profileBytesAfter",profile.afterBytes,"removedOwnedBytes",profile.beforeBytes-profile.afterBytes,
      "nonTlsPrefsBeforeSha256",profile.beforeNonTlsSha256,"nonTlsPrefsAfterSha256",profile.afterNonTlsSha256,"nonTlsPrefsBytePreserved",profile.beforeNonTlsSha256.equals(profile.afterNonTlsSha256),
      "closedRouteConfigPrefixPreserved",true,"configBeforeSha256",configBeforeSha256,"configAfterSha256",configAfterSha256);}
  }
  private static String sha(byte[] raw)throws Exception{StringBuilder value=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(raw))value.append(String.format(Locale.ROOT,"%02x",b&255));return value.toString();}
  static Preparation prepare(File root,File profile,GeckoTlsSpec spec)throws Exception{
    Objects.requireNonNull(spec);Reconciliation reconciled=reconcile(root,profile);
    File config=new File(root,"gecko-browser.yaml");byte[] before=read(config);
    if(before.length>65536)throw new IOException("TLS config bound");String base=decode(before);
    if(!base.startsWith("prefs:\n")||!base.endsWith("\n")||!base.contains("  network.proxy.socks: '127.0.0.1'\n")||!base.contains("  network.proxy.socks_port: 9\n")||base.contains(MIN)||base.contains(MAX))throw new IOException("TLS closed config changed");
    if(spec.isDefault())return new Preparation(reconciled,spec,before,read(config));
    byte[] after=(base+"  "+MIN+": 4\n  "+MAX+": 4\n").getBytes(StandardCharsets.UTF_8);
    File temporary=new File(root,"pocket-tls-config.tmp");if(Files.exists(temporary.toPath(),LinkOption.NOFOLLOW_LINKS))throw new IOException("TLS config temporary exists");
    boolean moved=false;try{
      try(FileOutputStream stream=new FileOutputStream(temporary)){stream.write(after);stream.getFD().sync();}
      if(!Arrays.equals(before,read(config)))throw new IOException("TLS config changed");
      Files.move(temporary.toPath(),config.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);moved=true;
    }finally{if(!moved)Files.deleteIfExists(temporary.toPath());}
    return new Preparation(reconciled,spec,before,read(config));
  }
  static Reconciliation reconcile(File root,File profile)throws Exception{
    File base=root.getCanonicalFile();if(Files.isSymbolicLink(root.toPath())||!root.getAbsoluteFile().equals(base))throw new IOException("TLS profile root link");
    File expected=new File(base,"gecko-browser");if(!profile.getAbsoluteFile().equals(expected)||Files.isSymbolicLink(profile.toPath()))throw new IOException("TLS profile path");
    if(!profile.isDirectory()&&!profile.mkdir())throw new IOException("TLS profile directory");
    if(!profile.getCanonicalFile().equals(expected))throw new IOException("TLS profile link");
    File user=new File(profile,"user.js"),prefs=new File(profile,"prefs.js");
    validateUser(read(user));byte[] before=read(prefs),after=withoutTls(before);
    if(java.util.Arrays.equals(before,after))return new Reconciliation(before,after,read(prefs));
    File temporary=new File(profile,"pocket-tls-prefs.tmp");
    if(Files.exists(temporary.toPath(),LinkOption.NOFOLLOW_LINKS))throw new IOException("TLS profile temporary exists");
    boolean moved=false;try{
      try(FileOutputStream stream=new FileOutputStream(temporary)){stream.write(after);stream.getFD().sync();}
      // Recheck after the bounded parse; app data is private and only the cold
      // environment parent owns this profile. A changed file is never replaced.
      if(!java.util.Arrays.equals(before,read(prefs)))throw new IOException("TLS profile changed");
      Files.move(temporary.toPath(),prefs.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);moved=true;
    }finally{if(!moved)Files.deleteIfExists(temporary.toPath());}
    return new Reconciliation(before,after,read(prefs));
  }
  private static byte[] read(File file)throws IOException{
    if(Files.isSymbolicLink(file.toPath()))throw new IOException("TLS profile preference link");
    if(!Files.exists(file.toPath(),LinkOption.NOFOLLOW_LINKS))return new byte[0];
    if(!file.isFile()||file.length()>MAX_BYTES)throw new IOException("TLS profile preference bound");
    try(InputStream input=new FileInputStream(file);ByteArrayOutputStream output=new ByteArrayOutputStream()){
      byte[] buffer=new byte[8192];int count;while((count=input.read(buffer))!=-1){if(output.size()+count>MAX_BYTES)throw new IOException("TLS profile preference bound");output.write(buffer,0,count);}return output.toByteArray();
    }
  }
  static byte[] withoutTls(byte[] source)throws Exception{
    String text=decode(source);StringBuilder result=new StringBuilder(text.length());int offset=0;Set<String> matched=new HashSet<>();
    while(offset<text.length()){
      int end=text.indexOf('\n',offset);if(end<0)end=text.length();else end++;
      String bytes=text.substring(offset,end);int content=bytes.length();while(content>0&&(bytes.charAt(content-1)=='\r'||bytes.charAt(content-1)=='\n'))content--;
      String line=bytes.substring(0,content),name=key(line),trimmed=line.trim();
      if(name==null&&!trimmed.isEmpty()&&!trimmed.startsWith("//"))throw new IOException("TLS profile preference ambiguous");
      if(MIN.equals(name)||MAX.equals(name)){if(!OWNED.matcher(line).matches()||!matched.add(name))throw new IOException("TLS profile preference ambiguous");}
      else{if(line.contains(MIN)||line.contains(MAX))throw new IOException("TLS profile preference ambiguous");result.append(bytes);}offset=end;
    }return result.toString().getBytes(StandardCharsets.UTF_8);
  }
  private static void validateUser(byte[] bytes)throws Exception{
    String text=decode(bytes);for(String line:text.split("\\n",-1)){
      String trimmed=line.trim();if(trimmed.isEmpty()||trimmed.startsWith("//"))continue;
      String name=key(line);if(name==null||MIN.equals(name)||MAX.equals(name)||line.contains(MIN)||line.contains(MAX))throw new IOException("TLS user.js override unsupported");
    }
  }
  private static String key(String line)throws Exception{
    // Linear literal scanner, so even a bounded multi-megabyte string cannot
    // overflow a recursive regex. Only one literal preference call is allowed.
    String text=line.trim();int open=text.indexOf('(');if(open<0)return null;
    String function=text.substring(0,open).trim();if(!function.equals("user_pref")&&!function.equals("pref")&&!function.equals("sticky_pref"))return null;
    int start=space(text,open+1),end=quoted(text,start);if(end<0)return null;
    Object key=new JSONTokener(text.substring(start,end)).nextValue();int cursor=space(text,end);
    if(cursor>=text.length()||text.charAt(cursor++)!=',')return null;cursor=space(text,cursor);
    if(cursor>=text.length())return null;
    if(text.charAt(cursor)=='"'){cursor=quoted(text,cursor);if(cursor<0)return null;}
    else{
      int valueStart=cursor;while(cursor<text.length()&&text.charAt(cursor)!=')'&&!Character.isWhitespace(text.charAt(cursor)))cursor++;
      String literal=text.substring(valueStart,cursor);if(!literal.equals("true")&&!literal.equals("false")&&!literal.matches("-?[0-9]+"))return null;
    }
    cursor=space(text,cursor);if(cursor>=text.length()||text.charAt(cursor++)!=')')return null;
    cursor=space(text,cursor);if(cursor>=text.length()||text.charAt(cursor++)!=';'||space(text,cursor)!=text.length())return null;
    return key instanceof String?(String)key:null;
  }
  private static int space(String text,int offset){while(offset<text.length()&&Character.isWhitespace(text.charAt(offset)))offset++;return offset;}
  private static int quoted(String text,int start){if(start>=text.length()||text.charAt(start)!='"')return -1;for(int i=start+1;i<text.length();i++){char value=text.charAt(i);if(value=='"')return i+1;if(value=='\\'&&++i>=text.length())return -1;}return -1;}
  private static String decode(byte[] bytes)throws CharacterCodingException{
    if(bytes.length>MAX_BYTES)throw new CharacterCodingException();return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)).toString();
  }
}
