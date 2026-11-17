package local.pocketchat;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.zip.*;

/** Response names, document identity and byte preservation, with actual local files. */
public final class DownloadContentCases {
  static int passed;
  static void check(String name,boolean ok){if(!ok)throw new AssertionError(name);passed++;}
  interface Work {void run()throws Exception;}
  static void rejects(String name,Work work)throws Exception {
    try{work.run();}catch(DownloadFileInfo.InvalidContent expected){passed++;return;}
    throw new AssertionError(name);
  }
  static File bytes(File root,String name,byte[] bytes)throws IOException {
    File file=new File(root,name);Files.write(file.toPath(),bytes);return file;
  }
  static File office(File root,String name,String member)throws IOException {
    File file=new File(root,name);
    try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))){
      zip.putNextEntry(new ZipEntry("[Content_Types].xml"));zip.write("<?xml version=\"1.0\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>".getBytes(StandardCharsets.UTF_8));zip.closeEntry();
      zip.putNextEntry(new ZipEntry(member));zip.write("<?xml version=\"1.0\"?><document/>".getBytes(StandardCharsets.UTF_8));zip.closeEntry();
    }return file;
  }
  public static void main(String[] args)throws Exception {
    File root=Files.createTempDirectory("download-content-").toFile();
    try{
      DownloadFileInfo.Info info=DownloadFileInfo.resolve("https://example.test/backend/download", "attachment; filename=ascii.docx; filename*=UTF-8''%E7%A9%BA%E8%A1%A8+2026.docx",DownloadFileInfo.DOCX,"");
      check("RFC 5987 Unicode and literal plus",info.name.equals("空表+2026.docx")&&info.mime.equals(DownloadFileInfo.DOCX));
      check("Quoted semicolon belongs to filename",DownloadFileInfo.dispositionName("attachment; filename=\"notes; final.pdf\"").equals("notes; final.pdf"));
      check("Malformed extended value uses filename",DownloadFileInfo.dispositionName("attachment; filename=report.pdf; filename*=UTF-8''bad%QQ").equals("report.pdf"));
      info=DownloadFileInfo.resolve("https://example.test/download","attachment; filename=final.docx",DownloadFileInfo.DOCX,"download.bin");
      check("Final response filename wins",info.name.equals("final.docx"));
      info=DownloadFileInfo.resolve("https://example.test/download","",DownloadFileInfo.PDF,"download.bin");
      check("Final PDF MIME repairs generic suffix",info.name.equals("download.pdf")&&info.mime.equals(DownloadFileInfo.PDF));
      info=DownloadFileInfo.resolve("blob:https://example.test/id","",DownloadFileInfo.DOCX,"文件");
      check("Blob Word MIME supplies its suffix",info.name.equals("文件.docx")&&info.mime.equals(DownloadFileInfo.DOCX));
      info=DownloadFileInfo.resolve("https://example.test/a+b%20c.pdf?signature=private","",DownloadFileInfo.BINARY,"");
      check("URL filename decodes without query or plus changes",info.name.equals("a+b c.pdf")&&info.mime.equals(DownloadFileInfo.PDF));
      check("An empty Blob type keeps the listener document MIME",DownloadFileInfo.finalMime("",DownloadFileInfo.DOCX).equals(DownloadFileInfo.DOCX));
      check("Generic final MIME keeps established document intent",DownloadFileInfo.finalMime(DownloadFileInfo.BINARY,DownloadFileInfo.PDF).equals(DownloadFileInfo.PDF));
      check("An explicit response type overrides the old guess",DownloadFileInfo.finalMime(DownloadFileInfo.DOCX,"text/html").equals(DownloadFileInfo.DOCX));
      String longName="表".repeat(200)+".docx";
      check("Long filename keeps Office extension",DownloadFileInfo.safeName(longName).length()<=160&&DownloadFileInfo.safeName(longName).endsWith(".docx"));
      check("Filename cannot traverse folders",!DownloadFileInfo.safeName("../../report.pdf").contains("/"));
      check("Bidi filename controls are removed",!DownloadFileInfo.safeName("report\u202efdp.exe").contains("\u202e"));
      byte[] pdf="%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n".getBytes(StandardCharsets.US_ASCII);
      File actual=bytes(root,"received.part",pdf);
      info=DownloadFileInfo.inspect(actual,"report.bin",DownloadFileInfo.BINARY);
      check("PDF bytes identify generic download",info.name.equals("report.pdf")&&info.mime.equals(DownloadFileInfo.PDF));
      check("PDF byte stream is preserved",Arrays.equals(pdf,Files.readAllBytes(actual.toPath())));
      File truncated=bytes(root,"truncated.part","%PDF-1.7\nunfinished".getBytes(StandardCharsets.US_ASCII));
      rejects("Truncated PDF never becomes a saved file",()->DownloadFileInfo.inspect(truncated,"report.pdf",DownloadFileInfo.PDF));
      File html=bytes(root,"login.part","<!DOCTYPE html><html><body>Please sign in</body></html>".getBytes(StandardCharsets.UTF_8));
      rejects("Login HTML cannot masquerade as PDF",()->DownloadFileInfo.inspect(html,"report.pdf",DownloadFileInfo.PDF));
      rejects("Login HTML cannot masquerade as Word",()->DownloadFileInfo.inspect(html,"report.docx",DownloadFileInfo.BINARY));
      File error=bytes(root,"error.part","{\"error\":\"signed URL expired\"}".getBytes(StandardCharsets.UTF_8));
      rejects("200 JSON error cannot masquerade as PDF",()->DownloadFileInfo.inspect(error,"report.pdf",DownloadFileInfo.PDF));
      check("Explicit JSON attachment remains downloadable",DownloadFileInfo.inspect(error,"error.json","application/json").name.equals("error.json"));
      check("Explicit HTML attachment remains downloadable",DownloadFileInfo.inspect(html,"page.html","text/html").name.equals("page.html"));
      File rtf=bytes(root,"rtf.part","{\\rtf1\\ansi Word export}".getBytes(StandardCharsets.US_ASCII));
      check("Legacy Word RTF is not a JSON error",DownloadFileInfo.inspect(rtf,"report.doc","application/msword").name.equals("report.doc"));
      rejects("RTF cannot masquerade as a spreadsheet",()->DownloadFileInfo.inspect(rtf,"report.xls","application/vnd.ms-excel"));
      rejects("RTF cannot masquerade as presentation",()->DownloadFileInfo.inspect(rtf,"report.ppt","application/vnd.ms-powerpoint"));
      File docx=office(root,"word.part","word/document.xml");byte[] original=Files.readAllBytes(docx.toPath());
      info=DownloadFileInfo.inspect(docx,"空表.docx",DownloadFileInfo.BINARY);
      check("Word package keeps its name and correct MIME",info.name.equals("空表.docx")&&info.mime.equals(DownloadFileInfo.DOCX));
      check("Word ZIP bytes are preserved",Arrays.equals(original,Files.readAllBytes(docx.toPath())));
      info=DownloadFileInfo.inspect(docx,"download.html",DownloadFileInfo.DOCX);
      check("Final Word response type replaces an old HTML URL suffix",info.name.equals("download.docx")&&info.mime.equals(DownloadFileInfo.DOCX));
      info=DownloadFileInfo.inspect(docx,"download.html",DownloadFileInfo.BINARY);
      check("Word bytes repair an endpoint suffix even with generic MIME",info.name.equals("download.docx")&&info.mime.equals(DownloadFileInfo.DOCX));
      info=DownloadFileInfo.inspect(docx,"word-source.zip","application/zip");
      check("Explicit ZIP attachment keeps its archive name and type",info.name.equals("word-source.zip")&&info.mime.equals("application/zip"));
      info=DownloadFileInfo.inspect(docx,"download.bin",DownloadFileInfo.BINARY);
      check("Word package identifies generic Blob bytes",info.name.equals("download.docx")&&info.mime.equals(DownloadFileInfo.DOCX));
      rejects("Word package is not a PDF",()->DownloadFileInfo.inspect(docx,"wrong.pdf",DownloadFileInfo.PDF));
      rejects("PDF is not a Word package",()->DownloadFileInfo.inspect(actual,"wrong.docx",DownloadFileInfo.DOCX));
      File xlsx=office(root,"sheet.part","xl/workbook.xml");
      check("Spreadsheet package MIME is correct",DownloadFileInfo.inspect(xlsx,"sheet.xlsx",DownloadFileInfo.BINARY).mime.equals(DownloadFileInfo.XLSX));
      rejects("Spreadsheet cannot masquerade as Word",()->DownloadFileInfo.inspect(xlsx,"wrong.docx",DownloadFileInfo.DOCX));
      File pptx=office(root,"slides.part","ppt/presentation.xml");
      check("Slides package MIME is correct",DownloadFileInfo.inspect(pptx,"slides.pptx",DownloadFileInfo.BINARY).mime.equals(DownloadFileInfo.PPTX));
      File broken=bytes(root,"broken.part",Arrays.copyOf(original,Math.max(8,original.length/2)));
      rejects("Truncated ZIP never becomes Word",()->DownloadFileInfo.inspect(broken,"report.docx",DownloadFileInfo.DOCX));
      File empty=bytes(root,"empty.part",new byte[0]);
      rejects("Empty PDF is rejected",()->DownloadFileInfo.inspect(empty,"report.pdf",DownloadFileInfo.PDF));
      check("Empty text file remains valid",DownloadFileInfo.inspect(empty,"empty.txt","text/plain").mime.equals("text/plain"));
      System.out.println("{\"status\":\"passed\",\"checks\":"+passed+",\"actualAndroidExecution\":false,\"scope\":\"Actual production metadata and document checks on local byte streams; no full Office or PDF renderer claim\"}");
    }finally{File[] files=root.listFiles();if(files!=null)for(File file:files)file.delete();root.delete();}
  }
}
