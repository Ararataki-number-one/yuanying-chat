package local.pocketchat;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.security.*;
import java.util.*;
import javax.crypto.*;
import javax.crypto.spec.*;
import org.json.*;

/** Portable configuration only. Never serialize a vault, device key, identity,
 * route receipt, login, draft, page state or browser storage. */
final class EnvironmentConfigBackup {
  static final int LIMIT=64*1024,ITERATIONS=210000,HEADER=40;
  private static final byte[] MAGIC={'P','C','C','F','G',1,1,0};
  static final String[] PREFERENCES={"autoHistory","saveDraft","restoreScroll","backgroundWait","replyNotice","wifiDownloads","cleanTemporaryCache"};
  static final class Config {
    final String name;
    final BrowserIdentitySpec browser;
    private final String preferences;
    Config(String name,JSONObject browser,JSONObject preferences)throws IOException{
      if(name==null||name.trim().isEmpty()||name.length()>24||name.indexOf('\0')>=0)throw invalid();
      exact(browser,"schema","templateId","display","privacy","locales","timezoneStrategy");
      if(integer(browser,"schema")!=BrowserIdentitySpec.SCHEMA)throw invalid();
      for(String key:new String[]{"templateId","display","privacy","timezoneStrategy"})if(!(browser.opt(key) instanceof String))throw invalid();
      Object languages=browser.opt("locales");if(!(languages instanceof JSONArray))throw invalid();
      JSONArray array=(JSONArray)languages;if(array.length()>3)throw invalid();for(int i=0;i<array.length();i++)if(!(array.opt(i) instanceof String))throw invalid();
      try{this.browser=BrowserIdentitySpec.from(browser);if(!this.browser.validate().isEmpty())throw invalid();}catch(IllegalArgumentException failure){throw invalid();}
      exact(preferences,PREFERENCES);for(String key:PREFERENCES)if(!(preferences.opt(key) instanceof Boolean))throw invalid();
      this.name=name.trim();this.preferences=preferences.toString();
    }
    JSONObject preferences(){try{return new JSONObject(preferences);}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
    byte[] bytes()throws IOException{
      try{return new JSONObject().put("schema",1).put("name",name).put("browser",browser.json()).put("preferences",preferences()).toString().getBytes(StandardCharsets.UTF_8);}catch(JSONException problem){throw invalid();}
    }
    static Config read(byte[] raw)throws IOException{
      if(raw==null||raw.length==0||raw.length>LIMIT-HEADER-16)throw invalid();
      try{
        String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
        boundedNesting(text);
        JSONTokener parser=new JSONTokener(text);Object value=parser.nextValue();if(!(value instanceof JSONObject)||parser.nextClean()!=0)throw invalid();JSONObject json=(JSONObject)value;
        exact(json,"schema","name","browser","preferences");if(integer(json,"schema")!=1||!(json.opt("name") instanceof String))throw invalid();
        return new Config(json.getString("name"),json.getJSONObject("browser"),json.getJSONObject("preferences"));
      }catch(IOException problem){throw problem;}catch(Exception problem){throw invalid();}
    }
  }
  static byte[] encrypt(Config config,char[] password)throws IOException{
    requirePassword(password);byte[] plain=config.bytes(),key=null;
    try{
      if(plain.length>LIMIT-HEADER-16)throw invalid();
      byte[] salt=new byte[16],iv=new byte[12];SecureRandom random=new SecureRandom();random.nextBytes(salt);random.nextBytes(iv);
      byte[] header=ByteBuffer.allocate(HEADER).put(MAGIC).putInt(ITERATIONS).put(salt).put(iv).array();
      key=derive(password,salt);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,iv));cipher.updateAAD(header);
      byte[] encrypted=cipher.doFinal(plain);return ByteBuffer.allocate(header.length+encrypted.length).put(header).put(encrypted).array();
    }catch(GeneralSecurityException problem){throw new IOException("无法加密配置备份",problem);}finally{Arrays.fill(plain,(byte)0);if(key!=null)Arrays.fill(key,(byte)0);}
  }
  static Config decrypt(byte[] sealed,char[] password)throws IOException{
    requirePassword(password);if(sealed==null||sealed.length<HEADER+17||sealed.length>LIMIT)throw invalid();byte[] key=null,plain=null;
    try{
      ByteBuffer buffer=ByteBuffer.wrap(sealed);byte[] magic=new byte[8];buffer.get(magic);if(!Arrays.equals(magic,MAGIC)||buffer.getInt()!=ITERATIONS)throw invalid();
      byte[] salt=new byte[16],iv=new byte[12];buffer.get(salt);buffer.get(iv);key=derive(password,salt);
      Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,iv));cipher.updateAAD(Arrays.copyOf(sealed,HEADER));plain=cipher.doFinal(sealed,HEADER,sealed.length-HEADER);return Config.read(plain);
    }catch(GeneralSecurityException problem){throw new IOException("密码不正确或备份已损坏，原环境未改变");}finally{if(key!=null)Arrays.fill(key,(byte)0);if(plain!=null)Arrays.fill(plain,(byte)0);}
  }
  static byte[] read(InputStream stream)throws IOException{
    if(stream==null)throw invalid();ByteArrayOutputStream output=new ByteArrayOutputStream();byte[] chunk=new byte[4096];int n,total=0;
    while((n=stream.read(chunk,0,Math.min(chunk.length,LIMIT-total+1)))!=-1){if(n==0){int one=stream.read();if(one<0)break;chunk[0]=(byte)one;n=1;}if(n>LIMIT-total)throw new IOException("配置备份超过 64 KB，原环境未改变");output.write(chunk,0,n);total+=n;}return output.toByteArray();
  }
  private static byte[] derive(char[] password,byte[] salt)throws GeneralSecurityException{
    PBEKeySpec spec=new PBEKeySpec(password,salt,ITERATIONS,256);try{return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();}finally{spec.clearPassword();}
  }
  static void requirePassword(char[] password)throws IOException{if(password==null||password.length<10||password.length>256)throw new IOException("备份密码需为 10–256 个字符");}
  private static void boundedNesting(String text)throws IOException{
    int depth=0;boolean quoted=false,escaped=false;for(int i=0;i<text.length();i++){char c=text.charAt(i);if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;}else if(c=='"')quoted=true;else if(c=='{'||c=='['){if(++depth>8)throw invalid();}else if(c=='}'||c==']'){if(--depth<0)throw invalid();}}if(depth!=0||quoted)throw invalid();
  }
  private static long integer(JSONObject object,String key)throws IOException{Object value=object.opt(key);if(!(value instanceof Integer)&&!(value instanceof Long))throw invalid();return ((Number)value).longValue();}
  private static void exact(JSONObject object,String... allowed)throws IOException{
    if(object==null||object.length()!=allowed.length)throw invalid();Set<String> keys=new HashSet<>(Arrays.asList(allowed));Iterator<String> iterator=object.keys();while(iterator.hasNext())if(!keys.contains(iterator.next()))throw invalid();
  }
  static IOException invalid(){return new IOException("备份格式、版本或模板不受支持，原环境未改变");}
}
