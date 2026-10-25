package local.pocketchat;

import android.view.Window;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Test-only observation: every callback still executes the original exactly once. */
final class ReloadWindowCallbackObservation {
  interface Observer {
    void record(boolean before,Method method,Object[] arguments,Object result,Throwable failure);
  }
  static void record(Observer observer,boolean before,Method method,Object[] arguments,Object result,Throwable failure){
    // Diagnostics must not change arguments, returns or exceptions of the real window.
    try{observer.record(before,method,arguments==null?null:arguments.clone(),result,failure);}catch(Throwable ignored){}
  }
  static Window.Callback wrap(Window.Callback original,Observer observer){
    if(original==null||observer==null)throw new NullPointerException();
    return (Window.Callback)Proxy.newProxyInstance(Window.Callback.class.getClassLoader(),new Class<?>[]{Window.Callback.class},(proxy,method,arguments)->{
      record(observer,true,method,arguments,null,null);
      final Object result;
      try{result=method.invoke(original,arguments);}
      catch(InvocationTargetException wrapped){Throwable failure=wrapped.getCause();record(observer,false,method,arguments,null,failure);throw failure;}
      record(observer,false,method,arguments,result,null);
      return result;
    });
  }
}
