package local.pocketchat;
import java.io.*;
import java.nio.file.*;
import java.util.*;
/** Execute the verbatim production preference/database selection loops against
 * real temporary files. Only Android SharedPreferences is a recording boundary. */
public final class DeletePreferenceCases {
  static int checks;static void check(String label,boolean pass){checks++;if(!pass)throw new AssertionError(label);}
  static String pref(int slot,String base){return (slot==0?"":"env"+slot+"_")+base;}
  static void file(Path path,String value)throws IOException{Files.createDirectories(path.getParent());Files.write(path,value.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
  static void shareSnapshots()throws Exception{
    Path root=Files.createTempDirectory("retired-share-snapshots-");
    Path outside=Files.createTempDirectory("retired-share-link-target-");
    try{
      String version="abcdefghijklmnopabcdefghijklmnop";
      String otherVersion="ponmlkjihgfedcbaponmlkjihgfedcba";
      List<Path> records=new ArrayList<>();
      for(String label:new String[]{"share-saved-head","share-running-head","share-entry-selection-"+version,
          "share-exit-selection-"+version,"share-entry-provider-"+version,"share-exit-provider-"+version}){
        for(String suffix:new String[]{".sealed",".sealed.bak",".sealed.new"}){
          Path item=root.resolve(label+suffix);file(item,"synthetic snapshot");records.add(item);
        }
      }
      Map<Path,byte[]> retained=new LinkedHashMap<>();
      for(String name:new String[]{"network-catalog.sealed","source-pool-entry-"+version+version+".sealed",
          "network-snapshot.lock","sealed-io-02.lock",
          "share-entry-selection-"+version+".sealed.copy","share-exit-provider-invalid.sealed",
          "profiles/env1/share-saved-head.sealed","profiles/env1/share-entry-provider-"+version+".sealed"}){
        Path item=root.resolve(name);file(item,"retained synthetic file");retained.put(item,Files.readAllBytes(item));
      }
      Path linkTarget=outside.resolve("shared-fixture");file(linkTarget,"terminal link target");
      retained.put(linkTarget,Files.readAllBytes(linkTarget));
      Path link=root.resolve("share-exit-provider-"+otherVersion+".sealed");
      Files.createSymbolicLink(link,linkTarget);records.add(link);
      Path blocked=root.resolve("share-entry-provider-"+otherVersion+".sealed");
      Path child=blocked.resolve("untouched");file(child,"unexpected directory entry");
      boolean refused=false;
      try{EnvironmentBrowserData.clearNetworkShareSnapshots(root.toFile());}catch(IOException expected){refused=true;}
      check("unexpected snapshot directory prevents completion and keeps its content",refused&&Files.isRegularFile(child));
      Files.delete(child);Files.delete(blocked);
      EnvironmentBrowserData.clearNetworkShareSnapshots(root.toFile());
      EnvironmentBrowserData.clearNetworkShareSnapshots(root.toFile());
      check("retry and repeat preserve the shared parent",Files.isDirectory(root));
      for(Path item:records)check("retire exact private record "+item.getFileName(),!Files.exists(item,LinkOption.NOFOLLOW_LINKS));
      for(Map.Entry<Path,byte[]> item:retained.entrySet())
        check("retain other scope bytes "+item.getKey(),Arrays.equals(item.getValue(),Files.readAllBytes(item.getKey())));
      Path linkedRoot=root.resolve("redirected");Files.createSymbolicLink(linkedRoot,outside);
      Path otherHead=outside.resolve("share-saved-head.sealed");file(otherHead,"other root head");
      refused=false;
      try{EnvironmentBrowserData.clearNetworkShareSnapshots(linkedRoot.toFile());}catch(IOException expected){refused=true;}
      check("linked parent is rejected before examining another root",refused&&Files.exists(otherHead));
    }finally{EnvironmentBrowserData.erase(root.toFile());EnvironmentBrowserData.erase(outside.toFile());}
  }
  public static void main(String[] args)throws Exception{
    for(int target=0;target<8;target++){
      Path data=Files.createTempDirectory("browser-delete-prefs-");try{
        Profiles.context.cleared.clear();Map<Path,byte[]> retained=new LinkedHashMap<>();
        for(int slot=0;slot<8;slot++)for(String base:new String[]{"universal-browser","chat"})for(String suffix:new String[]{".xml",".xml.bak"}){
          Path path=data.resolve("shared_prefs/"+pref(slot,base)+suffix);file(path,"{history:[https://example.com/],bookmarks:[https://example.net/],slot:"+slot+"}");if(slot!=target)retained.put(path,Files.readAllBytes(path));
        }
        for(String name:new String[]{"saved-files-index.xml","browser-environment-names.xml","download-library.xml","universal-browser.xml.bak.tmp","env10_universal-browser.xml"}){Path path=data.resolve("shared_prefs/"+name);file(path,"global metadata");retained.put(path,Files.readAllBytes(path));}
        Path sharedIndex=data.resolve("databases/saved-download-library.db");file(sharedIndex,"global user-owned saved file index");retained.put(sharedIndex,Files.readAllBytes(sharedIndex));
        Path userFile=data.resolve("Downloads/saved-file.pdf");file(userFile,"user-owned download bytes");retained.put(userFile,Files.readAllBytes(userFile));
        for(int slot=1;slot<8;slot++){Path database=data.resolve("databases/env"+slot+"_conversations.db");file(database,"local conversation slot "+slot);if(slot!=target)retained.put(database,Files.readAllBytes(database));}
        DeletePreferenceSelection.clear(data.toFile(),target);
        for(String base:new String[]{"universal-browser","chat"}){
          String selected=pref(target,base);
          check("target "+target+" clears in-memory preference "+base,Profiles.context.cleared.contains(selected));
          for(String suffix:new String[]{".xml",".xml.bak"})check("target "+target+" removes persisted "+base+suffix,!Files.exists(data.resolve("shared_prefs/"+selected+suffix)));
        }
        if(target>0)check("target environment database removed",!Files.exists(data.resolve("databases/env"+target+"_conversations.db")));
        for(Map.Entry<Path,byte[]> entry:retained.entrySet())check("target "+target+" preserves "+entry.getKey().getFileName(),Files.exists(entry.getKey())&&Arrays.equals(entry.getValue(),Files.readAllBytes(entry.getKey())));
        for(String cleared:Profiles.context.cleared)check("no unrelated live preference cache cleared",target==0?cleared.equals("chat")||cleared.equals("universal-browser"):cleared.startsWith("env"+target+"_"));
      }finally{EnvironmentBrowserData.erase(data.toFile());}
    }
    shareSnapshots();
    System.out.println("Chromium production delete selection: "+checks+" checks passed");
  }
}
class Profiles {static final PrefContext context=new PrefContext();static PrefContext global(Object ignored){return context;}}
class PrefContext {final Set<String> cleared=new HashSet<>();PrefRecord getSharedPreferences(String name,int mode){return new PrefRecord(name,cleared);}}
class PrefRecord {final String name;final Set<String> cleared;PrefRecord(String name,Set<String> cleared){this.name=name;this.cleared=cleared;}PrefRecord edit(){return this;}PrefRecord clear(){cleared.add(name);return this;}boolean commit(){return true;}}
