package local.pocketchat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Host parser checks: no network requests, account login, or Android persistence claimed. */
public final class ExitSubscriptionParserTest {
  static int checks;
  static void check(boolean condition,String label){checks++;if(!condition)throw new AssertionError(label);}
  static List<ExitSubscriptionParser.Node> parse(String text)throws Exception{return ExitSubscriptionParser.parse(text.getBytes(StandardCharsets.UTF_8));}
  static void reject(String text,String label)throws Exception{try{parse(text);throw new AssertionError(label);}catch(IOException expected){check(!expected.getMessage().contains("secret-password"),label+" sanitized");}}
  public static void main(String[] args)throws Exception{
    check(ExitSubscriptionIdentity.cacheSlot(ExitSubscriptionIdentity.source("https://example.test/secret-token123")).matches("[a-z-]+"),"exit cache slot satisfies SecretStore alphabet");
    check(!ExitSubscriptionIdentity.source("https://example.test/a").equals(ExitSubscriptionIdentity.source("https://example.test/b")),"sources have typed distinct identities");
    String first="proxies:\n  - name: '出口 # A'\n    type: socks5\n    server: example.test\n    port: 1080\n    username: 'user'\n    password: 'secret-password'\n    udp: true\n";
    ExitSubscriptionParser.Node n=parse(first).get(0);check(n.name.equals("出口 # A")&&n.host.equals("example.test")&&n.port==1080,"block map");check(n.password.equals("secret-password"),"quoted credential preserved");
    String flow="proxies:\n  - {name: \"same, name\", type: socks5, server: other.test, port: 1081, username: \"a:b\", password: \"a,#b\"}\n";
    ExitSubscriptionParser.Node f=parse(flow).get(0);check(f.name.equals("same, name")&&f.password.equals("a,#b"),"flow quoted punctuation");
    check(parse("proxies:\n- name: one\n  type: socks5\n  server: one.test\n  port: 1080\n").size()==1,"YAML indentless sequence");
    check(parse(first.replace("'出口 # A'","'Bob''s exit'")).get(0).name.equals("Bob's exit"),"single quote escape");
    check(parse(first.replace("'出口 # A'","\"a\\\"b\\\\c\"")).get(0).name.equals("a\"b\\c"),"bounded double quote escapes");
    check(parse("\ufeff"+first).size()==1,"UTF-8 BOM");
    check(parse("# source comment\n"+first+"# trailing\n").size()==1,"comments");
    ExitSubscriptionParser.Node changed=parse(first.replace("secret-password","changed")).get(0);check(n.key.equals(changed.key),"credential rotation retains node identity");check(!n.configRevision.equals(changed.configRevision)&&!n.credentialRevision.equals(changed.credentialRevision),"credential rotation changes revisions");
    ExitSubscriptionParser.Node renamed=parse(first.replace("出口 # A","another display name")).get(0);check(n.key.equals(renamed.key)&&n.configRevision.equals(renamed.configRevision),"display name isn't identity");
    check(!n.key.equals(parse(first.replace("example.test","other.test")).get(0).key),"different endpoints aren't same node");
    check(parse("proxies:\n- {name: same, type: socks5, server: first.test, port: 1080}\n- {name: same, type: socks5, server: second.test, port: 1080}\n").size()==2,"duplicate labels with distinct identities");
    ExitSubscriptionParser.Node explicit=parse(first+"    x-pocket-id: fixed-01\n").get(0),explicitChanged=parse(first.replace("example.test","new.test")+"    x-pocket-id: fixed-01\n").get(0);check(explicit.key.equals(explicitChanged.key)&&!explicit.configRevision.equals(explicitChanged.configRevision),"explicit provider ID with route revision");
    ExitSubscriptionParser.Node u=parse("socks5://a%2Bb:p%3Aa%23%2Bb@example.test:1080#%E5%87%BA%E5%8F%A3\n").get(0);check(u.user.equals("a+b")&&u.password.equals("p:a#+b")&&u.name.equals("出口"),"URI percent decoding");
    check(parse("socks5://a+b:p+a@example.test:1080\n").get(0).password.equals("p+a"),"URI plus preserved");
    check(parse("socks5://[2001:db8::1]:1080#IPv6\n").get(0).host.equals("2001:db8::1"),"IPv6 URI");
    for(String bad:new String[]{"", "proxies: []", "---\n"+first, first+"rules:\n - MATCH,DIRECT\n", first.replace("type: socks5","type: vless"), first.replace("port: 1080","port: 0"), first.replace("port: 1080","port: 65536"),first.replace("port: 1080","port: 01080e2"),first.replace("server: example.test","server: https://example.test"),first.replace("udp: true","tls: true"),first.replace("udp: true","udp: maybe"),first.replace("password: 'secret-password'","password: null"),first.replace("password: 'secret-password'","password: 1234"),first.replace("password: 'secret-password'","password: true"),first.replace("udp: true","skip-cert-verify: true"),first.replace("name: '出口 # A'","name: &alias something"),first.replace("name: '出口 # A'","name: *alias"),first.replace("name: '出口 # A'","name: !!str abc"),first.replace("name: '出口 # A'","name: |\n      multiline"),first.replace("name: '出口 # A'","name: null\n    name: duplicate"),first.replace("    port:","\tport:"),first.replace("password: 'secret-password'","password: \"secret-password\\n\""),first+"    nested:\n      thing: value\n",first.replace("username: 'user'","username: ''"),"socks5://example.test:1080?udp=true", "http://example.test:1080", "socks5://example.test:1080/path", "socks5://u:secret-password@example.test:1080#%xx", "socks5://u:%C3%28@example.test:1080"})reject(bad,"reject unsupported structure");
    reject(first+first.replace("proxies:\n",""),"duplicate endpoint ID");
    reject(first+first.replace("proxies:\n","").replace("secret-password","new"),"conflicting same endpoint credentials");
    reject(first.replace("password: 'secret-password'","password: '"+String.join("",Collections.nCopies(130,"密"))+"'"),"SOCKS credential byte bound");
    byte[] malformed={(byte)0xc3,(byte)0x28};try{ExitSubscriptionParser.parse(malformed);throw new AssertionError("UTF8");}catch(IOException expected){checks++;}
    try{ExitSubscriptionParser.parse(new byte[ExitSubscriptionParser.MAX_BYTES+1]);throw new AssertionError("size");}catch(IOException expected){checks++;}
    StringBuilder huge=new StringBuilder("proxies:\n");for(int i=0;i<257;i++)huge.append("- {name: n, type: socks5, server: h").append(i).append(".test, port: 1080}\n");reject(huge.toString(),"node count bound");
    System.out.println("ExitSubscriptionParserTest: "+checks+" checks passed (host parser scope)");
  }
}
