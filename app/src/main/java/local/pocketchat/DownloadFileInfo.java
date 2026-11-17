package local.pocketchat;

import java.io.*;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.BitSet;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import javax.xml.parsers.SAXParserFactory;
import org.xml.sax.Attributes;
import org.xml.sax.EntityResolver;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import org.xml.sax.XMLReader;
import org.xml.sax.ext.DefaultHandler2;
import org.xml.sax.helpers.DefaultHandler;

/** Download metadata and document checks. Never rewrites the received bytes. */
final class DownloadFileInfo {
  static final String BINARY="application/octet-stream";
  static final String PDF="application/pdf";
  static final String DOCX="application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  static final String XLSX="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  static final String PPTX="application/vnd.openxmlformats-officedocument.presentationml.presentation";
  static final long MAX_INSPECT_BYTES=512L*1024*1024;
  // The main part's content type distinguishes documents from templates and
  // macro-enabled packages. Their usual ZIP paths alone do not distinguish them.
  private static final String[][] OFFICE_TYPES={
    {"docx",DOCX,"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"},
    {"docm","application/vnd.ms-word.document.macroenabled.12","application/vnd.ms-word.document.macroenabled.main+xml"},
    {"dotx","application/vnd.openxmlformats-officedocument.wordprocessingml.template","application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"},
    {"dotm","application/vnd.ms-word.template.macroenabled.12","application/vnd.ms-word.template.macroenabledtemplate.main+xml"},
    {"xlsx",XLSX,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"},
    {"xlsm","application/vnd.ms-excel.sheet.macroenabled.12","application/vnd.ms-excel.sheet.macroenabled.main+xml"},
    {"xltx","application/vnd.openxmlformats-officedocument.spreadsheetml.template","application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml"},
    {"xltm","application/vnd.ms-excel.template.macroenabled.12","application/vnd.ms-excel.template.macroenabled.main+xml"},
    {"xlam","application/vnd.ms-excel.addin.macroenabled.12","application/vnd.ms-excel.addin.macroenabled.main+xml"},
    {"xlsb","application/vnd.ms-excel.sheet.binary.macroenabled.12","application/vnd.ms-excel.sheet.binary.macroenabled.main"},
    {"pptx",PPTX,"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"},
    {"pptm","application/vnd.ms-powerpoint.presentation.macroenabled.12","application/vnd.ms-powerpoint.presentation.macroenabled.main+xml"},
    {"potx","application/vnd.openxmlformats-officedocument.presentationml.template","application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"},
    {"potm","application/vnd.ms-powerpoint.template.macroenabled.12","application/vnd.ms-powerpoint.template.macroenabled.main+xml"},
    {"ppsx","application/vnd.openxmlformats-officedocument.presentationml.slideshow","application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml"},
    {"ppsm","application/vnd.ms-powerpoint.slideshow.macroenabled.12","application/vnd.ms-powerpoint.slideshow.macroenabled.main+xml"}
  };
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
    for(String[] type:OFFICE_TYPES)if(type[0].equals(ext))return type[1];
    switch(ext){
      case "pdf":return PDF;
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
    for(String[] type:OFFICE_TYPES)if(type[1].equals(mime))return type[0];
    for(String ext:new String[]{"pdf","doc","xls","ppt","zip","txt","csv","json","html","png","jpg","webp","gif","svg","apk"})
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
  private static boolean modernOffice(String ext){for(String[] type:OFFICE_TYPES)if(type[0].equals(ext))return true;return false;}
  private static boolean document(String ext){return ext.equals("pdf")||modernOffice(ext)||ext.equals("doc")||ext.equals("xls")||ext.equals("ppt");}
  private static boolean starts(byte[] data,int... values){
    if(data.length<values.length)return false;for(int i=0;i<values.length;i++)if((data[i]&255)!=values[i])return false;return true;
  }
  private static String office(File file)throws IOException {
    try(ZipFile zip=new ZipFile(file)){
      ZipEntry types=zip.getEntry("[Content_Types].xml"),relations=zip.getEntry("_rels/.rels");
      if(types==null||types.isDirectory()||relations==null||relations.isDirectory())return "";
      final long[] budget={0};final String[] main={null};
      parseOfficeXml(zip,relations,budget,new DefaultHandler(){
        int depth;
        @Override public void startElement(String namespace,String local,String name,Attributes attributes)throws SAXException{
          depth++;if(depth==1&&!("http://schemas.openxmlformats.org/package/2006/relationships".equals(namespace)&&"Relationships".equals(local)))throw new SAXException("Invalid package relationships root");
          if(depth!=2||!"http://schemas.openxmlformats.org/package/2006/relationships".equals(namespace)||!"Relationship".equals(local))return;
          String type=attributes.getValue("Type");
          if(!"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument".equals(type)&&!"http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument".equals(type))return;
          String mode=attributes.getValue("TargetMode");if(main[0]!=null||mode!=null&&!"Internal".equals(mode))throw new SAXException("Ambiguous or external Office main part");
          main[0]=packagePart(attributes.getValue("Target"));
        }
        @Override public void endElement(String namespace,String local,String name){depth--;}
      });
      if(main[0]==null)return "";ZipEntry part=zip.getEntry(main[0]);if(part==null||part.isDirectory()||part.getSize()==0)throw new IOException("Missing Office main part");
      final String[] override={null},fallback={null};final String extension=extension(main[0]);
      parseOfficeXml(zip,types,budget,new DefaultHandler(){
        int depth;
        @Override public void startElement(String namespace,String local,String name,Attributes attributes)throws SAXException{
          depth++;if(depth==1&&!("http://schemas.openxmlformats.org/package/2006/content-types".equals(namespace)&&"Types".equals(local)))throw new SAXException("Invalid content types root");
          if(depth!=2||!"http://schemas.openxmlformats.org/package/2006/content-types".equals(namespace))return;
          String content=attributes.getValue("ContentType");if(content==null)return;
          if("Override".equals(local)&&main[0].equals(packagePart(attributes.getValue("PartName")))){
            if(override[0]!=null)throw new SAXException("Duplicate main part content type");override[0]=content.toLowerCase(Locale.ROOT);
          }else if("Default".equals(local)&&extension.equalsIgnoreCase(attributes.getValue("Extension"))){
            if(fallback[0]!=null)throw new SAXException("Duplicate main part default type");fallback[0]=content.toLowerCase(Locale.ROOT);
          }
        }
        @Override public void endElement(String namespace,String local,String name){depth--;}
      });
      String content=override[0]!=null?override[0]:fallback[0];for(String[] type:OFFICE_TYPES)if(type[2].equals(content))return type[0];return "";
    }
  }
  private static String packagePart(String value)throws SAXException{
    try{
      if(value==null||value.isEmpty())throw new SAXException("Missing package part");URI path=new URI(value);
      if(path.isAbsolute()||path.getAuthority()!=null||path.getQuery()!=null||path.getFragment()!=null)throw new SAXException("External package part");
      String decoded=new URI("/").resolve(path).normalize().getPath();
      if(decoded==null||!decoded.startsWith("/")||decoded.contains("/../")||decoded.endsWith("/..")||decoded.endsWith("/"))throw new SAXException("Invalid package part");return decoded.substring(1);
    }catch(java.net.URISyntaxException invalid){throw new SAXException(invalid);}
  }
  private static void parseOfficeXml(ZipFile zip,ZipEntry entry,long[] budget,DefaultHandler handler)throws IOException{
    try(InputStream input=zip.getInputStream(entry)){
      SAXParserFactory factory=SAXParserFactory.newInstance();factory.setNamespaceAware(true);XMLReader reader=factory.newSAXParser().getXMLReader();
      reader.setFeature("http://xml.org/sax/features/external-general-entities",false);reader.setFeature("http://xml.org/sax/features/external-parameter-entities",false);
      reader.setProperty("http://xml.org/sax/properties/lexical-handler",new DefaultHandler2(){@Override public void startDTD(String name,String publicId,String systemId)throws SAXException{throw new SAXException("Office metadata cannot contain a DTD");}});
      reader.setEntityResolver(new EntityResolver(){@Override public InputSource resolveEntity(String publicId,String systemId)throws SAXException{throw new SAXException("External entities are not Office metadata");}});
      reader.setErrorHandler(new DefaultHandler(){@Override public void error(org.xml.sax.SAXParseException error)throws SAXException{throw error;}@Override public void fatalError(org.xml.sax.SAXParseException error)throws SAXException{throw error;}});
      reader.setContentHandler(handler);reader.parse(new InputSource(new OfficeMetadataInput(input,budget)));
    }catch(javax.xml.parsers.ParserConfigurationException|SAXException invalid){throw new IOException("Invalid Office package metadata",invalid);}
  }
  /** Streaming XML has the same finite byte budget as the download itself. */
  private static final class OfficeMetadataInput extends FilterInputStream {
    final long[] budget;
    OfficeMetadataInput(InputStream input,long[] budget){super(input);this.budget=budget;}
    private void account(int count)throws IOException{
      if((budget[0]+=count)>MAX_INSPECT_BYTES||Thread.currentThread().isInterrupted())throw new IOException("Office metadata exceeds the download limit or was cancelled");
    }
    @Override public int read()throws IOException{int value=in.read();if(value>=0)account(1);return value;}
    @Override public int read(byte[] bytes,int offset,int length)throws IOException{int count=in.read(bytes,offset,length);if(count>0)account(count);return count;}
  }
  /**
   * Identifies the encrypted OOXML envelope, without decrypting its contents.
   * Sector chains and the two root streams must be present and fully allocated;
   * an OLE signature or matching text somewhere in a file is not sufficient.
   */
  private static final class EncryptedOffice implements Closeable {
    static final int FREE=-1,END=-2,FAT=-3,DIFAT=-4;
    final RandomAccessFile input;final int version,sectorSize,sectorCount;final int[] fat,directory;
    final BitSet allocated=new BitSet(),miniAllocated=new BitSet();
    final Entry root;final int[] miniFat,miniStream;
    static final class Entry {
      final String name;final int kind,left,right,child,start;final long size;
      Entry(byte[] bytes,int version)throws IOException{
        kind=bytes[66]&255;int length=u16(bytes,64);
        if(length<2||length>64||(length&1)!=0||bytes[length-2]!=0||bytes[length-1]!=0)throw bad();
        name=new String(bytes,0,length-2,StandardCharsets.UTF_16LE);
        left=i32(bytes,68);right=i32(bytes,72);child=i32(bytes,76);start=i32(bytes,116);
        // MS-CFB: old v3 writers can leave the high DWORD uninitialized.
        size=version==3?u32(bytes,120):i64(bytes,120);
        if(size<0||size>MAX_INSPECT_BYTES)throw bad();
      }
    }
    static IOException bad(){return new IOException("Invalid encrypted Office container");}
    static int u16(byte[] b,int p){return (b[p]&255)|((b[p+1]&255)<<8);}
    static int i32(byte[] b,int p){return (b[p]&255)|((b[p+1]&255)<<8)|((b[p+2]&255)<<16)|(b[p+3]<<24);}
    static long u32(byte[] b,int p){return i32(b,p)&0xffffffffL;}
    static long i64(byte[] b,int p){return u32(b,p)|((long)i32(b,p+4)<<32);}
    EncryptedOffice(File file)throws IOException{
      input=new RandomAccessFile(file,"r");
      try{
        long length=input.length();if(length<512||length>MAX_INSPECT_BYTES)throw bad();
        byte[] header=new byte[512];input.readFully(header);version=u16(header,26);
        if(!starts(header,0xd0,0xcf,0x11,0xe0,0xa1,0xb1,0x1a,0xe1)||u16(header,28)!=0xfffe
            ||!(version==3&&u16(header,30)==9||version==4&&u16(header,30)==12)||u16(header,32)!=6||i32(header,56)!=4096)throw bad();
        sectorSize=1<<u16(header,30);if(length%sectorSize!=0||length<=sectorSize)throw bad();sectorCount=(int)(length/sectorSize)-1;
        int fatCount=i32(header,44),difatCount=i32(header,72);
        if(fatCount<=0||fatCount>sectorCount||difatCount<0||difatCount>sectorCount||(long)fatCount*(sectorSize/4)<sectorCount)throw bad();
        List<Integer> fatSectors=new ArrayList<>();List<Integer> difatSectors=new ArrayList<>();
        for(int p=76;p<512;p+=4)addFat(fatSectors,i32(header,p),fatCount);
        int next=i32(header,68);
        for(int i=0;i<difatCount;i++){
          claim(next,allocated,sectorCount);difatSectors.add(next);byte[] block=sector(next);
          for(int p=0;p<sectorSize-4;p+=4)addFat(fatSectors,i32(block,p),fatCount);
          next=i32(block,sectorSize-4);
        }
        if(next!=END||fatSectors.size()!=fatCount)throw bad();fat=new int[sectorCount];
        int written=0;
        for(int id:fatSectors){byte[] block=sector(id);for(int p=0;p<sectorSize&&written<sectorCount;p+=4)fat[written++]=i32(block,p);}
        for(int id:fatSectors)if(fat[id]!=FAT)throw bad();for(int id:difatSectors)if(fat[id]!=DIFAT)throw bad();
        directory=chain(i32(header,48),-1,fat,allocated,sectorCount);
        if(directory.length==0||version==4&&i32(header,40)!=directory.length||version==3&&i32(header,40)!=0)throw bad();
        root=entry(0);if(root.kind!=5||root.left!=FREE||root.right!=FREE)throw bad();
        miniStream=chain(root.start,blocks(root.size,sectorSize),fat,allocated,sectorCount);
        int miniFatCount=i32(header,64);if(miniFatCount<0||miniFatCount>sectorCount)throw bad();
        int[] miniFatSectors=chain(i32(header,60),miniFatCount,fat,allocated,sectorCount);
        int miniCount=blocks(root.size,64);if((long)miniFatSectors.length*(sectorSize/4)<miniCount)throw bad();miniFat=new int[miniCount];
        written=0;for(int id:miniFatSectors){byte[] block=sector(id);for(int p=0;p<sectorSize&&written<miniCount;p+=4)miniFat[written++]=i32(block,p);}
      }catch(IOException|RuntimeException error){input.close();throw error;}
    }
    static int blocks(long bytes,int size)throws IOException{if(bytes<0||bytes>MAX_INSPECT_BYTES)throw bad();return (int)((bytes+size-1)/size);}
    void addFat(List<Integer> ids,int id,int count)throws IOException{
      if(id==FREE)return;if(ids.size()>=count)throw bad();claim(id,allocated,sectorCount);ids.add(id);
    }
    static void claim(int id,BitSet used,int limit)throws IOException{
      if(Thread.currentThread().isInterrupted())throw new IOException("Office inspection cancelled");
      if(id<0||id>=limit||used.get(id))throw bad();used.set(id);
    }
    byte[] sector(int id)throws IOException{
      if(id<0||id>=sectorCount)throw bad();byte[] bytes=new byte[sectorSize];input.seek(((long)id+1)*sectorSize);input.readFully(bytes);return bytes;
    }
    static int[] chain(int start,int expected,int[] table,BitSet used,int limit)throws IOException{
      if(expected>limit)throw bad();int[] ids=new int[expected>=0?expected:Math.min(16,limit)];int count=0,next=start;
      while(next!=END){
        if(expected>=0&&count>=expected||count>=limit)throw bad();claim(next,used,limit);
        if(count==ids.length)ids=java.util.Arrays.copyOf(ids,Math.min(limit,Math.max(1,ids.length*2)));
        ids[count++]=next;next=table[next];
      }
      if(expected>=0&&count!=expected)throw bad();return count==ids.length?ids:java.util.Arrays.copyOf(ids,count);
    }
    Entry entry(int index)throws IOException{
      int perSector=sectorSize/128;if(index<0||(long)index>=((long)directory.length)*perSector)throw bad();
      byte[] bytes=new byte[128];input.seek(((long)directory[index/perSector]+1)*sectorSize+(index%perSector)*128L);input.readFully(bytes);return new Entry(bytes,version);
    }
    byte[] streamPrefix(Entry entry,int count)throws IOException{
      if(entry.kind!=2||entry.child!=FREE||entry.size<count)throw bad();boolean small=entry.size<4096;
      int unit=small?64:sectorSize;
      int[] ids=chain(entry.start,blocks(entry.size,unit),small?miniFat:fat,small?miniAllocated:allocated,small?miniFat.length:sectorCount);
      byte[] result=new byte[count];int written=0;long consumed=0;
      for(int id:ids){
        long offset;
        if(small){long relative=(long)id*64;if(relative+Math.min(entry.size-consumed,64)>root.size)throw bad();offset=((long)miniStream[(int)(relative/sectorSize)]+1)*sectorSize+relative%sectorSize;}
        else offset=((long)id+1)*sectorSize;
        if(written<count){int take=Math.min(count-written,unit);input.seek(offset);input.readFully(result,written,take);written+=take;}
        consumed+=unit;
      }
      return result;
    }
    boolean identifies()throws IOException{
      int entries=directory.length*(sectorSize/128);BitSet visited=new BitSet();List<Integer> pending=new ArrayList<>();if(root.child!=FREE)pending.add(root.child);
      Entry info=null,packageStream=null;
      while(!pending.isEmpty()){
        int index=pending.remove(pending.size()-1);if(index==0)throw bad();claim(index,visited,entries);Entry value=entry(index);
        if(value.kind!=1&&value.kind!=2)throw bad();if(value.left!=FREE)pending.add(value.left);if(value.right!=FREE)pending.add(value.right);
        if(value.kind==2&&"EncryptionInfo".equalsIgnoreCase(value.name)){if(info!=null)throw bad();info=value;}
        if(value.kind==2&&"EncryptedPackage".equalsIgnoreCase(value.name)){if(packageStream!=null)throw bad();packageStream=value;}
      }
      if(info==null||packageStream==null)return false;
      byte[] encryption=streamPrefix(info,8),contents=streamPrefix(packageStream,8);
      int major=u16(encryption,0),minor=u16(encryption,2);
      boolean knownVersion=minor==2&&major>=2&&major<=4||minor==3&&(major==3||major==4)||minor==4&&major==4&&i32(encryption,4)==0x40;
      long plainBytes=i64(contents,0);
      // Ciphertext remains opaque. These checks identify the wrapper, not a
      // successful decryption or the hidden document/template content type.
      return knownVersion&&info.size>8&&plainBytes>0&&plainBytes<=MAX_INSPECT_BYTES&&packageStream.size>=8+plainBytes;
    }
    @Override public void close()throws IOException{input.close();}
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
    if(zip)try{office=office(file);}catch(IOException malformed){if(modernOffice(expected))throw new InvalidContent("Office 文件未下载完整或内容无效，请重新下载。");}
    if(expected.equals("pdf")&&!pdf)throw new InvalidContent("下载内容不是有效的 PDF，未保存错误文件。请回原网页重新下载。");
    if(ole&&modernOffice(expected)){
      try(EncryptedOffice encrypted=new EncryptedOffice(file)){
        if(encrypted.identifies())return new Info(withExtension(info.name,expected),forExtension(expected));
      }catch(IOException|RuntimeException invalid){throw new InvalidContent("加密 Office 文件未下载完整或封装无效，请重新下载。");}
    }
    if(modernOffice(expected)&&!expected.equals(office))throw new InvalidContent("下载内容与 Office 文件格式不符，未保存错误文件。请回原网页重新下载。");
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
