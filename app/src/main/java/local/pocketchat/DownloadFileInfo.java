package local.pocketchat;

import java.io.*;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipFile;

/** Download metadata and document checks. Never rewrites the received bytes. */
final class DownloadFileInfo {
  static final String BINARY="application/octet-stream";
  static final String PDF="application/pdf";
  static final String DOCX="application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  static final String XLSX="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  static final String PPTX="application/vnd.openxmlformats-officedocument.presentationml.presentation";
  private static final Pattern PARAMETER=Pattern.compile("(?:^|;)\\s*(filename\\*?)\\s*=\\s*(\"(?:\\\\.|[^\"\\\\])*\"|[^;]*)",Pattern.CASE_INSENSITIVE);
  static final class Info {
    final String name,mime;
    Info(String name,String mime){this.name=name;this.mime=mime;}
  }
  static final class InvalidContent extends IOException {
    InvalidContent(String message){super(message);}
  }
  private DownloadFileInfo() {}

  static String mime(String value){
    String clean=value==null?"":value.split(";",2)[0].trim().toLowerCase(Locale.ROOT);
    return clean.matches("[a-z0-9.+-]+/[a-z0-9.+-]+")?clean:BINARY;
  }
  static long completeRangeLength(String value)throws IOException {
    Matcher range=Pattern.compile("bytes ([0-9]+)-([0-9]+)/([0-9]+)").matcher(value==null?"":value.trim());
    if(range.matches())try{
      long first=Long.parseLong(range.group(1)),last=Long.parseLong(range.group(2)),total=Long.parseLong(range.group(3));
      if(first==0&&total>0&&last==total-1)return total;
    }catch(NumberFormatException ignored){}
    throw new IOException("下载响应只包含部分文件，请回原网页重新下载");
  }
  static String finalMime(String received,String fallback){
    String actual=mime(received);return actual.equals(BINARY)?mime(fallback):actual;
  }
  static String extension(String name){
    int dot=name==null?-1:name.lastIndexOf('.');
    return dot<0?"":name.substring(dot+1).toLowerCase(Locale.ROOT);
  }
  static String forExtension(String ext){
    switch(ext){
      case "pdf":return PDF;
      case "docx":return DOCX;
      case "xlsx":return XLSX;
      case "pptx":return PPTX;
      case "doc":return "application/msword";
      case "xls":return "application/vnd.ms-excel";
      case "ppt":return "application/vnd.ms-powerpoint";
      case "zip":return "application/zip";
      case "txt":return "text/plain";
      case "csv":return "text/csv";
      case "json":return "application/json";
      case "html":case "htm":return "text/html";
      case "png":return "image/png";
      case "jpg":case "jpeg":return "image/jpeg";
      case "webp":return "image/webp";
      case "gif":return "image/gif";
      case "svg":return "image/svg+xml";
      case "apk":return "application/vnd.android.package-archive";
      default:return BINARY;
    }
  }
  static String forMime(String mime){
    for(String ext:new String[]{"pdf","docx","xlsx","pptx","doc","xls","ppt","zip","txt","csv","json","html","png","jpg","webp","gif","svg","apk"})
      if(forExtension(ext).equals(mime))return ext;
    return "";
  }
  static String safeName(String value){
    String name=(value==null?"":value).replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}\\u202a-\\u202e\\u2066-\\u2069]","_").trim();
    if(name.isEmpty()||name.equals(".")||name.equals("..")||name.equals("payload.part"))name="文件";
    if(name.length()>160){
      String ext=extension(name),suffix=ext.length()>0&&ext.length()<=16?"."+ext:"";
      int end=160-suffix.length();if(Character.isHighSurrogate(name.charAt(end-1)))end--;
      name=name.substring(0,end)+suffix;
    }
    return name;
  }
  private static String decoded(String value,String charset)throws Exception {
    // RFC 5987 is percent encoding, not form encoding: a literal '+' stays '+'.
    return URLDecoder.decode(value.replace("+","%2B"),charset);
  }
  static String dispositionName(String disposition){
    if(disposition==null||disposition.length()>16384)return "";
    String plain="",extended="";Matcher matches=PARAMETER.matcher(disposition);
    while(matches.find()){
      String value=matches.group(2).trim();
      if(value.startsWith("\"")&&value.endsWith("\""))value=value.substring(1,value.length()-1).replaceAll("\\\\(.)","$1");
      if(matches.group(1).endsWith("*")){
        int first=value.indexOf('\''),second=first<0?-1:value.indexOf('\'',first+1);
        if(first<=0||second<0)continue;
        String charset=value.substring(0,first);
        if(!charset.equalsIgnoreCase("UTF-8")&&!charset.equalsIgnoreCase("ISO-8859-1"))continue;
        try{extended=decoded(value.substring(second+1),charset);}catch(Exception ignored){}
      }else if(plain.isEmpty())plain=value;
    }
    return extended.isEmpty()?plain:extended;
  }
  static Info resolve(String url,String disposition,String proposed,String fallback){
    String name=dispositionName(disposition),type=mime(proposed);
    if(name.isEmpty()&&fallback!=null&&!fallback.isEmpty()&&!fallback.equals("文件"))name=fallback;
    if(name.isEmpty()&&url!=null&&!url.startsWith("blob:"))try{
      String path=new URI(url).getRawPath();
      if(path!=null&&!path.endsWith("/"))name=decoded(path.substring(path.lastIndexOf('/')+1),"UTF-8");
    }catch(Exception ignored){}
    name=safeName(name);String ext=extension(name),known=forExtension(ext),suggested=forMime(type);
    if((ext.isEmpty()||ext.equals("bin")||ext.equals("download"))&&!suggested.isEmpty())name=withExtension(name,suggested);
    if(type.equals(BINARY)&&!known.equals(BINARY))type=known;
    return new Info(name,type);
  }
  static String withExtension(String name,String extension){
    String current=extension(name);if(current.equals(extension))return safeName(name);
    int dot=name.lastIndexOf('.');String base=dot>0?name.substring(0,dot):name;
    return safeName(base+"."+extension);
  }
  private static boolean document(String ext){return ext.equals("pdf")||ext.equals("docx")||ext.equals("xlsx")||ext.equals("pptx")||ext.equals("doc")||ext.equals("xls")||ext.equals("ppt");}
  private static boolean starts(byte[] data,int... values){
    if(data.length<values.length)return false;for(int i=0;i<values.length;i++)if((data[i]&255)!=values[i])return false;return true;
  }
  private static String office(File file)throws IOException {
    try(ZipFile zip=new ZipFile(file)){
      if(zip.getEntry("[Content_Types].xml")==null)return "";
      if(zip.getEntry("word/document.xml")!=null)return "docx";
      if(zip.getEntry("xl/workbook.xml")!=null)return "xlsx";
      if(zip.getEntry("ppt/presentation.xml")!=null)return "pptx";
      return "";
    }
  }
  static Info inspect(File file,String requested,String proposed)throws IOException {
    if(file==null||!file.isFile())throw new IOException("下载的文件内容不可用，请重新下载");
    Info info=resolve(null,"",proposed,requested);String ext=extension(info.name),expected=document(ext)?ext:forMime(info.mime);
    byte[] prefix;
    try(InputStream input=new FileInputStream(file)){
      ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] part=new byte[8192];int count=input.read(part);
      if(count>0)bytes.write(part,0,count);prefix=bytes.toByteArray();
    }
    String beginning=new String(prefix,StandardCharsets.ISO_8859_1),lower=beginning.trim().toLowerCase(Locale.ROOT);
    boolean html=lower.startsWith("<!doctype html")||lower.startsWith("<html")||lower.startsWith("<head")||lower.startsWith("<body");
    boolean rtf=lower.startsWith("{\\rtf");
    boolean json=lower.startsWith("{")&&!rtf||lower.startsWith("[");
    if(document(expected)&&(html||json))throw new InvalidContent("下载链接返回了网页或错误信息，未保存为文档。请回原网页重新获取文件。");
    boolean pdf=beginning.indexOf("%PDF-")>=0&&beginning.indexOf("%PDF-")<1024;
    boolean zip=starts(prefix,0x50,0x4b,3,4)||starts(prefix,0x50,0x4b,5,6)||starts(prefix,0x50,0x4b,7,8);
    boolean ole=starts(prefix,0xd0,0xcf,0x11,0xe0,0xa1,0xb1,0x1a,0xe1);
    String office="";
    if(zip)try{office=office(file);}catch(IOException malformed){if(expected.equals("docx")||expected.equals("xlsx")||expected.equals("pptx"))throw new InvalidContent("Office 文件未下载完整或内容无效，请重新下载。");}
    if(expected.equals("pdf")&&!pdf)throw new InvalidContent("下载内容不是有效的 PDF，未保存错误文件。请回原网页重新下载。");
    if((expected.equals("docx")||expected.equals("xlsx")||expected.equals("pptx"))&&!expected.equals(office))throw new InvalidContent("下载内容与 Office 文件格式不符，未保存错误文件。请回原网页重新下载。");
    if((expected.equals("doc")||expected.equals("xls")||expected.equals("ppt"))&&!ole&&!(expected.equals("doc")&&rtf))
      throw new InvalidContent("下载内容与旧版 Office 格式不符，请回原网页重新下载。");
    if(pdf){
      byte[] tail=new byte[(int)Math.min(file.length(),65536)];
      try(RandomAccessFile input=new RandomAccessFile(file,"r")){input.seek(file.length()-tail.length);input.readFully(tail);}
      if(!new String(tail,StandardCharsets.ISO_8859_1).contains("%%EOF"))throw new InvalidContent("PDF 未下载完整，请回原网页重新下载。");
      return new Info(withExtension(info.name,"pdf"),PDF);
    }
    // A URL endpoint suffix is not the document type. Preserve an explicitly
    // requested ZIP archive, otherwise use the recognized Office container.
    if(!office.isEmpty()&&(!ext.equals("zip")||document(expected)))
      return new Info(withExtension(info.name,office),forExtension(office));
    return info;
  }
}
