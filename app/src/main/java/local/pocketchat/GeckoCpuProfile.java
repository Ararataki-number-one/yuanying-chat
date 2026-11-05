package local.pocketchat;

import java.io.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.util.regex.*;
import org.json.JSONTokener;

/** Offline, CPU-only reconciliation. Never call after GeckoRuntime.create.
 * YAML sets DEFAULT prefs, so an older persisted USER value must be removed
 * before Gecko can revive a profile's ServiceWorkers. All other bytes survive. */
final class GeckoCpuProfile {
  static final String PREF="dom.maxHardwareConcurrency";
  static final int MAX_BYTES=4*1024*1024;
  private static final Pattern OWNED=Pattern.compile("^\\s*user_pref\\(\"dom\\.maxHardwareConcurrency\",\\s*[0-9]{1,9}\\);\\s*$");
  private GeckoCpuProfile(){}
  static void prepare(File root,File profile,GeckoCpuSpec spec)throws Exception{
    reconcile(root,profile);
    File config=new File(root,"gecko-browser.yaml");if(Files.isSymbolicLink(config.toPath()))throw new IOException("CPU config link");
    String yaml="prefs:\n  network.proxy.type: 1\n  network.proxy.socks: '127.0.0.1'\n  network.proxy.socks_port: 9\n"
      +"  network.proxy.socks_version: 5\n  network.proxy.socks_remote_dns: true\n  network.proxy.no_proxies_on: ''\n"
      +"  network.proxy.allow_hijacking_localhost: true\n  network.trr.mode: 5\n  network.dns.disablePrefetch: true\n"
      +"  network.prefetch-next: false\n  network.http.speculative-parallel-limit: 0\n  media.peerconnection.enabled: false\n"
      +(spec.isAutomatic()?"":"  "+PREF+": "+spec.cap+"\n");
    // This complete closed-route config is prepared on environmentIo, including
    // default mode. Runtime creation performs no newly-added disk work on UI.
    File temporary=new File(root,"pocket-cpu-config.tmp");
    if(Files.exists(temporary.toPath(),LinkOption.NOFOLLOW_LINKS))throw new IOException("CPU config temporary exists");
    boolean moved=false;try{
      try(FileOutputStream output=new FileOutputStream(temporary)){output.write(yaml.getBytes(StandardCharsets.UTF_8));output.getFD().sync();}
      Files.move(temporary.toPath(),config.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);moved=true;
    }finally{if(!moved)Files.deleteIfExists(temporary.toPath());}
  }
  static void reconcile(File root,File profile)throws Exception{
    File base=root.getCanonicalFile();if(Files.isSymbolicLink(root.toPath())||!root.getAbsoluteFile().equals(base))throw new IOException("CPU profile root link");
    File expected=new File(base,"gecko-browser");if(!profile.getAbsoluteFile().equals(expected)||Files.isSymbolicLink(profile.toPath()))throw new IOException("CPU profile path");
    if(!profile.isDirectory()&&!profile.mkdir())throw new IOException("CPU profile directory");
    if(!profile.getCanonicalFile().equals(expected))throw new IOException("CPU profile link");
    File user=new File(profile,"user.js"),prefs=new File(profile,"prefs.js");
    validateUser(read(user));byte[] before=read(prefs),after=withoutCpu(before);
    if(java.util.Arrays.equals(before,after))return;
    File temporary=new File(profile,"pocket-cpu-prefs.tmp");
    if(Files.exists(temporary.toPath(),LinkOption.NOFOLLOW_LINKS))throw new IOException("CPU profile temporary exists");
    boolean moved=false;try{
      try(FileOutputStream stream=new FileOutputStream(temporary)){stream.write(after);stream.getFD().sync();}
      // Recheck after the bounded parse; app data is private and only the cold
      // environment parent owns this profile. A changed file is never replaced.
      if(!java.util.Arrays.equals(before,read(prefs)))throw new IOException("CPU profile changed");
      Files.move(temporary.toPath(),prefs.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);moved=true;
    }finally{if(!moved)Files.deleteIfExists(temporary.toPath());}
  }
  private static byte[] read(File file)throws IOException{
    if(Files.isSymbolicLink(file.toPath()))throw new IOException("CPU profile preference link");
    if(!Files.exists(file.toPath(),LinkOption.NOFOLLOW_LINKS))return new byte[0];
    if(!file.isFile()||file.length()>MAX_BYTES)throw new IOException("CPU profile preference bound");
    try(InputStream input=new FileInputStream(file);ByteArrayOutputStream output=new ByteArrayOutputStream()){
      byte[] buffer=new byte[8192];int count;while((count=input.read(buffer))!=-1){if(output.size()+count>MAX_BYTES)throw new IOException("CPU profile preference bound");output.write(buffer,0,count);}return output.toByteArray();
    }
  }
  static byte[] withoutCpu(byte[] source)throws Exception{
    String text=decode(source);StringBuilder result=new StringBuilder(text.length());int offset=0,matches=0;
    while(offset<text.length()){
      int end=text.indexOf('\n',offset);if(end<0)end=text.length();else end++;
      String bytes=text.substring(offset,end);int content=bytes.length();while(content>0&&(bytes.charAt(content-1)=='\r'||bytes.charAt(content-1)=='\n'))content--;
      String line=bytes.substring(0,content),key=key(line);
      String trimmed=line.trim();if(key==null&&!trimmed.isEmpty()&&!trimmed.startsWith("//"))throw new IOException("CPU profile preference ambiguous");
      if(PREF.equals(key)){
        if(!OWNED.matcher(line).matches()||++matches>1)throw new IOException("CPU profile preference ambiguous");
      }else{
        if(line.contains(PREF))throw new IOException("CPU profile preference ambiguous");result.append(bytes);
      }offset=end;
    }return result.toString().getBytes(StandardCharsets.UTF_8);
  }
  private static void validateUser(byte[] bytes)throws Exception{
    String text=decode(bytes);for(String line:text.split("\\n",-1)){
      String trimmed=line.trim();if(trimmed.isEmpty()||trimmed.startsWith("//"))continue;
      String key=key(line);if(key==null||PREF.equals(key)||line.contains(PREF))throw new IOException("CPU user.js override unsupported");
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
