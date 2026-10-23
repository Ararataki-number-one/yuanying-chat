package local.pocketchat;
import java.util.*;
import org.json.*;

/** Production state machine on the JVM, not Android/browser/picker acceptance. */
public final class ResourceUploadHostTest {
  static int checks;
  static void check(String name,boolean ok){checks++;if(!ok)throw new AssertionError(name);System.out.println("PASS "+name);}
  static ResourceUploadState state(){ResourceUploadState state=new ResourceUploadState();state.add(Arrays.asList("report.txt"),"document-one",7,1000);return state;}
  static String first(ResourceUploadState state){return state.batches.keySet().iterator().next();}
  static JSONObject row(String id,long sequence,String value){return J.obj("batchId",id,"sequence",sequence,"files",J.arr(J.obj("name","report.txt","state",value)));}
  static JSONObject result(JSONObject... rows){return J.obj("ok",true,"documentId","document-one","batches",new JSONArray(Arrays.asList(rows)));}
  public static void main(String[] args)throws Exception{
    ResourceUploadState state=state();String id=first(state);
    check("Unknown selection is protected without claiming actual uploading",state.active(7)&&state.unknown(7)&&!state.uploading(7));
    state.observe(result(row(id,1,"uploading")),"document-one",7);
    check("Observed uploading is distinguished from unknown",state.active(7)&&state.uploading(7)&&!state.unknown(7));
    state.observe(result(row(id,2,"unknown")),"document-one",7);
    check("Unknown does not release a formerly uploading selection",state.active(7)&&!state.uploading(7)&&state.unknown(7));
    state.observe(result(row(id,3,"ready")),"document-one",7);state.observe(result(row(id,3,"ready")),"document-one",7);
    check("Duplicate terminal sequence does not count as a fresh sample",state.active(7)&&state.stable()==1);
    state.observe(result(row(id,4,"unknown")),"document-one",7);state.observe(result(row(id,5,"ready")),"document-one",7);
    check("An unknown observation breaks terminal stability",state.active(7)&&state.stable()==1);
    check("Two fresh ready samples end the batch",state.observe(result(row(id,6,"ready")),"document-one",7)&&!state.active(7));
    for(String terminal:Arrays.asList("error","sent","removed")){
      state=state();id=first(state);state.observe(result(row(id,1,terminal)),"document-one",7);
      check("One "+terminal+" observation retains protection",state.active(7));
      state.observe(result(row(id,2,terminal)),"document-one",7);
      check("Two fresh "+terminal+" observations end only that selection",!state.active(7));
    }
    state=state();id=first(state);state.observe(result(row(id,1,"ready"),row(id,2,"ready")),"document-one",7);
    check("Duplicate rows cannot consume two confirmations in one response",state.active(7)&&state.stable()==0);
    JSONObject wrong=result(row(id,1,"ready"));wrong.put("documentId","document-two");state.observe(wrong,"document-one",7);state.observe(result(row(id,1,"ready")),"document-one",8);
    check("Other document and epoch observations are rejected",state.active(7)&&state.stable()==0);
    state.observe(result(row(id,1,"ready")),"document-one",7);state.add(Arrays.asList("report.txt"),"document-one",7,2000);String newer=state.snapshot().getJSONObject(1).getString("batchId");
    state.observe(result(row(id,2,"sent")),"document-one",7);
    check("Late completion of an old same-name batch retains the new batch",state.active(7)&&state.batches.size()==1&&state.batches.containsKey(newer)&&state.unknown(7));
    state.observe(result(row(id,3,"sent")),"document-one",7);
    check("Retired batch observations cannot advance new same-name work",state.stable()==0&&state.batches.get(newer).sequence==0);
    state=new ResourceUploadState();state.add(Arrays.asList("report.txt"),"",7,1000);id=first(state);state.observe(result(row(id,1,"ready")),"document-one",7);
    check("Unbound selection binds only to the accepted current document",state.batches.get(id).document.equals("document-one")&&state.stable()==1);
    JSONObject other=result(row(id,2,"ready"));other.put("documentId","document-two");state.observe(other,"document-two",7);
    check("Bound selection cannot migrate to another document",state.active(7)&&state.stable()==1);
    state.add(Arrays.asList("report.txt"),"document-two",8,2000);state.observe(result(row(id,2,"ready")),"document-one",7);
    check("New navigation invalidates old work without accepting its result",!state.active(7)&&state.active(8)&&state.batches.size()==1&&state.stable()==0);
    state=state();id=first(state);JSONObject malformed=row(id,1,"ready");malformed.getJSONArray("files").getJSONObject(0).put("name","other.txt");state.observe(result(malformed),"document-one",7);
    check("A mismatched filename cannot release the batch",state.active(7)&&state.stable()==0);
    System.out.println("TOTAL "+checks);
  }
}
