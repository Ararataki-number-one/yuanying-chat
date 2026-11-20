package android.app;

public final class AlertDialog {
  private final Activity owner;
  private boolean showing;
  public String message="";
  private Listener confirmed;
  private java.util.function.Consumer<AlertDialog> dismissed;
  AlertDialog(Activity owner){this.owner=owner;}
  public void setOnDismissListener(java.util.function.Consumer<AlertDialog> listener){dismissed=listener;}
  public void show(){showing=true;owner.dialog=this;}
  public void dismiss(){if(!showing)return;showing=false;owner.dialog=null;if(dismissed!=null)dismissed.accept(this);}
  public void confirm(){if(confirmed!=null)confirmed.click(this,1);dismiss();}
  public interface Listener {void click(AlertDialog dialog,int which);}
  public static final class Builder {
    private final AlertDialog dialog;
    public Builder(Activity owner){dialog=new AlertDialog(owner);}
    public Builder setTitle(String title){return this;}
    public Builder setMessage(String message){dialog.message=message;return this;}
    public Builder setNegativeButton(String label,Listener listener){return this;}
    public Builder setPositiveButton(String label,Listener listener){dialog.confirmed=listener;return this;}
    public AlertDialog create(){return dialog;}
  }
}
