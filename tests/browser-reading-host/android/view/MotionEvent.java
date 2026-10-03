package android.view;
public final class MotionEvent {
  public static final int ACTION_UP=1,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5;
  final int action,pointers;public MotionEvent(int a,int p){action=a;pointers=p;}
  public int getActionMasked(){return action;}public int getPointerCount(){return pointers;}
}
