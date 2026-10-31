"""Explicit new boundaries for unchanged legacy publication cases.

The full metadata implementation is executed separately by download46-host/run.py.
"""
from pathlib import Path
import hashlib

def emit(package):
    package=Path(package);package.mkdir(parents=True,exist_ok=True)
    code={
      'ProfileCatalog.java':'''package local.pocketchat;import android.content.Context;import org.json.*;final class ProfileCatalog{static ProfileCatalog get(Context c){return new ProfileCatalog();}JSONObject item(int slot){return J.obj("environmentId","00000000-0000-0000-0000-00000000000"+slot,"generation",1,"created",true,"deleting",false,"resetting",false);}}''',
      'SavedDownloadMetadata.java':'''package local.pocketchat;import android.content.Context;import android.net.Uri;import android.database.Cursor;import android.provider.OpenableColumns;import java.io.*;import org.json.*;final class SavedDownloadMetadata{static JSONObject describe(Context c,Uri uri){JSONObject facts=new JSONObject();try{if((c.getPackageName()+".saved-downloads").equals(uri.getAuthority())){File file=SavedDownloadProvider.resolve(c,uri);if(file.isFile())DownloadTasks.put(facts,"savedBytes",file.length(),"sizeSource","owned-stat","actualName",file.getName());}else try(Cursor row=c.getContentResolver().query(uri,new String[]{OpenableColumns.SIZE},null,null,null)){if(row!=null&&row.moveToFirst()&&!row.isNull(0)&&row.getLong(0)>=0)DownloadTasks.put(facts,"savedBytes",row.getLong(0),"sizeSource","provider-size");}}catch(Exception ignored){}DownloadTasks.put(facts,"metadataResult",DownloadMetadataValues.bytes(facts)>=0?"known":"unknown");return facts;}}'''
    }
    paths=[]
    for name,text in code.items():
        target=package/name;target.write_text(text);paths.append(target)
    return paths,{name:hashlib.sha256(text.encode()).hexdigest() for name,text in code.items()}
