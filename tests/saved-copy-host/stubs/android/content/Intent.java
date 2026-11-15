package android.content;
import android.net.Uri;
public final class Intent {
  public static final String ACTION_CREATE_DOCUMENT="create-document",CATEGORY_OPENABLE="openable",EXTRA_TITLE="title";
  public final String action;private Uri data;
  public Intent(String action){this.action=action;}
  public Intent setData(Uri uri){data=uri;return this;}public Uri getData(){return data;}
  public Intent addCategory(String value){if(!CATEGORY_OPENABLE.equals(value))throw new AssertionError("Unexpected category");return this;}
  public Intent setType(String value){if(value==null)throw new AssertionError("Missing MIME");return this;}
  public Intent putExtra(String key,String value){if(!EXTRA_TITLE.equals(key))throw new AssertionError("Unexpected extra");return this;}
}
