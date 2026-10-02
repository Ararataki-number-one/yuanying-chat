package local.pocketchat;
import android.app.*;
import java.text.SimpleDateFormat;
import java.util.*;

final class ExitIpUi {
  static String value(ChatSession s,NativeNetwork n){if(!s.internalNetwork())return "出口 IP：当前网络方式尚未核实";if(n.recoveryBlocked&&!n.observedExitIp.isEmpty())return "出口 IP 已变化："+n.observedExitIp+" · 已停止连接";String ip=n.exitIp;if(ip.isEmpty())return "出口 IP：待核实";String time=n.lastVerified>0?new SimpleDateFormat("HH:mm:ss",Locale.getDefault()).format(new Date(n.lastVerified)):"";if(s.offline)return "上次出口 IP："+ip+" · 当前离线";if(!n.ready||!s.networkReady)return "上次出口 IP："+ip+" · 连接未确认";return "出口 IP："+ip+" · "+time+" 核实";}
  static void update(MainActivity a){if(a.exitIpLine==null)return;NativeNetwork n=NativeNetwork.get(a);a.exitIpLine.setText(value(a.session,n));a.exitIpLine.setTextColor(n.recoveryBlocked?0xffb42318:Ui.MUTED);}
  static void show(MainActivity a){NativeNetwork n=NativeNetwork.get(a);String detail=value(a.session,n);if(n.recoveryBlocked&&!n.exitIp.isEmpty())detail+="\n原核实出口："+n.exitIp;if(!a.session.internalNetwork()){NetworkStatusUi.show(a);return;}new AlertDialog.Builder(a).setTitle("出口 IP").setMessage(detail+"\n\n每次发送前核实，连接正常时约每 30 秒复核。出口变化会停止连接。").setPositiveButton("立即核实",(d,w)->{a.exitIpLine.setText("出口 IP：正在核实…");n.checkExit((ok,message)->{ExitIpUi.update(a);if(!ok)a.status(message);});}).setNegativeButton("关闭",null).show();}
}
