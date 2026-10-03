package local.pocketchat;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Host policy checks; these do not authenticate a Google account. */
public final class LoginSettingsPolicyTest {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean ok){if(!ok)throw new AssertionError(name);checks.add(name);}
  public static void main(String[] args)throws Exception{
    check("Pending submission remains protected",!BrowserSettingsPolicy.reason(true,false,false,false,false,false).isEmpty());
    check("Active submission remains protected",!BrowserSettingsPolicy.reason(false,true,false,false,false,false).isEmpty());
    check("Actual web operation remains protected",!BrowserSettingsPolicy.reason(false,false,true,false,false,false).isEmpty());
    check("Active download remains protected",!BrowserSettingsPolicy.reason(false,false,false,true,false,false).isEmpty());
    check("Uploading attachment remains protected",!BrowserSettingsPolicy.reason(false,false,false,false,true,false).isEmpty());
    check("Live reply remains protected",!BrowserSettingsPolicy.reason(false,false,false,false,false,true).isEmpty());
    check("Idle state has no task blocker",BrowserSettingsPolicy.reason(false,false,false,false,false,false).isEmpty());
    check("Retry timers and loading can be replaced",!BrowserDisplay.busy(false,true,true,true,false));
    check("Navigation cannot override a pending task",BrowserDisplay.busy(true,true,true,true,false));
    check("Navigation cannot override a fresh reply",BrowserDisplay.busy(false,true,true,true,true));
    check("Fresh busy state binds to current chat navigation",BrowserSettingsPolicy.currentReply(true,true,true,17,17));
    check("Prior document cannot block new navigation",!BrowserSettingsPolicy.currentReply(true,true,true,16,17));
    check("Prior conversation cannot block current page",!BrowserSettingsPolicy.currentReply(true,false,true,17,17));
    check("Google login ignores old chat busy state",!BrowserSettingsPolicy.currentReply(false,false,true,17,17));
    check("New idle inspection clears an earlier busy result",!BrowserSettingsPolicy.currentReply(true,true,false,17,17));
    check("Google HTTPS login is recognized",LoginPagePolicy.google("https://accounts.google.com/v3/signin/rejected"));
    check("Google explicit HTTPS port is recognized",LoginPagePolicy.google("https://accounts.google.com:443/v3/signin/identifier"));
    for(String url:new String[]{"http://accounts.google.com/","https://accounts.google.com.evil.test/","https://evil.test/accounts.google.com","https://accounts.google.com@evil.test/","https://user@accounts.google.com/","https://accounts.google.com:8443/","javascript:accounts.google.com","file:///accounts.google.com","not a url"})check("Reject untrusted login URL "+url,!LoginPagePolicy.google(url));
    for(String host:new String[]{"accounts.google.com","auth.openai.com","auth0.openai.com","appleid.apple.com","login.live.com","login.microsoftonline.com"})check("Provider login wait state for "+host,LoginPagePolicy.login("https://"+host+"/login"));
    check("ChatGPT auth path is a login page",LoginPagePolicy.login("https://chatgpt.com/auth/login"));
    check("ChatGPT conversation retains normal synchronization",!LoginPagePolicy.login("https://chatgpt.com/c/room"));
    check("Ordinary external pages are not classified as auth",!LoginPagePolicy.login("https://example.com/login"));
    check("Spoofed auth host is not recognized",!LoginPagePolicy.login("https://auth.openai.com.evil.test/log-in"));
    if(args.length>0)Files.write(Paths.get(args[0]),LoginPagePolicy.blockedScript().getBytes(StandardCharsets.UTF_8));
    StringBuilder out=new StringBuilder("{\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"scope\":\"host policy only; no account login\",\"checks\":[");
    for(int i=0;i<checks.size();i++){if(i>0)out.append(',');out.append("{\"name\":\"").append(checks.get(i)).append("\",\"pass\":true}");}System.out.println(out.append("]}"));
  }
}
