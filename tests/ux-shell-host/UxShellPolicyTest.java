package local.pocketchat;

import java.util.*;

public final class UxShellPolicyTest {
  static int checks;
  static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
  static ActionSearchPolicy.Item item(String id,String label,String detail,String aliases){return new ActionSearchPolicy.Item(id,label,detail,aliases);}
  public static void main(String[] args){
    List<ActionSearchPolicy.Item> items=Arrays.asList(item("drafts","草稿救援","查找暂存输入","复制 恢复 draft"),item("network","当前环境网络","管理订阅和节点","network proxy"),item("reload","重新加载网页","先核对草稿与附件","刷新 reload"),item("downloads","下载中心","搜索文件","download file"));
    List<String> recent=Arrays.asList("downloads","network");
    check(ActionSearchPolicy.search(items,"草稿",recent).get(0).id.equals("drafts"),"label matches rank before detail matches");
    check(ActionSearchPolicy.search(items,"恢复",recent).get(0).id.equals("drafts"),"Chinese alias discovers draft rescue");
    check(ActionSearchPolicy.search(items," ＰＲＯＸＹ ",recent).get(0).id.equals("network"),"NFKC and case normalize full-width hardware input");
    check(ActionSearchPolicy.search(items,"network 节点",recent).size()==1,"every query token must match the same command");
    check(ActionSearchPolicy.search(items,"network 草稿",recent).isEmpty(),"unrelated terms cannot run an approximate command");
    check(ActionSearchPolicy.search(items,"missing",recent).isEmpty(),"unknown query remains empty");
    check(ActionSearchPolicy.search(items,"",recent).get(0).id.equals("downloads"),"recent available action ranks first");
    check(items.get(0).id.equals("drafts"),"search never mutates source command ordering");
    check(ActionSearchPolicy.search(items,"  ",Collections.emptyList()).get(0).id.equals("drafts"),"empty queries retain useful default order");
    check(ActionSearchPolicy.recent("bad,network,network,downloads,draft-from-another-context",items).equals(Arrays.asList("network","downloads")),"persisted recents deduplicate and cannot resurrect unavailable commands");
    check(ActionSearchPolicy.remember("network",recent).equals("network,downloads"),"executed command moves to front once");
    check(ActionSearchPolicy.remember("a",Arrays.asList("b","c","d","e","f","g","h")).equals("a,b,c,d,e,f"),"recent storage stays bounded");
    check(ActionSearchPolicy.normalize(null).isEmpty(),"missing query safe");
    check(ActionSearchPolicy.score(items.get(0),"草稿救援")>ActionSearchPolicy.score(items.get(0),"草稿"),"exact label outranks prefix");
    for(boolean requested:new boolean[]{false,true})for(boolean chat:new boolean[]{false,true})for(boolean visible:new boolean[]{false,true})for(boolean keyboard:new boolean[]{false,true}){
      boolean focused=FocusReadingPolicy.active(requested,chat,visible);
      check(focused==(requested&&chat&&visible),"focus only hides chrome over the visible chat");
      check(FocusReadingPolicy.navigation(focused,chat,keyboard)==(!focused&&!(chat&&keyboard)),"navigation handles keyboard and native workspace independently");
      check(FocusReadingPolicy.exitControl(focused,keyboard)==focused,"exit control remains available with keyboard open");
    }
    System.out.println("UX shell policies: "+checks+" behavioral checks passed");
  }
}
