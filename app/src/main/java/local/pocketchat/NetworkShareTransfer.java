package local.pocketchat;

import android.os.ParcelFileDescriptor;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executor;
import org.json.*;

/** Same-UID Binder facade passes only a descriptor; provider bytes never enter Bundle. */
final class NetworkShareTransfer {
  static final int MAGIC=0x504e3436;
  static void text(DataOutputStream out,String value,int limit)throws Exception {byte[] bytes=value.getBytes(StandardCharsets.UTF_8);if(bytes.length>limit)throw new IOException();out.writeInt(bytes.length);out.write(bytes);}
  static String text(DataInputStream in,int limit)throws Exception {int size=in.readInt();if(size<0||size>limit)throw new IOException();byte[] bytes=new byte[size];in.readFully(bytes);return StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)).toString();}
  static ParcelFileDescriptor write(NetworkSharePreparation.Frozen frozen,Executor io)throws Exception {
    ParcelFileDescriptor[] pipe=ParcelFileDescriptor.createReliablePipe();try{io.execute(()->{try(DataOutputStream out=new DataOutputStream(new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1]))){
      out.writeInt(MAGIC);text(out,frozen.request.json().toString(),8192);text(out,frozen.name,1024);
      for(int i=0;i<2;i++){NetworkSharePreparation.Part part=frozen.parts[i];out.writeBoolean(part!=null);if(part==null)continue;
        text(out,part.selection==null?"null":NetworkShareJson.encode(part.selection,1024*1024),1024*1024);text(out,part.failure==null?"null":part.failure.json().toString(),1024);
        if(part.bytes==null)out.writeInt(-1);else{if(part.bytes.length>NetworkSharePreparation.SOURCE_LIMIT)throw new IOException();out.writeInt(part.bytes.length);out.write(part.bytes);}
      }out.flush();
    }catch(Exception failed){try{pipe[1].closeWithError("分享快照不可读取");}catch(Exception ignored){}}});return pipe[0];}catch(Exception failed){pipe[0].close();pipe[1].close();throw failed;}
  }
  static NetworkSharePreparation.Frozen read(ParcelFileDescriptor descriptor,NetworkSharePreparation.Request expected)throws Exception {
    try(DataInputStream in=new DataInputStream(new ParcelFileDescriptor.AutoCloseInputStream(descriptor))){
      if(in.readInt()!=MAGIC)throw new IOException();NetworkSharePreparation.Request actual=NetworkSharePreparation.readRequest(new JSONObject(text(in,8192)));if(!actual.same(expected))throw new IOException();
      NetworkSharePreparation.Frozen result=new NetworkSharePreparation.Frozen(expected,text(in,1024));
      for(int i=0;i<2;i++){boolean has=in.readBoolean();if(has!=expected.wants(i))throw new IOException();if(!has)continue;
        String selection=text(in,1024*1024),failure=text(in,1024);JSONObject part="null".equals(selection)?null:(JSONObject)NetworkShareJson.decode(selection,1024*1024);NetworkSharePreparation.Failure problem="null".equals(failure)?null:NetworkSharePreparation.Failure.read(new JSONObject(failure));
        int length=in.readInt();if(length< -1||length>NetworkSharePreparation.SOURCE_LIMIT)throw new IOException();byte[] bytes=null;if(length>=0){bytes=new byte[length];in.readFully(bytes);if(part==null||!NetworkShareSnapshot.hash(bytes).equals(part.optString("payloadHash")))throw new IOException();}
        if(problem==null&&part==null)throw new IOException();if(part!=null&&(!NetworkShareSelection.owner(part).equals(expected.owner)||!expected.version.equals(part.optString("version"))||!(i==0?"entry":"exit").equals(part.optString("side"))))throw new IOException();result.parts[i]=new NetworkSharePreparation.Part(part,bytes,problem);
      }if(in.read()!=-1)throw new IOException();return result;
    }catch(NetworkSharePreparation.Failure typed){throw typed;}catch(Exception unavailable){throw NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","");}
  }
}
