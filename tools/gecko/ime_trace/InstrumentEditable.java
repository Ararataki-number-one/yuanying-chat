import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Inserts observations into the exact official class, preserving every original invoke. */
public final class InstrumentEditable implements Opcodes {
  static final String ACTION="org/mozilla/geckoview/GeckoEditable$Action";
  static final String EDIT="org/mozilla/geckoview/GeckoEditable",ASYNC=EDIT+"$AsyncText",TRACE="org/mozilla/geckoview/PocketGeckoEditableTrace",CHILD="org/mozilla/gecko/IGeckoEditableChild",HELPER="$pocketTracePrimitive";
  static void integer(InsnList i,int value){i.add(new LdcInsnNode(value));}
  static void callTrace(InsnList i,int code,int edge,int start,int end,int flags,int text){
    i.add(new VarInsnNode(ALOAD,0));integer(i,code);integer(i,edge);
    for(int v:new int[]{start,end,flags}){if(v<0)integer(i,-1);else i.add(new VarInsnNode(ILOAD,v));}
    if(text<0)integer(i,-1);else{i.add(new VarInsnNode(ALOAD,text));i.add(new MethodInsnNode(INVOKESTATIC,TRACE,"length","(Ljava/lang/CharSequence;)I",false));}
    i.add(new MethodInsnNode(INVOKESPECIAL,EDIT,HELPER,"(IIIIII)V",false));
  }
  static MethodNode observer(){
    MethodNode m=new MethodNode(ACC_PRIVATE,HELPER,"(IIIIII)V",null,null);InsnList i=m.instructions;
    LabelNode end=new LabelNode(),record=new LabelNode(),start=new LabelNode(),finish=new LabelNode(),caught=new LabelNode(),after=new LabelNode();
    i.add(new MethodInsnNode(INVOKESTATIC,TRACE,"enabled","()Z",false));i.add(new JumpInsnNode(IFEQ,end));
    for(int n=7;n<=11;n++){integer(i,-1);i.add(new VarInsnNode(ISTORE,n));}
    i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mIcRunHandler","Landroid/os/Handler;"));i.add(new JumpInsnNode(IFNULL,record));
    i.add(new MethodInsnNode(INVOKESTATIC,"android/os/Looper","myLooper","()Landroid/os/Looper;",false));i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mIcRunHandler","Landroid/os/Handler;"));i.add(new MethodInsnNode(INVOKEVIRTUAL,"android/os/Handler","getLooper","()Landroid/os/Looper;",false));i.add(new JumpInsnNode(IF_ACMPNE,record));
    // Current text mutations already synchronize on AsyncText. Read only while
    // holding that same monitor; shadow text is read only on its original IC thread.
    i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mText","L"+ASYNC+";"));i.add(new InsnNode(DUP));i.add(new VarInsnNode(ASTORE,13));i.add(new InsnNode(MONITORENTER));i.add(start);
    for(int n=7;n<=8;n++){i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mText","L"+ASYNC+";"));i.add(new MethodInsnNode(INVOKEVIRTUAL,ASYNC,"getCurrentText","()Landroid/text/Spanned;",false));i.add(new MethodInsnNode(INVOKESTATIC,"android/text/Selection",n==7?"getSelectionStart":"getSelectionEnd","(Ljava/lang/CharSequence;)I",false));i.add(new VarInsnNode(ISTORE,n));}
    i.add(new VarInsnNode(ALOAD,13));i.add(new InsnNode(MONITOREXIT));i.add(finish);i.add(new JumpInsnNode(GOTO,after));i.add(caught);i.add(new VarInsnNode(ASTORE,14));i.add(new VarInsnNode(ALOAD,13));i.add(new InsnNode(MONITOREXIT));i.add(new VarInsnNode(ALOAD,14));i.add(new InsnNode(ATHROW));i.add(after);
    for(int n=9;n<=10;n++){i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mText","L"+ASYNC+";"));i.add(new MethodInsnNode(INVOKEVIRTUAL,ASYNC,"getShadowText","()Landroid/text/Spanned;",false));i.add(new MethodInsnNode(INVOKESTATIC,"android/text/Selection",n==9?"getSelectionStart":"getSelectionEnd","(Ljava/lang/CharSequence;)I",false));i.add(new VarInsnNode(ISTORE,n));}
    i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mActions","Ljava/util/concurrent/ConcurrentLinkedQueue;"));i.add(new MethodInsnNode(INVOKEVIRTUAL,"java/util/concurrent/ConcurrentLinkedQueue","size","()I",false));i.add(new VarInsnNode(ISTORE,11));
    i.add(record);
    i.add(new VarInsnNode(ALOAD,0));i.add(new FieldInsnNode(GETFIELD,EDIT,"mActions","Ljava/util/concurrent/ConcurrentLinkedQueue;"));i.add(new MethodInsnNode(INVOKEVIRTUAL,"java/util/concurrent/ConcurrentLinkedQueue","size","()I",false));i.add(new VarInsnNode(ISTORE,11));
    integer(i,0);i.add(new VarInsnNode(ISTORE,15));LabelNode noOriginal=new LabelNode(),normalShift=new LabelNode(),shifted=new LabelNode();i.add(new VarInsnNode(ILOAD,5));i.add(new JumpInsnNode(IFLT,noOriginal));i.add(new VarInsnNode(ILOAD,1));integer(i,10);i.add(new JumpInsnNode(IF_ICMPEQ,normalShift));i.add(new VarInsnNode(ILOAD,1));integer(i,11);i.add(new JumpInsnNode(IF_ICMPEQ,normalShift));i.add(new VarInsnNode(ILOAD,5));integer(i,8);i.add(new InsnNode(ISHL));i.add(new JumpInsnNode(GOTO,shifted));i.add(normalShift);i.add(new VarInsnNode(ILOAD,5));integer(i,5);i.add(new InsnNode(ISHL));i.add(shifted);i.add(new VarInsnNode(ISTORE,15));i.add(noOriginal);
    String[] bools={"mNeedSync","mInBatchMode",null,"mIgnoreSelectionChange","mLastTextChangeReplacedSelection"};
    for(int bit=0;bit<bools.length;bit++){LabelNode noBit=new LabelNode();i.add(new VarInsnNode(ALOAD,0));if(bools[bit]==null){i.add(new FieldInsnNode(GETFIELD,EDIT,"mActions","Ljava/util/concurrent/ConcurrentLinkedQueue;"));i.add(new MethodInsnNode(INVOKEVIRTUAL,"java/util/concurrent/ConcurrentLinkedQueue","isEmpty","()Z",false));}else i.add(new FieldInsnNode(GETFIELD,EDIT,bools[bit],"Z"));i.add(new JumpInsnNode(IFEQ,noBit));i.add(new VarInsnNode(ILOAD,15));integer(i,1<<bit);i.add(new InsnNode(IOR));i.add(new VarInsnNode(ISTORE,15));i.add(noBit);}
    for(int n=1;n<=11;n++)i.add(new VarInsnNode(ILOAD,n==5?15:n));i.add(new MethodInsnNode(INVOKESTATIC,TRACE,"record","(IIIIIIIIIII)V",false));i.add(end);i.add(new InsnNode(RETURN));m.tryCatchBlocks.add(new TryCatchBlockNode(start,finish,caught,null));m.maxLocals=16;return m;
  }
  static void actionCall(InsnList i,int code,int edge){i.add(new VarInsnNode(ALOAD,0));integer(i,code);integer(i,edge);i.add(new VarInsnNode(ALOAD,1));i.add(new MethodInsnNode(INVOKESPECIAL,EDIT,"$pocketTraceAction","(IIL"+ACTION+";)V",false));}
  static MethodNode actionObserver(){MethodNode m=new MethodNode(ACC_PRIVATE,"$pocketTraceAction","(IIL"+ACTION+";)V",null,null);InsnList i=m.instructions;for(int n=4;n<=7;n++){integer(i,-1);i.add(new VarInsnNode(ISTORE,n));}LabelNode done=new LabelNode();i.add(new VarInsnNode(ALOAD,3));i.add(new JumpInsnNode(IFNULL,done));String[] fields={"mStart","mEnd","mType"};for(int n=4;n<=6;n++){i.add(new VarInsnNode(ALOAD,3));i.add(new FieldInsnNode(GETFIELD,ACTION,fields[n-4],"I"));i.add(new VarInsnNode(ISTORE,n));}i.add(new VarInsnNode(ALOAD,3));i.add(new FieldInsnNode(GETFIELD,ACTION,"mSequence","Ljava/lang/CharSequence;"));i.add(new MethodInsnNode(INVOKESTATIC,TRACE,"length","(Ljava/lang/CharSequence;)I",false));i.add(new VarInsnNode(ISTORE,7));i.add(done);i.add(new VarInsnNode(ALOAD,0));for(int n:new int[]{1,2,4,5,6,7})i.add(new VarInsnNode(ILOAD,n));i.add(new MethodInsnNode(INVOKESPECIAL,EDIT,HELPER,"(IIIIII)V",false));i.add(new InsnNode(RETURN));m.maxLocals=8;return m;}
  static final class Frames extends ClassWriter {
    final Map<String,ClassReader> cache=new HashMap<>();Frames(){super(COMPUTE_FRAMES|COMPUTE_MAXS);}
    ClassReader info(String name){return cache.computeIfAbsent(name,n->{try(InputStream in=ClassLoader.getSystemResourceAsStream(n+".class")){if(in==null)throw new IllegalStateException("Missing class hierarchy: "+n);return new ClassReader(in);}catch(IOException e){throw new UncheckedIOException(e);}});}
    boolean assign(String parent,String child){if(parent.equals(child)||parent.equals("java/lang/Object"))return true;ClassReader c=info(child);for(String it:c.getInterfaces())if(assign(parent,it))return true;String s=c.getSuperName();return s!=null&&assign(parent,s);}
    @Override protected String getCommonSuperClass(String a,String b){if(assign(a,b))return a;if(assign(b,a))return b;if((info(a).getAccess()&ACC_INTERFACE)!=0||(info(b).getAccess()&ACC_INTERFACE)!=0)return "java/lang/Object";do{a=info(a).getSuperName();}while(!assign(a,b));return a;}
  }
  public static void main(String[] args)throws Exception {
    ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(Paths.get(args[0]))).accept(c,0);if(!c.name.equals(EDIT))throw new IllegalStateException("Wrong official class");
    int incoming=0,replaces=0,compositions=0;
    for(MethodNode m:c.methods){
      if(m.name.equals(HELPER))throw new IllegalStateException("SDK already instrumented");
      int code=0,s=-1,e=-1,f=-1,t=-1;
      if(m.name.equals("onTextChange")&&m.desc.equals("(Landroid/os/IBinder;Ljava/lang/CharSequence;IIZ)V")){code=10;s=3;e=4;f=5;t=2;}
      if(m.name.equals("onSelectionChange")&&m.desc.equals("(Landroid/os/IBinder;IIZ)V")){code=11;s=2;e=3;f=4;}
      if(m.name.equals("notifyIME")&&m.desc.equals("(L"+CHILD+";I)V")){code=12;s=2;}
      if(m.name.equals("icSyncShadowText")&&m.desc.equals("()V"))code=13;
      if(m.name.equals("geckoActionReply")&&m.desc.equals("(L"+ACTION+";)V"))code=18;
      if(m.name.equals("icOfferAction")&&m.desc.equals("(L"+ACTION+";)V"))code=19;
      AbstractInsnNode[] original=m.instructions.toArray();
      if(code!=0){incoming++;InsnList entry=new InsnList();if(code>=18)actionCall(entry,code,0);else callTrace(entry,code,0,s,e,f,t);m.instructions.insert(entry);for(AbstractInsnNode n:original)if(n.getOpcode()==RETURN||n.getOpcode()==ATHROW){InsnList leave=new InsnList();if(code>=18)actionCall(leave,code,n.getOpcode()==ATHROW?2:1);else callTrace(leave,code,n.getOpcode()==ATHROW?2:1,s,e,f,t);m.instructions.insertBefore(n,leave);}}
      for(AbstractInsnNode n:original)if(n instanceof MethodInsnNode){MethodInsnNode invoke=(MethodInsnNode)n;if(!invoke.owner.equals(CHILD))continue;
        boolean replace=invoke.name.equals("onImeReplaceText")&&invoke.desc.equals("(IILjava/lang/String;)V"),compose=invoke.name.equals("onImeUpdateComposition")&&invoke.desc.equals("(III)V");if(!replace&&!compose)continue;
        if(replace)replaces++;else compositions++;int base=m.maxLocals;m.maxLocals+=4;InsnList pre=new InsnList();pre.add(new VarInsnNode(replace?ASTORE:ISTORE,base+3));pre.add(new VarInsnNode(ISTORE,base+2));pre.add(new VarInsnNode(ISTORE,base+1));pre.add(new VarInsnNode(ASTORE,base));callTrace(pre,replace?14:15,0,base+1,base+2,replace?-1:base+3,replace?base+3:-1);pre.add(new VarInsnNode(ALOAD,base));pre.add(new VarInsnNode(ILOAD,base+1));pre.add(new VarInsnNode(ILOAD,base+2));pre.add(new VarInsnNode(replace?ALOAD:ILOAD,base+3));m.instructions.insertBefore(n,pre);InsnList post=new InsnList();callTrace(post,replace?14:15,1,base+1,base+2,replace?-1:base+3,replace?base+3:-1);m.instructions.insert(n,post);
      }
    }
    if(incoming!=6||replaces!=2||compositions!=2)throw new IllegalStateException("Official callsite shape changed: "+incoming+","+replaces+","+compositions);
    c.methods.add(observer());c.methods.add(actionObserver());Frames writer=new Frames();c.accept(writer);Files.write(Paths.get(args[1]),writer.toByteArray());System.out.println("{\"incomingMethods\":6,\"replaceCallsites\":2,\"compositionCallsites\":2,\"diagnosticOnly\":true}");
  }
}
