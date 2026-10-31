package local.pocketchat;

import android.graphics.Typeface;
import android.widget.*;
import android.text.*;
import android.text.style.*;
import java.util.List;

/** Native bounded views only. Source parsing belongs to the history/update worker. */
final class ReleaseNotesRenderer {
  static void append(LinearLayout parent,List<ReleaseNotes.Block> blocks){
    if(blocks.isEmpty())return;SpannableStringBuilder value=new SpannableStringBuilder();
    for(ReleaseNotes.Block block:blocks){if(value.length()>0)value.append("\n\n");int start=value.length();value.append(block.text);int end=value.length();if(start==end)continue;
      if(block.kind==ReleaseNotes.HEADING){value.setSpan(new StyleSpan(Typeface.BOLD),start,end,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);value.setSpan(new RelativeSizeSpan(1.1f),start,end,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);}
      if(block.kind==ReleaseNotes.BULLET)value.setSpan(new BulletSpan(DesignUi.dp(parent.getContext(),8)),start,end,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
      if(block.kind==ReleaseNotes.ORDERED)value.setSpan(new LeadingMarginSpan.Standard(DesignUi.dp(parent.getContext(),8)),start,end,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
      if(block.kind==ReleaseNotes.CODE)value.setSpan(new TypefaceSpan("monospace"),start,end,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }
    TextView text=DesignUi.text(parent.getContext(),"",14,DesignUi.TEXT);text.setText(value);text.setTextIsSelectable(true);text.setLineSpacing(DesignUi.dp(parent.getContext(),3),1);text.setPadding(0,DesignUi.dp(parent.getContext(),6),0,0);parent.addView(text);
  }
}
