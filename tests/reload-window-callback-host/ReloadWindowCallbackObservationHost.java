package local.pocketchat;

import android.view.Window;
import java.lang.reflect.*;
import java.util.*;

/** JVM delegation controls against the actual API35 Window.Callback interface. */
public final class ReloadWindowCallbackObservationHost {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static Object defaultValue(Class<?> type){if(type==boolean.class)return false;if(type==int.class)return 0;if(type==long.class)return 0L;if(type==float.class)return 0f;if(type==double.class)return 0d;if(type==byte.class)return (byte)0;if(type==short.class)return (short)0;if(type==char.class)return (char)0;return null;}
  public static void main(String[] args)throws Exception{
    List<Method> methods=new ArrayList<>(Arrays.asList(Window.Callback.class.getMethods()));methods.sort(Comparator.comparing(Method::toGenericString));
    for(Method method:methods){
      int[] calls={0},before={0},after={0};Object[] expected=new Object[method.getParameterCount()];Class<?>[] types=method.getParameterTypes();for(int i=0;i<expected.length;i++)expected[i]=defaultValue(types[i]);
      Window.Callback original=(Window.Callback)Proxy.newProxyInstance(Window.Callback.class.getClassLoader(),new Class<?>[]{Window.Callback.class},(proxy,called,values)->{check("same method "+method.toGenericString(),called.equals(method));check("same arguments "+method.toGenericString(),Arrays.equals(expected,values==null?new Object[0]:values));calls[0]++;return defaultValue(called.getReturnType());});
      Window.Callback wrapped=ReloadWindowCallbackObservation.wrap(original,(enter,observed,values,result,failure)->{if(enter)before[0]++;else after[0]++;if(values!=null)Arrays.fill(values,null);throw new AssertionError("observer must not affect original");});
      Object result=method.invoke(wrapped,expected);check("original once and both observations "+method.toGenericString(),calls[0]==1&&before[0]==1&&after[0]==1);check("original return "+method.toGenericString(),Objects.equals(result,defaultValue(method.getReturnType())));
    }
    for(boolean answer:new boolean[]{false,true}){
      Window.Callback original=(Window.Callback)Proxy.newProxyInstance(Window.Callback.class.getClassLoader(),new Class<?>[]{Window.Callback.class},(proxy,method,values)->answer);
      Window.Callback wrapped=ReloadWindowCallbackObservation.wrap(original,(before,method,values,result,failure)->{});
      check("touch return preserved "+answer,wrapped.dispatchTouchEvent(null)==answer);
    }
    RuntimeException expectedFailure=new IllegalStateException("original failure identity");int[] calls={0},observed={0};
    Window.Callback original=(Window.Callback)Proxy.newProxyInstance(Window.Callback.class.getClassLoader(),new Class<?>[]{Window.Callback.class},(proxy,method,values)->{calls[0]++;throw expectedFailure;});
    Window.Callback wrapped=ReloadWindowCallbackObservation.wrap(original,(before,method,values,result,failure)->{if(!before&&failure==expectedFailure)observed[0]++;throw new AssertionError("observer failure");});
    try{wrapped.onWindowFocusChanged(true);throw new AssertionError("original failure lost");}catch(RuntimeException actual){check("original exception object is unwrapped unchanged",actual==expectedFailure);}
    check("throwing original called once and observed",calls[0]==1&&observed[0]==1);
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks.size()+",\"apiCallbackMethods\":"+methods.size()+",\"actualAndroidExecution\":false,\"diagnosticOnly\":true,\"releaseAcceptance\":false}");
  }
}
