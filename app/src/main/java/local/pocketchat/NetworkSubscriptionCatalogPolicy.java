package local.pocketchat;

import java.util.Objects;

/** Storage-independent checks for source publication and safe failure labels. */
final class NetworkSubscriptionCatalogPolicy {
  static void role(String role){if(!"entry".equals(role)&&!"exit".equals(role))throw new IllegalArgumentException("订阅类型无效");}
  static boolean current(String id,String role,String url,long addressRevision,String token,String nowId,String nowRole,String nowUrl,long nowAddressRevision,String nowToken,boolean updating){
    return updating&&token!=null&&!token.isEmpty()&&Objects.equals(id,nowId)&&Objects.equals(role,nowRole)&&Objects.equals(url,nowUrl)&&addressRevision==nowAddressRevision&&Objects.equals(token,nowToken);
  }
  static String error(String error){
    // Parser/HTTP exceptions can include private URLs and node credentials.
    String lower=error==null?"":error.toLowerCase(java.util.Locale.ROOT);
    if(lower.contains("timeout")||lower.contains("超时"))return "订阅更新超时，已保留上次可用节点";
    if(lower.contains("format")||lower.contains("parse")||lower.contains("解析")||lower.contains("格式"))return "订阅格式无法读取，已保留上次可用节点";
    return "订阅更新失败，已保留上次可用节点";
  }
}
