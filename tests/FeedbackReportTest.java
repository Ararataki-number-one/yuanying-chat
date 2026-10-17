package local.pocketchat;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
public final class FeedbackReportTest {
 static int checks;static void ok(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
 public static void main(String[] args){
  FeedbackReport report=new FeedbackReport(false,"图片上传 & 失败?","点击添加图片\n没有选择窗口 #1","2.0.6","Android 16");
  ok(report.error().isEmpty());ok(report.issueTitle().startsWith("[问题]"));
  URI uri=URI.create(report.url());ok(uri.getHost().equals("github.com"));ok(uri.getPath().equals("/Ararataki-number-one/yuanying-chat/issues/new"));ok(uri.getFragment()==null);
  String body=null,title=null;for(String p:uri.getRawQuery().split("&")){String[] pair=p.split("=",2);if(pair[0].equals("body"))body=URLDecoder.decode(pair[1],StandardCharsets.UTF_8);if(pair[0].equals("title"))title=URLDecoder.decode(pair[1],StandardCharsets.UTF_8);}
  ok(report.body().equals(body));ok(report.issueTitle().equals(title));
  FeedbackReport privateDevice=new FeedbackReport(true,"建议","提高阅读体验","2.0.6","");ok(!privateDevice.body().contains("系统："));ok(privateDevice.issueTitle().startsWith("[建议]"));
  ok(!new FeedbackReport(false," ","内容","v","").error().isEmpty());ok(!new FeedbackReport(false,"标题"," ","v","").error().isEmpty());
  ok(!new FeedbackReport(false,"a".repeat(81),"内容","v","").error().isEmpty());ok(!new FeedbackReport(false,"标题","a".repeat(2001),"v","").error().isEmpty());
  FeedbackReport longReport=new FeedbackReport(false,"中文标题","内容".repeat(1000),"v","");ok(longReport.error().isEmpty());ok(longReport.url()==null);ok(longReport.baseUrl().length()<FeedbackReport.URL_LIMIT);ok(longReport.body().contains("内容".repeat(1000)));
  ok(FeedbackReport.clean(null).isEmpty());ok(FeedbackReport.clean("\u0000 hello ").equals("hello"));
  System.out.println(checks+" feedback report checks passed");
 }
}
