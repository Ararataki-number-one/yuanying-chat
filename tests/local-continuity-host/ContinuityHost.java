package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import java.util.*;
import org.json.*;

public final class ContinuityHost {
  static int checks;
  static void check(String name,boolean value){checks++;if(!value)throw new AssertionError(name);}
  static LocalContinuityPolicy.Draft draft(String body,String origin,long at){return new LocalContinuityPolicy.Draft(body,origin,"https://chatgpt.com/c/test",at);}
  static Map<String,Object> row(Object... values){Map<String,Object> row=new HashMap<>();for(int i=0;i<values.length;i+=2)row.put((String)values[i],values[i+1]);return row;}
  static Map<String,Object> conversation(String title,String serial,long at){return row("url","https://chatgpt.com/c/"+at,"title",title,"messages",serial,"touched",at,"draft","");}
  static String serial(String body)throws Exception{return new JSONArray().put(new JSONObject().put("role","user").put("text",body)).toString();}
  public static void main(String[] args)throws Exception{
    check("Unicode/fullwidth and case normalization",LocalContinuityPolicy.matches("ｃｈａｔ 测试","CHAT","一个测试"));
    check("Multiple tokens may match separate message fields",LocalContinuityPolicy.matches("first last","first message","last message"));
    check("Every token is required",!LocalContinuityPolicy.matches("first absent","first message"));
    check("Unicode preview does not split a supplementary character",LocalContinuityPolicy.preview("😀甲乙",1).equals("😀…"));
    check("Preview whitespace folds without rewriting source",LocalContinuityPolicy.preview("  甲\n乙  ",20).equals("甲 乙"));
    List<LocalContinuityPolicy.Draft> source=Arrays.asList(draft("相同草稿","older",1),draft("相同草稿","newer",5),draft("  ","empty",9),draft("另一份","other",3));
    List<LocalContinuityPolicy.Draft> drafts=LocalContinuityPolicy.drafts(source,"",20);
    check("Draft deduplication keeps newest recovery copy",drafts.size()==2&&drafts.get(0).origin.equals("newer"));
    check("Draft source may be searched",LocalContinuityPolicy.drafts(source,"other",20).get(0).body.equals("另一份"));
    check("Matching older source survives newer same-body nonmatch",LocalContinuityPolicy.drafts(source,"older",20).get(0).origin.equals("older"));
    check("Draft limit applies after ordering and deduplication",LocalContinuityPolicy.drafts(source,"",1).get(0).created==5);
    List<LocalContinuityPolicy.Message> messages=Arrays.asList(new LocalContinuityPolicy.Message("user","First prompt",1),new LocalContinuityPolicy.Message("assistant","Actual answer 😀",2));
    check("Reader search keeps original conversation position",LocalContinuityPolicy.messages(messages,"answer").get(0).position==2);
    check("Copy preserves exact text, roles and order",LocalContinuityPolicy.transcript("Title",messages).equals("Title\n\n我\nFirst prompt\n\nChatGPT\nActual answer 😀"));
    check("Clipboard budget rejects oversized transcript before allocation",!LocalContinuityPolicy.copyFits("Title",messages,10)&&LocalContinuityPolicy.copyFits("Title",messages,200));
    Context context=new Context();
    for(int i=100;i>=1;i--)context.conversations.add(conversation("conversation "+i,serial(i==1?"oldest \"quoted\"\\text\nneedle":"new message"),i));
    LocalContinuityStore.History history=LocalContinuityStore.history(context,"quoted\\text",10);
    check("Raw JSON escaped byte search is not required",history.rows.isEmpty());
    history=LocalContinuityStore.history(context,"\"quoted\"\\text",10);
    check("Full text finds decoded quotes/backslashes beyond first page",history.rows.size()==1&&history.rows.get(0).touched==1);
    history=LocalContinuityStore.history(context,"",2);
    check("Conversation paging advertises further matching rows",history.rows.size()==2&&history.more);
    check("Conversation snapshot keeps original message text",LocalContinuityStore.history(context,"needle",10).rows.get(0).messages.get(0).text.equals("oldest \"quoted\"\\text\nneedle"));
    context.conversations.add(0,conversation("corrupt","not-json",101));
    history=LocalContinuityStore.history(context,"needle",10);
    check("Corrupt local row does not hide readable matches",history.incomplete&&history.rows.size()==1);
    context.conversations.add(0,row("url","https://untrusted.example/c/1","title","External","messages",serial("external content"),"touched",500));
    check("Reader never includes unrelated origin records",LocalContinuityStore.history(context,"external content",10).rows.isEmpty());
    Context other=new Context();other.conversations.add(conversation("other environment",serial("private second profile"),1));
    check("Read uses supplied profile context only",LocalContinuityStore.history(other,"needle",10).rows.isEmpty()&&LocalContinuityStore.history(context,"private second",10).rows.isEmpty());
    context.archives.add(row("body","shared body","origin","new archive","url","https://chatgpt.com/c/1","created",200L));
    context.archives.add(row("body","archive older","origin","old archive","url","https://chatgpt.com/c/1","created",1L));
    context.preferences.put("draft","legacy input");context.preferences.put("draftBackup:old","shared body");context.preferences.put("legacyPending","{\"prompt\":\"old pending\"}");
    context.conversations.add(0,row("draft","conversation draft","title","previous title","url","https://chatgpt.com/c/22","touched",80L,"messages","[]"));
    LocalContinuityStore.Drafts draftResult=LocalContinuityStore.drafts(context,"",20);
    check("Recovery search includes archive, legacy input, legacy request and conversation drafts",draftResult.rows.size()==5);
    check("Duplicate legacy backup cannot displace newer archive",draftResult.rows.get(0).origin.equals("new archive"));
    check("Draft paging advertises more matches",LocalContinuityStore.drafts(context,"",2).more);
    check("Draft filtering runs across archived and old stores",LocalContinuityStore.drafts(context,"previous title",10).rows.get(0).body.equals("conversation draft"));
    check("New profile has no access to first profile drafts",LocalContinuityStore.drafts(other,"shared body",20).rows.isEmpty());
    check("Readers never call a storage write",context.writeCalls==0&&other.writeCalls==0);
    ReaderCopyHost.verify();
    PerformanceCases.verify();
    System.out.println("{\"status\":\"passed\",\"passed\":"+checks+",\"actualAndroidExecution\":false,\"actualSqliteExecution\":false,\"performance\":"+PerformanceCases.metrics+"}");
  }
}

final class Database {
  final Context context;final boolean archive;Database(Context context,boolean archive){this.context=context;this.archive=archive;}
  Cursor query(String table,String[] columns,String selection,String[] values,String group,String having,String order){
    List<Map<String,Object>> result=new ArrayList<>();for(Map<String,Object> row:archive?context.archives:context.conversations){if("draft<>''".equals(selection)&&(row.get("draft")==null||row.get("draft").toString().isEmpty()))continue;if("messages<>'[]'".equals(selection)&&"[]".equals(row.get("messages")))continue;if("url=?".equals(selection)&&!row.get("url").equals(values[0]))continue;result.add(row);}return new Cursor(result,columns);
  }
}
final class ConversationStore implements AutoCloseable {
  final Context context;ConversationStore(Context context){this.context=context;}Database getReadableDatabase(){return new Database(context,false);}public void close(){}
}
final class DraftArchive {
  final Context context;DraftArchive(Context context){this.context=context;}static DraftArchive get(Context context){return new DraftArchive(context);}Database getReadableDatabase(){return new Database(context,true);}
}
final class MainActivity {static boolean chatUrl(String value){return value.startsWith("https://chatgpt.com/");}}
