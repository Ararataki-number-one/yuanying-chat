package local.pocketchat;

import java.io.*;
import java.nio.file.Files;

/** Narrow login/site storage cleanup. The trusted app roots themselves are never
 * removed; an environment ancestor link is refused, terminal links are unlinked. */
final class EnvironmentBrowserData {
  static File root(File trusted,int slot)throws IOException{
    if(slot<0||slot>=8)throw new IOException("环境槽位无效");if(Files.isSymbolicLink(trusted.toPath())||!trusted.isDirectory())throw new IOException("应用存储目录不可用");File base=trusted.getCanonicalFile();
    if(slot==0)return base;
    File profiles=directory(base,"profiles"),environment=directory(profiles,"env"+slot);
    if(!environment.getCanonicalPath().startsWith(base.getPath()+File.separator))throw new IOException("环境目录越界");return environment;
  }
  private static File directory(File parent,String name)throws IOException{
    File child=new File(parent,name);if(Files.isSymbolicLink(child.toPath()))throw new IOException("环境目录包含链接，未清理任何数据");
    if(!child.exists()&&!child.mkdir()||!child.isDirectory())throw new IOException("环境目录不可用");return child;
  }
  static void clear(File noBackup,File cache)throws IOException{
    for(String name:new String[]{"gecko-browser","gecko-session.json","gecko-session.json.bak","gecko-session.json.new"})erase(new File(noBackup,name));
    erase(new File(cache,"gecko-uploads"));
  }
  static void erase(File file)throws IOException{
    if(Files.isSymbolicLink(file.toPath())){if(!file.delete())throw new IOException("无法清理链接");return;}
    if(!file.exists())return;
    if(file.isDirectory()){File[] children=file.listFiles();if(children==null)throw new IOException("无法读取网页目录");for(File child:children)erase(child);}
    if(!file.delete())throw new IOException("无法清理网页数据");
  }
}
