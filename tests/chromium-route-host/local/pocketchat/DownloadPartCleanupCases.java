package local.pocketchat;
import java.io.*;
import java.nio.file.*;
import java.util.*;
/** Real filesystem coverage for the production helper and exact reset/delete
 * call sites. Never opens or removes a real app cache or downloaded user file. */
public final class DownloadPartCleanupCases {
  static int checks;static void check(String label,boolean pass){checks++;if(!pass)throw new AssertionError(label);}
  static void write(Path path,String bytes)throws IOException{Files.createDirectories(path.getParent());Files.write(path,bytes.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
  static void clear(int entry,File noBackup,File cache)throws IOException{
    if(entry==0)EnvironmentBrowserData.clearBrowserDownloadParts(cache);
    else if(entry==1)BrowserDataClearEntry.reset(new ProfileFixture(noBackup,cache));
    else BrowserDataClearEntry.delete(new ProfileFixture(noBackup,cache));
  }
  public static void main(String[] args)throws Exception{
    for(int entry=0;entry<3;entry++){
      Path root=Files.createTempDirectory("browser-download-cleanup-");Path outside=Files.createTempDirectory("browser-download-target-");try{
        Path cache=Files.createDirectories(root.resolve("cache")),noBackup=Files.createDirectories(root.resolve("no_backup"));
        Path partial=File.createTempFile("browser-download-",".part",cache.toFile()).toPath();write(partial,"private partial download bytes");
        Path second=cache.resolve("browser-download-stale.part");write(second,"another interrupted download");
        Map<Path,byte[]> preserved=new LinkedHashMap<>();
        for(String path:new String[]{"cache/image.cache","cache/browser-download-complete.pdf","cache/browser-download-stale.part.bak","cache/other-browser-download-11.part","cache/browser-download-folder.part/keep","cache/profiles/env1/browser-download-11.part","files/saved-downloads/browser-download-saved.part","Downloads/user-file.pdf","databases/saved-download-library.db"}){Path file=root.resolve(path);write(file,"keep "+path);preserved.put(file,Files.readAllBytes(file));}
        Path fileTarget=outside.resolve("private-target.part");write(fileTarget,"external symlink target bytes");preserved.put(fileTarget,Files.readAllBytes(fileTarget));
        Path directoryTarget=outside.resolve("directory");write(directoryTarget.resolve("keep"),"directory target bytes");preserved.put(directoryTarget.resolve("keep"),Files.readAllBytes(directoryTarget.resolve("keep")));
        Path fileLink=cache.resolve("browser-download-file-link.part"),directoryLink=cache.resolve("browser-download-directory-link.part"),keptLink=cache.resolve("unrelated-link");
        Files.createSymbolicLink(fileLink,fileTarget);Files.createSymbolicLink(directoryLink,directoryTarget);Files.createSymbolicLink(keptLink,fileTarget);
        clear(entry,noBackup.toFile(),cache.toFile());
        check("entry "+entry+" removes actual createTempFile part",!Files.exists(partial));check("entry "+entry+" removes stale named part",!Files.exists(second));
        check("entry "+entry+" unlinks matching file symlink only",!Files.exists(fileLink,LinkOption.NOFOLLOW_LINKS));check("entry "+entry+" unlinks matching directory symlink only",!Files.exists(directoryLink,LinkOption.NOFOLLOW_LINKS));
        check("entry "+entry+" preserves unrelated symlink",Files.isSymbolicLink(keptLink));check("entry "+entry+" preserves cache root",Files.isDirectory(cache));
        for(Map.Entry<Path,byte[]> file:preserved.entrySet())check("entry "+entry+" preserves bytes "+file.getKey().getFileName(),Files.exists(file.getKey())&&Arrays.equals(file.getValue(),Files.readAllBytes(file.getKey())));
        Path redirected=root.resolve("redirected-cache");Files.createSymbolicLink(redirected,outside);Path externalPart=outside.resolve("browser-download-keep.part");write(externalPart,"must not delete through linked cache root");
        boolean refused=false;try{clear(entry,noBackup.toFile(),redirected.toFile());}catch(IOException expected){refused=true;}
        check("entry "+entry+" refuses symlink cache root",refused&&Files.exists(externalPart)&&Files.isSymbolicLink(redirected));
      }finally{EnvironmentBrowserData.erase(root.toFile());EnvironmentBrowserData.erase(outside.toFile());}
    }
    System.out.println("Chromium production download-part cleanup: "+checks+" checks passed");
  }
}
final class ProfileFixture {final File noBackup,cache;ProfileFixture(File noBackup,File cache){this.noBackup=noBackup;this.cache=cache;}File getNoBackupFilesDir(){return noBackup;}File getCacheDir(){return cache;}}
