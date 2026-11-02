package local.pocketchat;

import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.text.TextUtils;
import android.view.*;
import android.widget.*;
import java.text.SimpleDateFormat;
import java.util.*;
import org.json.JSONObject;

/** Native, read-only dashboard. Drawing and rendering never perform network I/O. */
final class EnvironmentOverviewDashboard extends LinearLayout {
  final MainActivity a;
  final TextView clock,flag,connection,region,ip,source,notes,group,progress,browser,language,zone,agent;
  final Button check,query,audit;
  final List<LinearLayout> cards=new ArrayList<>();
  boolean paletteDark;
  EnvironmentOverviewDashboard(MainActivity a,int slot,Runnable inspect,Runnable queryIp,Runnable inspectIdentity,Runnable details,Runnable enter){
    super(a);this.a=a;setOrientation(VERTICAL);setBackground(new Backdrop());setContentDescription("环境仪表盘");
    LinearLayout body=new LinearLayout(a){@Override protected void onMeasure(int width,int height){super.onMeasure(MeasureSpec.makeMeasureSpec(Math.min(MeasureSpec.getSize(width),a.dp(760)),MeasureSpec.EXACTLY),height);}};
    body.setOrientation(VERTICAL);body.setPadding(a.dp(18),a.dp(20),a.dp(18),a.dp(18));
    FrameLayout centered=new FrameLayout(a);centered.addView(body,new FrameLayout.LayoutParams(-1,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL));
    ScrollView scroll=new ScrollView(a);scroll.setFillViewport(true);scroll.setClipToPadding(false);scroll.addView(centered);addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
    LinearLayout header=DesignUi.row(a);TextView badge=label(String.format(Locale.ROOT,"%02d",slot+1),11,DesignUi.BLUE,true);badge.setPadding(a.dp(8),a.dp(5),a.dp(8),a.dp(5));badge.setBackground(DesignUi.surface(a,ReferenceUi.BLUE_SOFT,8,Color.TRANSPARENT));header.addView(badge);
    TextView title=label(Profiles.display(a,slot),18,DesignUi.TEXT,true);title.setPadding(a.dp(9),0,a.dp(6),0);title.setMaxLines(2);header.addView(title,new LinearLayout.LayoutParams(0,-2,1));body.addView(header);
    clock=label("",11,DesignUi.MUTED,false);clock.setPadding(0,a.dp(3),0,a.dp(14));body.addView(clock);

    LinearLayout hero=card(body);FrameLayout heroHead=new FrameLayout(a);View globe=new View(a);globe.setBackground(new Globe());globe.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);heroHead.addView(globe,new FrameLayout.LayoutParams(a.dp(170),a.dp(126),Gravity.RIGHT|Gravity.CENTER_VERTICAL));
    LinearLayout heroCopy=DesignUi.column(a),statusRow=DesignUi.row(a);flag=label("◎",25,DesignUi.BLUE,false);flag.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);statusRow.addView(flag,new LinearLayout.LayoutParams(0,-2,1));connection=label("正在准备",11,DesignUi.BLUE,true);connection.setPadding(a.dp(9),a.dp(5),a.dp(9),a.dp(5));connection.setBackground(DesignUi.surface(a,ReferenceUi.BLUE_SOFT,8,Color.TRANSPARENT));statusRow.addView(connection);heroCopy.addView(statusRow);
    region=label("地区未取得",15,DesignUi.TEXT,true);region.setPadding(0,a.dp(20),0,a.dp(4));heroCopy.addView(region);
    ip=label("IP：查询中…",23,DesignUi.CYAN,true);ip.setTextDirection(View.TEXT_DIRECTION_LTR);ip.setTextIsSelectable(true);heroCopy.addView(ip);
    source=label("线路核验结果会在这里显示",11,DesignUi.MUTED,false);source.setPadding(0,a.dp(8),0,a.dp(16));heroCopy.addView(source);heroHead.addView(heroCopy,new FrameLayout.LayoutParams(-1,-2));hero.addView(heroHead);
    LinearLayout actions=DesignUi.row(a);check=ReferenceUi.small(a,"检测线路",false,inspect);query=DesignUi.button(a,"代理 IP 查询 ↗",true,queryIp);query.setTextSize(13);actions.addView(check,new LinearLayout.LayoutParams(0,-2,1));LinearLayout.LayoutParams qp=new LinearLayout.LayoutParams(0,-2,1);qp.leftMargin=a.dp(8);actions.addView(query,qp);hero.addView(actions);

    LinearLayout window=card(body);heading(window,"窗口信息",null);notes=row(window,"备注","—");group=row(window,"分组","未分组");progress=row(window,"网络状态","正在准备环境");
    LinearLayout identity=card(body);audit=ReferenceUi.small(a,"指纹检测 ↗",false,inspectIdentity);heading(identity,"指纹信息",audit);
    row(identity,"系统 / 内核","Android "+Build.VERSION.RELEASE+" / Firefox");browser=row(identity,"浏览器模板","等待浏览器确认");language=row(identity,"请求语言","等待浏览器确认");zone=row(identity,"网页时区","尚未观测");agent=row(identity,"User Agent","等待浏览器确认");agent.setMaxLines(3);agent.setEllipsize(TextUtils.TruncateAt.END);agent.setTextIsSelectable(true);
    Button technical=ReferenceUi.small(a,"查看来源与详细信息",false,details);identity.addView(technical,new LinearLayout.LayoutParams(-1,-2));
    TextView credit=label("IP 网页查询：ip123.in · 使用当前环境线路",11,DesignUi.MUTED,false);credit.setPadding(a.dp(2),a.dp(14),a.dp(2),a.dp(6));body.addView(credit);

    LinearLayout footer=DesignUi.column(a);footer.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(14));footer.addView(DesignUi.button(a,"进入聊天",true,enter),new LinearLayout.LayoutParams(-1,-2));addView(footer,new LinearLayout.LayoutParams(-1,-2));
    paletteDark=AppAppearance.dark();check.setEnabled(false);query.setEnabled(false);audit.setEnabled(false);
  }
  TextView label(String text,int size,int color,boolean bold){return ReferenceUi.text(a,text,size,color,bold);}
  LinearLayout card(LinearLayout parent){LinearLayout v=DesignUi.column(a);v.setPadding(a.dp(18),a.dp(18),a.dp(18),a.dp(12));v.setBackground(DesignUi.surface(a,DesignUi.CARD,18,DesignUi.LINE));cards.add(v);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=a.dp(12);parent.addView(v,p);return v;}
  void heading(LinearLayout card,String text,Button action){LinearLayout row=DesignUi.row(a);TextView title=label(text,15,DesignUi.TEXT,true);if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);row.addView(title,new LinearLayout.LayoutParams(0,-2,1));if(action!=null)row.addView(action,new LinearLayout.LayoutParams(-2,-2));card.addView(row);}
  TextView row(LinearLayout card,String title,String value){LinearLayout row=DesignUi.row(a);row.setGravity(Gravity.TOP);row.setPadding(0,a.dp(12),0,a.dp(3));TextView name=label(title,12,DesignUi.MUTED,false);row.addView(name,new LinearLayout.LayoutParams(a.dp(88),-2));TextView text=label(value,13,DesignUi.TEXT,false);text.setBreakStrategy(android.graphics.text.LineBreaker.BREAK_STRATEGY_HIGH_QUALITY);row.addView(text,new LinearLayout.LayoutParams(0,-2,1));card.addView(row);return text;}
  static void update(TextView view,String value){if(!TextUtils.equals(view.getText(),value))view.setText(value);}
  void render(EnvironmentOverviewInfo.Snapshot v,JSONObject metadata,ChatSession session,boolean checking){
    if(paletteDark!=AppAppearance.dark()){paletteDark=AppAppearance.dark();for(LinearLayout card:cards)card.setBackground(DesignUi.surface(a,DesignUi.CARD,18,DesignUi.LINE));invalidate();}
    update(clock,TimeZone.getDefault().getID()+"  "+new SimpleDateFormat("yyyy-MM-dd HH:mm",Locale.getDefault()).format(new Date())+" · 手机时间");
    update(connection,session==null?"正在准备":v.verified?"已连接":session.offline?"未连接":session.connecting?"连接中":session.networkReady?"线路已连接":"等待连接");
    update(region,v.region.isEmpty()?"地区未取得":v.region+" · 上次定位");update(flag,flag(v.region));
    update(ip,"IP："+(v.ip.isEmpty()?(session==null||session.connecting?"查询中…":"未取得"):v.ip));
    update(source,v.ip.isEmpty()?"尚未取得当前线路核验结果":(v.verified?"已核验":"上次查询")+" · "+v.ipTime+"\n"+v.ipSource);
    update(notes,metadata.optString("notes").isEmpty()?"—":EnvironmentOverviewInfo.clean(metadata.optString("notes")));update(group,metadata.optString("group").isEmpty()?"未分组":EnvironmentOverviewInfo.clean(metadata.optString("group")));update(progress,v.connection);
    update(browser,v.browser);update(language,v.language);update(zone,v.zone);
    String ua=session==null?"":session.web.getSettings().getUserAgentString();update(agent,ua==null||ua.isEmpty()?"等待浏览器确认":ua);
    boolean owned=session!=null&&NetworkStatusUi.current(a,session);boolean connected=owned&&NetworkStatusUi.connectionReady(session);
    check.setEnabled(connected&&!checking);query.setEnabled(connected);audit.setEnabled(owned);
    if(!TextUtils.equals(check.getText(),checking?"检测中…":"检测线路"))check.setText(checking?"检测中…":"检测线路");
  }
  static String flag(String region){String[] places={"日本","香港","台湾","新加坡","美国","英国","德国","法国","韩国","加拿大","澳大利亚","荷兰"},flags={"🇯🇵","🇭🇰","🇹🇼","🇸🇬","🇺🇸","🇬🇧","🇩🇪","🇫🇷","🇰🇷","🇨🇦","🇦🇺","🇳🇱"};for(int i=0;i<places.length;i++)if(region.startsWith(places[i]))return flags[i];return "◎";}
  static final class Backdrop extends Drawable {
    final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    @Override public void draw(Canvas c){Rect b=getBounds();c.drawColor(DesignUi.BG);float radius=Math.max(b.width(),b.height())*.65f;paint.setShader(new RadialGradient(b.left,b.bottom,radius,AppAppearance.dark()?0x20278099:0x3038c9ed,Color.TRANSPARENT,Shader.TileMode.CLAMP));c.drawRect(b,paint);paint.setShader(new RadialGradient(b.right,b.bottom,radius,AppAppearance.dark()?0x185b58a0:0x288d77e5,Color.TRANSPARENT,Shader.TileMode.CLAMP));c.drawRect(b,paint);paint.setShader(null);}
    @Override public void setAlpha(int a){}@Override public void setColorFilter(ColorFilter f){}@Override public int getOpacity(){return PixelFormat.OPAQUE;}
  }
  static final class Globe extends Drawable {
    final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);final RectF oval=new RectF();
    @Override public void draw(Canvas c){Rect b=getBounds();paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(Math.max(1,b.width()/220f));paint.setColor(AppAppearance.dark()?0x2058bdd5:0x1471b9d0);float x=b.centerX(),y=b.centerY(),rx=b.width()*.47f,ry=b.height()*.44f;int save=c.save();c.rotate(-22,x,y);oval.set(x-rx,y-ry,x+rx,y+ry);c.drawOval(oval,paint);for(int i=1;i<4;i++){float scale=i/4f;oval.set(x-rx*scale,y-ry,x+rx*scale,y+ry);c.drawOval(oval,paint);}for(int i=-2;i<=2;i++){float yy=y+i*ry/3;float xr=rx*(float)Math.sqrt(1-(yy-y)*(yy-y)/(ry*ry));c.drawLine(x-xr,yy,x+xr,yy,paint);}c.restoreToCount(save);}
    @Override public void setAlpha(int a){}@Override public void setColorFilter(ColorFilter f){}@Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
}
