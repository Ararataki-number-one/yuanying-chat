package org.mozilla.geckoview;

import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.atomic.*;

/** JVM scope/graph verification only; Android editing acceptance is separate. */
public final class VerifyHardwareCaretScope {
  static int checks;
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks++;}
  static void ready(){PocketHardwareCaretScope.beginSynthetic();PocketHardwareCaretScope.eligible(true,true);}
  static int result(){ready();return PocketHardwareCaretScope.offset(1);}
  static void under(int source,int flags,int action,Runnable body){PocketHardwareCaretScope.wrap(body,source,flags,action).run();}
  static void neutral(String name,int source,int flags,int action){under(source,flags,action,()->check(name,result()==1));}
  static void actualEarlyReturns()throws Exception{
    Class<?> editableClass=Class.forName("org.mozilla.geckoview.GeckoEditable");
    Class<?> unsafeClass=Class.forName("sun.misc.Unsafe");Field field=unsafeClass.getDeclaredField("theUnsafe");field.setAccessible(true);
    Object editable=unsafeClass.getMethod("allocateInstance",Class.class).invoke(field.get(null),editableClass);
    Class<?> actionClass=Class.forName("org.mozilla.geckoview.GeckoEditable$Action");
    Method newAction=actionClass.getDeclaredMethod("newReplaceText",CharSequence.class,int.class,int.class);newAction.setAccessible(true);
    Method synthetic=editableClass.getDeclaredMethod("sendCharKeyEvents",actionClass);synthetic.setAccessible(true);
    Object multi=newAction.invoke(null,"paste",22,22);
    under(257,0,0,()->{try{ready();synthetic.invoke(editable,multi);check("Real transformed SDK multi-character early return clears eligibility",PocketHardwareCaretScope.offset(1)==1);}catch(ReflectiveOperationException error){throw new AssertionError(error);}});
    Class<?> spannable=Class.forName("android.text.Spannable");
    Object styled=Proxy.newProxyInstance(spannable.getClassLoader(),new Class<?>[]{spannable},(proxy,method,args)->{
      switch(method.getName()){
        case "length":return 1;case "nextSpanTransition":return 0;case "toString":return "a";
        case "charAt":return 'a';case "subSequence":return "a";case "equals":return proxy==args[0];case "hashCode":return System.identityHashCode(proxy);
        default:throw new AssertionError("Unexpected styled early-return query: "+method);
      }
    });
    Object rich=newAction.invoke(null,styled,22,22);
    under(257,0,0,()->{try{ready();synthetic.invoke(editable,rich);check("Real transformed SDK styled early return clears eligibility",PocketHardwareCaretScope.offset(1)==1);}catch(ReflectiveOperationException error){throw new AssertionError(error);}});
    // android.jar's KeyCharacterMap.load throws its standard RuntimeException.
    // The actual original SDK catches it and returns no synthesized keys.
    Object single=newAction.invoke(null,"a",22,22);
    under(257,0,0,()->{try{ready();synthetic.invoke(editable,single);check("Real SDK unavailable key-map path does not become eligible",PocketHardwareCaretScope.offset(1)==1);}catch(ReflectiveOperationException error){throw new AssertionError(error);}});
  }
  public static void main(String[] args)throws Exception{
    Class.forName("org.mozilla.geckoview.GeckoEditable",false,VerifyHardwareCaretScope.class.getClassLoader()).getDeclaredMethods();
    check("Unscoped soft-IME calls keep original offset",result()==1);
    neutral("FLAG_SOFT_KEYBOARD excluded",257,2,0);
    neutral("Keyboard ACTION_UP excluded",257,0,1);
    neutral("Keyboard ACTION_MULTIPLE excluded",257,0,2);
    neutral("Touchscreen source excluded",0x1002,0,0);
    neutral("Unknown source excluded",0,0,0);
    neutral("Non-keyboard source with same class bit excluded",0x201,0,0);
    under(257,0,0,()->{
      check("Hardware without actual synthesized down remains original",PocketHardwareCaretScope.offset(1)==1);
      PocketHardwareCaretScope.eligible(false,true);check("Synthesized keyup alone remains original",PocketHardwareCaretScope.offset(1)==1);
      PocketHardwareCaretScope.eligible(true,false);check("IME batch is never eligible",PocketHardwareCaretScope.offset(1)==1);
      ready();check("Actual nonbatch hardware synthesized down uses forward predicate",PocketHardwareCaretScope.offset(1)==-1);
      check("Eligibility is consumed exactly once",PocketHardwareCaretScope.offset(1)==1);
      ready();check("Multi-character predicate operand remains original",PocketHardwareCaretScope.offset(5)==5);
      check("Multi-character operand still consumes stale eligibility",PocketHardwareCaretScope.offset(1)==1);
      ready();check("Empty predicate operand remains original",PocketHardwareCaretScope.offset(0)==0);
      ready();PocketHardwareCaretScope.beginSynthetic();check("Next failed synthesis attempt resets eligibility",PocketHardwareCaretScope.offset(1)==1);
      ready();PocketHardwareCaretScope.eligible(false,true);check("Keyup does not erase successful preceding synthesized down",PocketHardwareCaretScope.offset(1)==-1);
      ready();PocketHardwareCaretScope.eligible(true,true);check("Multiple non-modifier down events retain original dead-key predicate",PocketHardwareCaretScope.offset(1)==1);
      ready();PocketHardwareCaretScope.eligible(true,false);check("A later batched down invalidates the entire synthesis attempt",PocketHardwareCaretScope.offset(1)==1);
      ready();under(257,2,0,()->check("Nested soft input cannot inherit hardware eligibility",result()==1));
      check("Nested soft input preserves the outer hardware frame",PocketHardwareCaretScope.offset(1)==-1);
      ready();under(257,0,0,()->check("Nested hardware uses an independent frame",result()==-1));
      check("Nested hardware consumption preserves outer eligibility",PocketHardwareCaretScope.offset(1)==-1);
      RuntimeException same=new RuntimeException("original");ready();
      try{under(257,0,0,()->{ready();throw same;});throw new AssertionError("Missing original exception");}catch(RuntimeException value){check("Original nested exception propagated unchanged",value==same);}
      check("Exception restores the previous frame",PocketHardwareCaretScope.offset(1)==-1);
    });
    check("Hardware scope never leaks to following soft input",result()==1);
    under(257|0x10000,8,0,()->check("Additional source bits and ordinary system flags preserve hardware",result()==-1));
    AtomicInteger calls=new AtomicInteger();Runnable queued=PocketHardwareCaretScope.wrap(()->{calls.incrementAndGet();check("Deferred original runnable receives captured hardware origin",result()==-1);},257,0,0);
    check("Wrapping does not execute, repost or pace the original runnable",calls.get()==0);queued.run();check("Original runnable executes exactly once",calls.get()==1);
    Error originalError=new AssertionError("same error");try{under(257,0,0,()->{ready();throw originalError;});throw new AssertionError("Missing error");}catch(Error error){check("Original Error propagated unchanged",error==originalError);}
    check("Error also clears the outermost scope",result()==1);
    AtomicReference<Throwable> failure=new AtomicReference<>();AtomicInteger parallel=new AtomicInteger();Thread[] workers=new Thread[4];
    for(int n=0;n<workers.length;n++){workers[n]=new Thread(()->{try{for(int i=0;i<100;i++){under(257,0,0,()->{if(result()!=-1)throw new AssertionError("Missing thread frame");parallel.incrementAndGet();});if(result()!=1)throw new AssertionError("Leaked thread frame");}}catch(Throwable error){failure.compareAndSet(null,error);}});workers[n].start();}
    for(Thread worker:workers)worker.join();check("Concurrent IC-equivalent threads do not share eligibility",failure.get()==null&&parallel.get()==400);
    actualEarlyReturns();
    check("Real private-method early returns leave no outer scope",result()==1);
    System.out.println("{\"jvmBytecodeVerification\":true,\"scopeChecks\":"+checks+",\"concurrentRuns\":400,\"actualSdkGuardedEarlyReturns\":3,\"singleUseEligibility\":true,\"nestingAndExceptionCleanup\":true,\"softImePredicateUnchanged\":true,\"actualAndroidExecution\":false}");
  }
}
