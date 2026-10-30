package local.pocketchat;
import java.io.*;import java.nio.*;import java.nio.charset.*;import java.util.*;import org.json.*;

public final class EnvironmentConfigBackupHost {
  static final JSONArray checks=new JSONArray();
  interface Action{void run()throws Exception;}
  static void check(String name,boolean pass)throws Exception{checks.put(new JSONObject().put("name",name).put("pass",pass));if(!pass)throw new AssertionError(name);}
  static void rejected(String name,Action action)throws Exception{boolean failed=false;try{action.run();}catch(IOException expected){failed=true;check(name+" has no sensitive echo",!expected.getMessage().contains("sensitive-password"));}check(name,failed);}
  static JSONObject prefs()throws Exception{JSONObject p=new JSONObject();for(String key:EnvironmentConfigBackup.PREFERENCES)p.put(key,!"wifiDownloads".equals(key));return p;}
  static EnvironmentConfigBackup.Config sample()throws Exception{return new EnvironmentConfigBackup.Config("环境备份",BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP).withLocales(Arrays.asList("zh-CN","en-US")).json(),prefs());}
  public static void main(String[] args)throws Exception{
    EnvironmentConfigBackup.Config config=sample();char[] password="sensitive-password-123".toCharArray();byte[] one=EnvironmentConfigBackup.encrypt(config,password),two=EnvironmentConfigBackup.encrypt(config,password);
    check("fresh salt IV and ciphertext for repeated backup",!Arrays.equals(one,two));
    EnvironmentConfigBackup.Config restored=EnvironmentConfigBackup.decrypt(one,password);
    check("name survives",restored.name.equals(config.name));check("complete browser template survives",restored.browser.json().toString().equals(config.browser.json().toString()));
    check("language order retained",restored.browser.locales.equals(Arrays.asList("zh-CN","en-US")));check("preference types and values retained",restored.preferences().getBoolean("saveDraft")&&!restored.preferences().getBoolean("wifiDownloads"));
    String serialized=new String(config.bytes(),StandardCharsets.UTF_8);for(String key:new String[]{"network","Cookie","cookie","draftRaw","environmentId","generation","deviceKey","appliedRevision","exit","subscription","proxy"})check("payload excludes "+key,!serialized.contains('"'+key+'"'));
    check("ciphertext does not contain template label",!new String(one,StandardCharsets.ISO_8859_1).contains(BrowserIdentitySpec.RFP));
    rejected("wrong password",()->EnvironmentConfigBackup.decrypt(one,"wrong-password-123".toCharArray()));
    for(int index:new int[]{0,5,6,7,8,11,12,27,28,39,40,one.length-1}){byte[] changed=one.clone();changed[index]^=1;rejected("tamper byte "+index,()->EnvironmentConfigBackup.decrypt(changed,password));}
    rejected("truncated ciphertext",()->EnvironmentConfigBackup.decrypt(Arrays.copyOf(one,one.length-1),password));
    rejected("oversize ciphertext",()->EnvironmentConfigBackup.decrypt(new byte[EnvironmentConfigBackup.LIMIT+1],password));
    rejected("short password",()->EnvironmentConfigBackup.encrypt(config,new char[9]));rejected("long password",()->EnvironmentConfigBackup.encrypt(config,new char[257]));
    byte[] input=Arrays.copyOf(one,one.length);check("bounded read valid",Arrays.equals(input,EnvironmentConfigBackup.read(new ByteArrayInputStream(input))));
    final int[] consumed={0};InputStream infinite=new InputStream(){public int read(){consumed[0]++;return 1;}public int read(byte[] b,int off,int len){Arrays.fill(b,off,off+len,(byte)1);consumed[0]+=len;return len;}};
    rejected("bounded read oversize",()->EnvironmentConfigBackup.read(infinite));check("read stops at exact limit plus one",consumed[0]==EnvironmentConfigBackup.LIMIT+1);
    InputStream zeroOnce=new ByteArrayInputStream(one){boolean zero=true;public synchronized int read(byte[] b,int off,int len){if(zero){zero=false;return 0;}return super.read(b,off,len);}};check("zero-length provider read cannot spin",Arrays.equals(one,EnvironmentConfigBackup.read(zeroOnce)));
    JSONObject source=new JSONObject(serialized);source.put("schema",2);rejected("future payload version",()->EnvironmentConfigBackup.Config.read(source.toString().getBytes(StandardCharsets.UTF_8)));
    rejected("floating schema",()->EnvironmentConfigBackup.Config.read(serialized.replace("\"schema\":1","\"schema\":1.0").getBytes(StandardCharsets.UTF_8)));
    JSONObject unknown=new JSONObject(serialized).put("network",new JSONObject());rejected("unknown payload field",()->EnvironmentConfigBackup.Config.read(unknown.toString().getBytes(StandardCharsets.UTF_8)));
    JSONObject badPrefs=prefs().put("saveDraft","true");rejected("boolean string rejected",()->new EnvironmentConfigBackup.Config("环境",config.browser.json(),badPrefs));
    JSONObject badBrowser=config.browser.json().put("canvas","anything");rejected("unsupported native control rejected",()->new EnvironmentConfigBackup.Config("环境",badBrowser,prefs()));
    JSONObject unknownTemplate=config.browser.json().put("templateId","arbitrary-phone");rejected("unsupported template rejected",()->new EnvironmentConfigBackup.Config("环境",unknownTemplate,prefs()));
    JSONObject mismatch=config.browser.json().put("privacy","standard");rejected("template protection mismatch",()->new EnvironmentConfigBackup.Config("环境",mismatch,prefs()));
    JSONObject badLanguages=config.browser.json().put("locales",new JSONArray().put(true));rejected("language type strict",()->new EnvironmentConfigBackup.Config("环境",badLanguages,prefs()));
    JSONObject repeatedLanguages=config.browser.json().put("locales",new JSONArray().put("zh-CN").put("zh-cn"));rejected("duplicate language rejected",()->new EnvironmentConfigBackup.Config("环境",repeatedLanguages,prefs()));
    rejected("trailing payload data",()->EnvironmentConfigBackup.Config.read((serialized+"{}").getBytes(StandardCharsets.UTF_8)));
    rejected("invalid UTF8",()->EnvironmentConfigBackup.Config.read(new byte[]{(byte)0xc0,(byte)0xaf}));
    StringBuilder deep=new StringBuilder();for(int i=0;i<50;i++)deep.append('[');for(int i=0;i<50;i++)deep.append(']');rejected("parser nesting bounded",()->EnvironmentConfigBackup.Config.read(deep.toString().getBytes(StandardCharsets.UTF_8)));
    rejected("long environment name",()->new EnvironmentConfigBackup.Config(new String(new char[25]).replace('\0','a'),config.browser.json(),prefs()));
    JSONObject immutable=prefs();EnvironmentConfigBackup.Config frozen=new EnvironmentConfigBackup.Config("独立副本",config.browser.json(),immutable);immutable.put("saveDraft",false);check("caller preferences detached",frozen.preferences().getBoolean("saveDraft"));JSONObject detached=frozen.preferences();detached.put("saveDraft",false);check("returned preferences detached",frozen.preferences().getBoolean("saveDraft"));
    check("fixed reasonable KDF work factor",ByteBuffer.wrap(one,8,4).getInt()==210000);check("header has fixed version and cipher identifiers",one[5]==1&&one[6]==1&&one[7]==0);
    Arrays.fill(password,'\0');System.out.println(new JSONObject().put("status","passed").put("passed",checks.length()).put("checks",checks).put("physicalPhoneAcceptance",false));
  }
}
