package local.pocketchat;

import java.net.URLEncoder;
import java.io.UnsupportedEncodingException;

/** Public, user-reviewed reports. Never accepts preferences, logs or network credentials. */
final class FeedbackReport {
  static final String ISSUES="https://github.com/Ararataki-number-one/yuanying-chat/issues";
  static final int TITLE_LIMIT=80,DETAIL_LIMIT=2000,URL_LIMIT=7000;
  final boolean suggestion;final String title,details,version,system;
  FeedbackReport(boolean suggestion,String title,String details,String version,String system){
    this.suggestion=suggestion;this.title=clean(title);this.details=clean(details);
    this.version=clean(version);this.system=clean(system);
  }
  static String clean(String value){return value==null?"":value.replace("\u0000","").trim();}
  String error(){if(title.isEmpty())return "请用一句话说明问题或建议";if(details.isEmpty())return "请补充发生过程，或你希望改善的体验";if(title.length()>TITLE_LIMIT||details.length()>DETAIL_LIMIT)return "内容太长，请精简后再提交";return "";}
  String issueTitle(){return (suggestion?"[建议] ":"[问题] ")+title;}
  String body(){return "## "+(suggestion?"建议与使用场景":"问题与复现过程")+"\n\n"+details+"\n\n## 应用信息\n\n版本："+version+(system.isEmpty()?"":"\n系统："+system)+"\n\n---\n通过 PocketChat 的问题与建议入口创建。";}
  static String encode(String value){try{return URLEncoder.encode(value,"UTF-8");}catch(UnsupportedEncodingException impossible){throw new AssertionError(impossible);}}
  String baseUrl(){return ISSUES+"/new?title="+encode(issueTitle());}
  String url(){String result=baseUrl()+"&body="+encode(body());return result.length()<=URL_LIMIT?result:null;}
}
