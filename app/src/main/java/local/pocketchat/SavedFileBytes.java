package local.pocketchat;

import java.io.*;
import java.util.function.BooleanSupplier;

/** Bytes actually accepted by the destination stream; the caller must also close/publish it. */
final class SavedFileBytes {
  static long copy(InputStream in,OutputStream out,BooleanSupplier current)throws IOException{
    if(in==null||out==null)throw new IOException("保存位置无法写入");byte[] buffer=new byte[65536];long copied=0;int count;
    while((count=in.read(buffer))!=-1){if(!current.getAsBoolean())throw new IOException("保存已暂停");out.write(buffer,0,count);copied+=count;}
    out.flush();return copied;
  }
}
