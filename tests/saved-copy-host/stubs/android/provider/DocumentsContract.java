package android.provider;
import android.content.*;import android.net.Uri;
/** Controlled document classification, not a real Storage Access Framework provider. */
public final class DocumentsContract {
  public static boolean isDocumentUri(Context context,Uri uri){return "documents.test".equals(uri.getAuthority());}
  public static boolean deleteDocument(ContentResolver resolver,Uri uri){return resolver.delete(uri,null,null)>0;}
}
