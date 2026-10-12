import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Pinned graph plus per-action synthesized insertion; original dispatch/ACK calls remain. */
public final class TransformHardwareCaret implements Opcodes {
  static final String EDIT="org/mozilla/geckoview/GeckoEditable";
  static final String ACTION=EDIT+"$Action", CHILD="org/mozilla/gecko/IGeckoEditableChild";
  static final String SCOPE="org/mozilla/geckoview/PocketSynthesizedInsertionScope";
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
    for(MethodNode m:c.methods)require(addedCalls(m,"enter")==0,"Already modified SDK");
    MethodNode synthetic=one(c,"sendCharKeyEvents","(L"+ACTION+";)V");
    MethodNode perform=one(c,"icPerformAction","(L"+ACTION+";)V");
    List<AbstractInsnNode> syntheticOriginal=graph(synthetic),performOriginal=graph(perform);
    // Existing filters decide which keys are emitted. Mark eligibility after,
    // never before, the one original dispatch. A thrown dispatch stays ineligible.
    call(synthetic,"android/view/KeyEvent","isModifierKey","(I)Z");
    MethodInsnNode dispatched=call(synthetic,EDIT,"onKeyEvent","(L"+CHILD+";Landroid/view/KeyEvent;IIZ)V");
    AbstractInsnNode previous=previous(dispatched);require(previous.getOpcode()==ICONST_1&&previous(previous).getOpcode()==ICONST_0,"Synthesized event flag changed");
    AbstractInsnNode action=previous(previous(previous));require(action instanceof MethodInsnNode&&((MethodInsnNode)action).owner.equals("android/view/KeyEvent")&&((MethodInsnNode)action).name.equals("getAction"),"Actual event action producer changed");
    AbstractInsnNode event=previous(action);require(event instanceof VarInsnNode&&event.getOpcode()==ALOAD&&((VarInsnNode)event).var==6,"Event local changed");
    InsnList marker=new InsnList();LabelNode notDown=new LabelNode(),haveDown=new LabelNode();
    marker.add(new VarInsnNode(ALOAD,6));marker.add(new MethodInsnNode(INVOKEVIRTUAL,"android/view/KeyEvent","getAction","()I",false));marker.add(new JumpInsnNode(IFNE,notDown));marker.add(new InsnNode(ICONST_1));marker.add(new JumpInsnNode(GOTO,haveDown));marker.add(notDown);marker.add(new InsnNode(ICONST_0));marker.add(haveDown);
    marker.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"markDown","(Z)V",false));synthetic.instructions.insert(dispatched,marker);
    // Enter only after the original composition path has returned/broken.
    // The action, original dispatch and its shadow predicate share one frame;
    // normal and exceptional exits restore an outer reentrant action's frame.
    MethodInsnNode synthCall=call(perform,EDIT,"sendCharKeyEvents","(L"+ACTION+";)V");
    AbstractInsnNode arg=previous(synthCall),receiver=previous(arg);
    require(arg instanceof VarInsnNode&&arg.getOpcode()==ALOAD&&((VarInsnNode)arg).var==1&&receiver instanceof VarInsnNode&&receiver.getOpcode()==ALOAD&&((VarInsnNode)receiver).var==0,"Synthesis branch producer changed");
    List<MethodInsnNode> replacements=new ArrayList<>();for(AbstractInsnNode n:perform.instructions)if(n instanceof MethodInsnNode){MethodInsnNode m=(MethodInsnNode)n;if(m.owner.equals(CHILD)&&m.name.equals("onImeReplaceText")&&m.desc.equals("(IILjava/lang/String;)V"))replacements.add(m);}
    require(replacements.size()==2,"Original replacement paths changed");
    MethodInsnNode originalReplace=replacements.get(1);
    int priorFrame=perform.maxLocals++,throwable=perform.maxLocals++;
    LabelNode actionStart=new LabelNode(),actionEnd=new LabelNode(),caught=new LabelNode();
    InsnList enter=new InsnList();enter.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"enter","()[I",false));enter.add(new VarInsnNode(ASTORE,priorFrame));enter.add(actionStart);perform.instructions.insertBefore(receiver,enter);
    InsnList leave=new InsnList();leave.add(actionEnd);leave.add(new VarInsnNode(ALOAD,priorFrame));leave.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"exit","([I)V",false));perform.instructions.insert(originalReplace,leave);
    InsnList cleanup=new InsnList();cleanup.add(caught);cleanup.add(new VarInsnNode(ASTORE,throwable));cleanup.add(new VarInsnNode(ALOAD,priorFrame));cleanup.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"exit","([I)V",false));cleanup.add(new VarInsnNode(ALOAD,throwable));cleanup.add(new InsnNode(ATHROW));perform.instructions.add(cleanup);
    perform.tryCatchBlocks.add(new TryCatchBlockNode(actionStart,actionEnd,caught,null));
    AbstractInsnNode addition=null;for(AbstractInsnNode n:perform.instructions)if(n.getOpcode()==IADD){require(addition==null,"Predicate addition not unique");addition=n;}require(addition!=null,"Missing original predicate addition");
    AbstractInsnNode length=previous(addition);require(length instanceof MethodInsnNode&&((MethodInsnNode)length).owner.equals("java/lang/String")&&((MethodInsnNode)length).name.equals("length")&&((MethodInsnNode)length).desc.equals("()I"),"Predicate length producer changed");
    InsnList offset=new InsnList();offset.add(new MethodInsnNode(INVOKESTATIC,SCOPE,"offset","(I)I",false));perform.instructions.insertBefore(addition,offset);
    preserved(synthetic,syntheticOriginal);preserved(perform,performOriginal);
    require(addedCalls(synthetic,"markDown")==1&&addedCalls(perform,"enter")==1&&addedCalls(perform,"exit")==2&&addedCalls(perform,"offset")==1,"Inserted recipe count mismatch");
    // No original method/field added, removed or renamed; only these two bodies.
    Frames writer=new Frames();c.accept(writer);Files.write(Paths.get(args[1]),writer.toByteArray());
    System.out.println("{\"processKeyWrapperCallsites\":0,\"perActionEnterCallsites\":1,\"normalAndExceptionalExitCallsites\":2,\"actualSyntheticDispatchMarkers\":1,\"predicateOffsetCallsites\":1,\"originalIaddPreserved\":true,\"originalInstructionsAndLabelsPreservedInOrder\":true,\"originalHandlerAndRunnablePostPreservedOnce\":true,\"originalDispatchAndAckCallsPreservedOnce\":true,\"changedMethodCount\":2,\"hardwareOnly\":false,\"perActionOnly\":true,\"extraBatchRestriction\":false,\"observerIncluded\":false}");
  }
}
