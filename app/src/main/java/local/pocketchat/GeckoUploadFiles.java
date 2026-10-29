package local.pocketchat;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.BooleanSupplier;

/** SAF/cloud document URIs are streams, not filesystem paths usable by Gecko. */
final class GeckoUploadFiles {
  static final long MAX=512L*1024*1024;
  static final class Cleanup {
    final int removedFiles,failedEntries;final long removedBytes;
    Cleanup(int files,long bytes,int failed){removedFiles=files;removedBytes=bytes;failedEntries=failed;}
    boolean complete(){return failedEntries==0;}
  }
  static final class Cancelled extends IOException {
    final Cleanup cleanup;
    Cancelled(Cleanup cleanup){super("附件读取已取消");this.cleanup=cleanup;}
  }
  /** A bounded, read-only sample; retained bytes are never classified as disposable. */
  static final class Usage {
    int directories,files,unknownEntries;long bytes;boolean complete=true;
  }
  static final class Selection {
    final File directory;final Uri[] files;
    Selection(File directory,Uri[] files){this.directory=directory;this.files=files;}
    Cleanup delete(){
      int removed=0,failed=0;long bytes=0;
      try{
        if(Files.isSymbolicLink(directory.toPath()))return new Cleanup(0,0,directory.delete()?0:1);
        File[] children=directory.listFiles();if(children==null)return new Cleanup(0,0,directory.exists()?1:0);
        for(File child:children){long size=!Files.isSymbolicLink(child.toPath())&&child.isFile()?child.length():0;if(child.delete()){removed++;bytes+=size;}else if(child.exists()||Files.isSymbolicLink(child.toPath()))failed++;}
        if(!directory.delete()&&directory.exists())failed++;
      }catch(RuntimeException unavailable){failed++;}
      return new Cleanup(removed,bytes,failed);
    }
  }
  static Selection prepare(Context context,Uri[] source)throws IOException {
    return prepare(context,source,()->false);
  }
  static void checkCancelled(BooleanSupplier cancelled)throws Cancelled {
    if(Thread.currentThread().isInterrupted()||cancelled.getAsBoolean())throw new Cancelled(new Cleanup(0,0,0));
  }
  static Selection prepare(Context context,Uri[] source,BooleanSupplier cancelled)throws IOException {
    if(source==null||source.length==0)throw new IOException("没有选中附件，请重新选择");
    Objects.requireNonNull(cancelled);checkCancelled(cancelled);
    File parent=new File(context.getCacheDir(),"gecko-uploads"),directory=new File(parent,UUID.randomUUID().toString());
    if(!directory.mkdirs())throw new IOException("无法准备附件，请检查剩余空间");
    Selection selection=new Selection(directory,new Uri[source.length]);long total=0;Set<String> names=new HashSet<>();
    try{for(int i=0;i<source.length;i++){
      checkCancelled(cancelled);
      Uri uri=source[i];if(uri==null||!("content".equals(uri.getScheme())||"file".equals(uri.getScheme())))throw new IOException("所选附件不可读取，请重新选择");
      String name="附件",mime=null;
      if("file".equals(uri.getScheme()))name=new File(uri.getPath()).getName();
      else {
        // Photo/cloud providers may grant the stream but omit their metadata.
        // An optional name or MIME lookup must not reject a readable document.
        try(Cursor cursor=context.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst()){int column=cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);if(column>=0&&!cursor.isNull(column)){String candidate=cursor.getString(column);if(candidate!=null)name=candidate;}}}catch(RuntimeException ignored){}
        try{mime=context.getContentResolver().getType(uri);}catch(RuntimeException ignored){}
      }
      name=name.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]","_").trim();if(name.isEmpty()||name.equals(".")||name.equals(".."))name="附件";if(name.length()>80)name=name.substring(name.length()-80);
      // Gecko infers File.type from the prepared path, not the provider MIME.
      // Also retain document types when a cloud provider gives an extensionless name.
      if(mime!=null){int dot=name.lastIndexOf('.');String actual=dot<0?null:MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substring(dot+1).toLowerCase(Locale.ROOT));String extension=MimeTypeMap.getSingleton().getExtensionFromMimeType(mime.toLowerCase(Locale.ROOT));if(extension!=null&&(dot<0||mime.startsWith("image/")&&!mime.equalsIgnoreCase(actual)))name+="."+extension;}
      String original=name;int duplicate=1,dot=original.lastIndexOf('.');while(!names.add(name)){String suffix=" ("+(++duplicate)+")";name=dot>0?original.substring(0,dot)+suffix+original.substring(dot):original+suffix;}
      File file=new File(directory,name);
      checkCancelled(cancelled);
      try(InputStream input=context.getContentResolver().openInputStream(uri);OutputStream output=new FileOutputStream(file)){
        if(input==null)throw new IOException("附件不可读取，请重新选择");byte[] buffer=new byte[65536];int count;
        while(true){checkCancelled(cancelled);count=input.read(buffer);checkCancelled(cancelled);if(count==-1)break;total+=count;if(total>MAX||directory.getUsableSpace()<64L*1024*1024)throw new IOException("附件过大或剩余空间不足");output.write(buffer,0,count);}
      }
      checkCancelled(cancelled);
      selection.files[i]=Uri.fromFile(file);
    }checkCancelled(cancelled);return selection;}catch(Exception error){Cleanup cleanup=selection.delete();if(error instanceof Cancelled)throw new Cancelled(cleanup);throw new IOException("读取附件失败："+(error.getMessage()==null?"请重新选择":error.getMessage()),error);}
  }
  /** Run on an existing IO worker only, when the user requests storage details. */
  static Usage usage(Context context){
    Usage result=new Usage();long deadline=System.nanoTime()+100000000L;int entries=0;
    try{
      File cache=context.getCacheDir(),root=new File(cache,"gecko-uploads");
      if(Files.isSymbolicLink(cache.toPath())||Files.isSymbolicLink(root.toPath())){result.unknownEntries++;result.complete=false;return result;}
      if(!root.exists())return result;
      if(!root.isDirectory()||!cache.getCanonicalFile().equals(root.getCanonicalFile().getParentFile())){result.unknownEntries++;result.complete=false;return result;}
      try(DirectoryStream<Path> directories=Files.newDirectoryStream(root.toPath())){
        for(Path directory:directories){
          if(++entries>4096||System.nanoTime()>deadline){result.complete=false;break;}
          if(!directory.getFileName().toString().matches("[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")||!Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS)){result.unknownEntries++;result.complete=false;continue;}
          result.directories++;
          try(DirectoryStream<Path> files=Files.newDirectoryStream(directory)){
            for(Path file:files){
              if(++entries>4096||System.nanoTime()>deadline){result.complete=false;return result;}
              if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)){result.unknownEntries++;result.complete=false;continue;}
              result.files++;result.bytes+=Files.size(file);
            }
          }
        }
      }
    }catch(IOException|RuntimeException unavailable){result.complete=false;}
    return result;
  }
}
