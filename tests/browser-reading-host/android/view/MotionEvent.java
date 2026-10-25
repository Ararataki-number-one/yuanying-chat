package android.view;
public final class MotionEvent {
  public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5;
  final int action,pointers;final float x,y;public MotionEvent(int a,int p){this(a,p,0,0);}public MotionEvent(int a,int p,float rawX,float rawY){action=a;pointers=p;x=rawX;y=rawY;}
  public int getActionMasked(){return action;}public int getPointerCount(){return pointers;}
  public float getRawX(){return x;}public float getRawY(){return y;}
}
