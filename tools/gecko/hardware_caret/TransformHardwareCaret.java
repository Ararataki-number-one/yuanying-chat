import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Pinned original graph plus narrow context; never changes original dispatch/ACK calls. */
public final class TransformHardwareCaret implements Opcodes {
  static final String EDIT="org/mozilla/geckoview/GeckoEditable";
  static final String ACTION=EDIT+"$Action", CHILD="org/mozilla/gecko/IGeckoEditableChild";
  static final String SCOPE="org/mozilla/geckoview/PocketHardwareCaretScope";
  static final String SHA="608461e22cae3ed19572aa43a0dc38d4926d48709bd456c91853935462f5fa54";
  static void require(boolean value,String message){if(!value)throw new IllegalStateException(message);}
  static String sha(byte[] value)throws Exception{StringBuilder out=new StringBuilder();for(byte x:MessageDigest.getInstance("SHA-256").digest(value))out.append(String.format(Locale.ROOT,"%02x",x&255));return out.toString();}
  static MethodNode one(ClassNode c,String name,String descriptor){MethodNode found=null;for(MethodNode m:c.methods)if(m.name.equals(name)){require(found==null&&m.desc.equals(descriptor),"Method overload/descriptor changed: "+name);found=m;}require(found!=null,"Missing method: "+name);return found;}
  static MethodInsnNode call(MethodNode method,String owner,String name,String descriptor){MethodInsnNode found=null;for(AbstractInsnNode n:method.instructions)if(n instanceof MethodInsnNode){MethodInsnNode m=(MethodInsnNode)n;if(m.owner.equals(owner)&&m.name.equals(name)&&m.desc.equals(descriptor)){require(found==null,"Callsite not unique: "+name);found=m;}}require(found!=null,"Missing callsite: "+name);return found;}
  static AbstractInsnNode previous(AbstractInsnNode n){do{n=n.getPrevious();}while(n!=null&&n.getOpcode()<0);return n;}
  static List<AbstractInsnNode> graph(MethodNode m){List<AbstractInsnNode> result=new ArrayList<>();for(AbstractInsnNode n:m.instructions)if(!(n instanceof FrameNode))result.add(n);return result;}
  static void preserved(MethodNode m,List<AbstractInsnNode> original){Iterator<AbstractInsnNode> remaining=graph(m).iterator();for(AbstractInsnNode expected:original){boolean found=false;while(remaining.hasNext())if(remaining.next()==expected){found=true;break;}require(found,"Original instruction or label was removed/reordered: "+m.name);}}
  static int addedCalls(MethodNode m,String name){int count=0;for(AbstractInsnNode n:m.instructions)if(n instanceof MethodInsnNode){MethodInsnNode c=(MethodInsnNode)n;if(c.owner.equals(SCOPE)&&c.name.equals(name))count++;}return count;}
  static final class Frames extends ClassWriter {
    final Map<String,ClassReader> cache=new HashMap<>();Frames(){super(COMPUTE_FRAMES|COMPUTE_MAXS);}
    ClassReader info(String name){return cache.computeIfAbsent(name,n->{try(InputStream in=ClassLoader.getSystemResourceAsStream(n+".class")){if(in==null)throw new IllegalStateException("Missing hierarchy: "+n);return new ClassReader(in);}catch(IOException e){throw new UncheckedIOException(e);}});}
    boolean assign(String parent,String child){if(parent.equals(child)||parent.equals("java/lang/Object"))return true;ClassReader c=info(child);for(String it:c.getInterfaces())if(assign(parent,it))return true;String s=c.getSuperName();return s!=null&&assign(parent,s);}
    @Override protected String getCommonSuperClass(String a,String b){if(assign(a,b))return a;if(assign(b,a))return b;if((info(a).getAccess()&ACC_INTERFACE)!=0||(info(b).getAccess()&ACC_INTERFACE)!=0)return "java/lang/Object";do{a=info(a).getSuperName();}while(!assign(a,b));return a;}
  }
  public static void main(String[] args)throws Exception {
    byte[] input=Files.readAllBytes(Paths.get(args[0]));require(sha(input).equals(SHA),"Pinned original SDK class changed");
    ClassNode c=new ClassNode();new ClassReader(input).accept(c,0);require(c.name.equals(EDIT),"Wrong class identity");
    for(MethodNode m:c.methods)require(addedCalls(m,"wrap")==0,"Already modified SDK");
    MethodNode process=one(c,"processKey","(Landroid/view/View;IILandroid/view/KeyEvent;)Z");
    MethodNode synthetic=one(c,"sendCharKeyEvents","(L"+ACTION+";)V");
    MethodNode perform=one(c,"icPerformAction","(L"+ACTION+";)V");
    List<AbstractInsnNode> processOriginal=graph(process),syntheticOriginal=graph(synthetic),performOriginal=graph(perform);
    MethodInsnNode post=call(process,EDIT,"postToInputConnection","(Ljava/lang/Runnable;)V");
    require(previous(post) instanceof MethodInsnNode&&((MethodInsnNode)previous(post)).owner.equals(EDIT+"$12")&&((MethodInsnNode)previous(post)).name.equals("<init>"),"Original Runnable construction changed");
    InsnList wrapper=new InsnList();
    wrapper.add(new VarInsnNode(ALOAD,4));wrapper.add(new MethodInsnNode(INVOKEVIRTUAL,"android/view/KeyEvent","getSource","()I",false));
    wrapper.add(new VarInsnNode(ALOAD,4));wrapper.add(new MethodInsnNode(INVOKEVIRTUAL,"android/view/KeyEvent","getFlags","()I",false));
    wrapper.add(new VarInsnNode(ILOAD,2));wrapper.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"wrap","(Ljava/lang/Runnable;III)Ljava/lang/Runnable;",false));
    process.instructions.insertBefore(post,wrapper);
    // Existing filters decide which keys are emitted. Mark eligibility after,
    // never before, the one original dispatch. A thrown dispatch stays ineligible.
    call(synthetic,"android/view/KeyEvent","isModifierKey","(I)Z");
    MethodInsnNode dispatched=call(synthetic,EDIT,"onKeyEvent","(L"+CHILD+";Landroid/view/KeyEvent;IIZ)V");
    AbstractInsnNode previous=previous(dispatched);require(previous.getOpcode()==ICONST_1&&previous(previous).getOpcode()==ICONST_0,"Synthesized event flag changed");
    AbstractInsnNode action=previous(previous(previous));require(action instanceof MethodInsnNode&&((MethodInsnNode)action).owner.equals("android/view/KeyEvent")&&((MethodInsnNode)action).name.equals("getAction"),"Actual event action producer changed");
    AbstractInsnNode event=previous(action);require(event instanceof VarInsnNode&&event.getOpcode()==ALOAD&&((VarInsnNode)event).var==6,"Event local changed");
    InsnList reset=new InsnList();reset.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"beginSynthetic","()V",false));synthetic.instructions.insert(reset);
    InsnList marker=new InsnList();LabelNode notDown=new LabelNode(),haveDown=new LabelNode();
    marker.add(new VarInsnNode(ALOAD,6));marker.add(new MethodInsnNode(INVOKEVIRTUAL,"android/view/KeyEvent","getAction","()I",false));marker.add(new JumpInsnNode(IFNE,notDown));marker.add(new InsnNode(ICONST_1));marker.add(new JumpInsnNode(GOTO,haveDown));marker.add(notDown);marker.add(new InsnNode(ICONST_0));marker.add(haveDown);
    marker.add(new VarInsnNode(ALOAD,0));marker.add(new FieldInsnNode(GETFIELD,EDIT,"mInBatchMode","Z"));marker.add(new InsnNode(ICONST_1));marker.add(new InsnNode(IXOR));marker.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"eligible","(ZZ)V",false));synthetic.instructions.insert(dispatched,marker);
    AbstractInsnNode addition=null;for(AbstractInsnNode n:perform.instructions)if(n.getOpcode()==IADD){require(addition==null,"Predicate addition not unique");addition=n;}require(addition!=null,"Missing original predicate addition");
    AbstractInsnNode length=previous(addition);require(length instanceof MethodInsnNode&&((MethodInsnNode)length).owner.equals("java/lang/String")&&((MethodInsnNode)length).name.equals("length")&&((MethodInsnNode)length).desc.equals("()I"),"Predicate length producer changed");
    InsnList offset=new InsnList();offset.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"offset","(I)I",false));perform.instructions.insertBefore(addition,offset);
    preserved(process,processOriginal);preserved(synthetic,syntheticOriginal);preserved(perform,performOriginal);
    require(addedCalls(process,"wrap")==1&&addedCalls(synthetic,"beginSynthetic")==1&&addedCalls(synthetic,"eligible")==1&&addedCalls(perform,"offset")==1,"Inserted recipe count mismatch");
    // No original method/field added, removed or renamed; only these three bodies.
    Frames writer=new Frames();c.accept(writer);Files.write(Paths.get(args[1]),writer.toByteArray());
    System.out.println("{\"processKeyWrapperCallsites\":1,\"syntheticResetCallsites\":1,\"actualSyntheticDispatchMarkers\":1,\"predicateOffsetCallsites\":1,\"originalIaddPreserved\":true,\"originalInstructionsAndLabelsPreservedInOrder\":true,\"originalHandlerAndRunnablePostPreservedOnce\":true,\"originalDispatchAndAckCallsPreservedOnce\":true,\"changedMethodCount\":3,\"hardwareOnly\":true,\"observerIncluded\":false}");
  }
}
