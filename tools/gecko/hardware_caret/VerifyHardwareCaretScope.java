package org.mozilla.geckoview;

import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.atomic.*;

/** JVM scope/graph verification only; Android editing acceptance is separate. */
public final class VerifyHardwareCaretScope {
  static int checks;
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks++;}
  static void ready(){PocketSynthesizedInsertionScope.markDown(true);}
  static int result(){ready();return PocketSynthesizedInsertionScope.offset(1);}
  static void under(Runnable body){int[] previous=PocketSynthesizedInsertionScope.enter();try{body.run();}finally{PocketSynthesizedInsertionScope.exit(previous);}}
  static boolean predicate(int start,int end,int shadowStart,int shadowEnd,int length){return start==end&&shadowStart==shadowEnd&&start==shadowStart+PocketSynthesizedInsertionScope.offset(length);}
  static void actualEarlyReturns()throws Exception{
    Class<?> editableClass=Class.forName("org.mozilla.geckoview.GeckoEditable");
    Class<?> unsafeClass=Class.forName("sun.misc.Unsafe");Field field=unsafeClass.getDeclaredField("theUnsafe");field.setAccessible(true);
    Object editable=unsafeClass.getMethod("allocateInstance",Class.class).invoke(field.get(null),editableClass);
    Class<?> actionClass=Class.forName("org.mozilla.geckoview.GeckoEditable$Action");
    Method newAction=actionClass.getDeclaredMethod("newReplaceText",CharSequence.class,int.class,int.class);newAction.setAccessible(true);
    Method synthetic=editableClass.getDeclaredMethod("sendCharKeyEvents",actionClass);synthetic.setAccessible(true);
    Object multi=newAction.invoke(null,"paste",22,22);
    under(()->{try{synthetic.invoke(editable,multi);check("Real SDK multi-character return remains ineligible",PocketSynthesizedInsertionScope.offset(1)==1);}catch(ReflectiveOperationException error){throw new AssertionError(error);}});
    Class<?> spannable=Class.forName("android.text.Spannable");
    Object styled=Proxy.newProxyInstance(spannable.getClassLoader(),new Class<?>[]{spannable},(proxy,method,args)->{
      switch(method.getName()){
        case "length":return 1;case "nextSpanTransition":return 0;case "toString":return "a";
        case "charAt":return 'a';case "subSequence":return "a";case "equals":return proxy==args[0];case "hashCode":return System.identityHashCode(proxy);
        default:throw new AssertionError("Unexpected styled early-return query: "+method);
      }
    });
    Object rich=newAction.invoke(null,styled,22,22);
    under(()->{try{synthetic.invoke(editable,rich);check("Real SDK styled return remains ineligible",PocketSynthesizedInsertionScope.offset(1)==1);}catch(ReflectiveOperationException error){throw new AssertionError(error);}});
    // android.jar's KeyCharacterMap.load throws its standard RuntimeException.
    // The original SDK catches it and returns no synthesized keys.
    Object single=newAction.invoke(null,"a",22,22);
    under(()->{try{synthetic.invoke(editable,single);check("Real SDK unavailable key map remains ineligible",PocketSynthesizedInsertionScope.offset(1)==1);}catch(ReflectiveOperationException error){throw new AssertionError(error);}});
  }
  public static void main(String[] args)throws Exception{
    Class.forName("org.mozilla.geckoview.GeckoEditable",false,VerifyHardwareCaretScope.class.getClassLoader()).getDeclaredMethods();
    check("Unscoped call keeps original offset",result()==1);
    check("Unscoped mark does not become a later action",PocketSynthesizedInsertionScope.offset(1)==1);
    under(()->{
      check("New noncomposition action is initially ineligible",PocketSynthesizedInsertionScope.offset(1)==1);
      PocketSynthesizedInsertionScope.markDown(false);check("Keyup alone remains ineligible",PocketSynthesizedInsertionScope.offset(1)==1);
      check("One successful nonmodifier synthesized down changes operand",result()==-1);
      check("Offset eligibility is consumed once",PocketSynthesizedInsertionScope.offset(1)==1);
      ready();check("Multi-character operand retains original predicate",PocketSynthesizedInsertionScope.offset(5)==5);
      check("Multi-character operand consumed eligibility",PocketSynthesizedInsertionScope.offset(1)==1);
      ready();check("Empty replacement retains original predicate",PocketSynthesizedInsertionScope.offset(0)==0);
      ready();check("Surrogate pair retains original predicate",PocketSynthesizedInsertionScope.offset(2)==2);
      ready();PocketSynthesizedInsertionScope.markDown(false);check("Successful down survives keyup",PocketSynthesizedInsertionScope.offset(1)==-1);
      ready();ready();check("Two successful down calls preserve dead-key path",PocketSynthesizedInsertionScope.offset(1)==1);
      for(int i=0;i<100;i++)ready();check("Count saturates instead of wrapping into eligibility",PocketSynthesizedInsertionScope.offset(1)==1);
      ready();under(()->check("Nested action cannot inherit preceding down",PocketSynthesizedInsertionScope.offset(1)==1));
      check("Nested action preserves outer down",PocketSynthesizedInsertionScope.offset(1)==-1);
      ready();under(()->check("Nested eligible action consumes its own frame",result()==-1));
      check("Nested eligible consumption preserves outer frame",PocketSynthesizedInsertionScope.offset(1)==-1);
      RuntimeException same=new RuntimeException("original");ready();
      try{under(()->{ready();throw same;});throw new AssertionError("Missing exception");}catch(RuntimeException value){check("Nested exception propagated unchanged",value==same);}
      check("Exceptional nested action restores outer frame",PocketSynthesizedInsertionScope.offset(1)==-1);
      under(()->{ready();check("Collapsed forward insertion satisfies documented predicate",predicate(22,22,23,23,1));});
      under(()->{ready();check("Selection replacement remains explicit",!predicate(22,25,23,23,1));});
      under(()->{ready();check("Reversed selection replacement remains explicit",!predicate(25,22,23,23,1));});
      under(()->{ready();check("Noncollapsed shadow selection remains explicit",!predicate(22,22,23,25,1));});
      under(()->{ready();check("Unchanged shadow caret does not falsely skip selection",!predicate(22,22,22,22,1));});
      under(()->{ready();check("Different shadow insertion position remains explicit",!predicate(22,22,25,25,1));});
    });
    check("Completed action does not leak to unscoped call",result()==1);
    under(()->{ready();});
    under(()->check("New action after unused prior eligibility starts empty",PocketSynthesizedInsertionScope.offset(1)==1));
    under(()->check("Single down admitted identically for an IC batch",result()==-1));
    under(()->check("Single down admitted identically for nonbatch hardware",result()==-1));
    AtomicInteger calls=new AtomicInteger();under(calls::incrementAndGet);check("Action body executes exactly once",calls.get()==1);
    Error originalError=new AssertionError("same error");try{under(()->{ready();throw originalError;});throw new AssertionError("Missing error");}catch(Error error){check("Original Error propagated unchanged",error==originalError);}
    check("Error clears the outermost frame",result()==1);
    AtomicReference<Throwable> failure=new AtomicReference<>();AtomicInteger parallel=new AtomicInteger();Thread[] workers=new Thread[4];
    for(int n=0;n<workers.length;n++){workers[n]=new Thread(()->{try{for(int i=0;i<100;i++){under(()->{if(result()!=-1)throw new AssertionError("Missing frame");parallel.incrementAndGet();});if(result()!=1)throw new AssertionError("Leaked frame");}}catch(Throwable error){failure.compareAndSet(null,error);}});workers[n].start();}
    for(Thread worker:workers)worker.join();check("Concurrent input threads do not share eligibility",failure.get()==null&&parallel.get()==400);
    actualEarlyReturns();
    check("Real SDK early returns leave no outer scope",result()==1);
    System.out.println("{\"jvmBytecodeVerification\":true,\"scopeChecks\":"+checks+",\"concurrentRuns\":400,\"actualSdkGuardedEarlyReturns\":3,\"singleUseEligibility\":true,\"nestingAndExceptionCleanup\":true,\"perActionOnly\":true,\"extraBatchRestriction\":false,\"actualAndroidExecution\":false}");
  }
}
