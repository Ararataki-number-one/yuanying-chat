package local.pocketchat;

import java.util.ArrayList;
import java.util.List;

/** Records rendered copy and action callbacks without implementing Android layout. */
class LinearLayout {
 final List<String> messages=new ArrayList<>();
 static class LayoutParams {LayoutParams(int width,int height){}}
 void addView(String message,LayoutParams layout){messages.add(message);}
}
class ReferenceUi {
 static String modalWarning(Object owner,String glyph,String title,String detail){return title+"\n"+detail;}
 static void modalFooterNote(LinearLayout body,String note){body.messages.add(note);}
 static class Modal {
  final LinearLayout body=new LinearLayout();
  static int shows;Runnable positive,negative;String positiveLabel,negativeLabel;boolean shown,closeHidden;java.util.function.Consumer<Object> dismiss;
  Modal(Object owner,String title){}
  Modal hideClose(){closeHidden=true;return this;}
  void note(String note){body.messages.add(note);}
  void setOnDismissListener(java.util.function.Consumer<Object> listener){dismiss=listener;}
  void dismiss(){shown=false;if(dismiss!=null)dismiss.accept(this);}
  void buttons(String left,Runnable cancel,String right,Runnable confirm){negative=cancel;negativeLabel=left;positive=confirm;positiveLabel=right;}
  void show(){shown=true;shows++;}
 }
}
