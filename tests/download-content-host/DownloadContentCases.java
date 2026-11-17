package local.pocketchat;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
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
    String type=member.startsWith("word/")?"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml":member.startsWith("xl/")?"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml":"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml";
    return office(root,name,member,type);
  }
  static File office(File root,String name,String member,String type)throws IOException {
    return officeXml(root,name,member,"<?xml version=\"1.0\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Override PartName=\"/"+member+"\" ContentType=\""+type+"\"/></Types>",StandardCharsets.UTF_8);
  }
  static File officeXml(File root,String name,String member,String types,java.nio.charset.Charset encoding)throws IOException {
    return officePackage(root,name,member,types,encoding,relationships(member));
  }
  static String relationships(String member){return "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\""+member+"\"/></Relationships>";}
  static File officePackage(File root,String name,String member,String types,java.nio.charset.Charset encoding,String relations)throws IOException {
    File file=new File(root,name);
    try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))){
      zip.putNextEntry(new ZipEntry("[Content_Types].xml"));zip.write(types.getBytes(encoding));zip.closeEntry();
      if(relations!=null){zip.putNextEntry(new ZipEntry("_rels/.rels"));zip.write(relations.getBytes(StandardCharsets.UTF_8));zip.closeEntry();}
      zip.putNextEntry(new ZipEntry(member));zip.write("<?xml version=\"1.0\"?><document/>".getBytes(StandardCharsets.UTF_8));zip.closeEntry();
    }return file;
  }
  static void u16(byte[] bytes,int at,int value){bytes[at]=(byte)value;bytes[at+1]=(byte)(value>>>8);}
  static void i32(byte[] bytes,int at,int value){for(int i=0;i<4;i++)bytes[at+i]=(byte)(value>>>(8*i));}
  static void i64(byte[] bytes,int at,long value){for(int i=0;i<8;i++)bytes[at+i]=(byte)(value>>>(8*i));}
  static int get32(byte[] bytes,int at){return (bytes[at]&255)|((bytes[at+1]&255)<<8)|((bytes[at+2]&255)<<16)|(bytes[at+3]<<24);}
  static void directory(byte[] data,int at,String name,int kind,int left,int right,int child,int start,long size){
    byte[] label=(name+"\0").getBytes(StandardCharsets.UTF_16LE);System.arraycopy(label,0,data,at,label.length);u16(data,at+64,label.length);data[at+66]=(byte)kind;data[at+67]=1;
    i32(data,at+68,left);i32(data,at+72,right);i32(data,at+76,child);i32(data,at+116,start);i64(data,at+120,size);
  }
  /** Real CFB allocation tables/streams with opaque synthetic ciphertext, not a decryption oracle. */
  static byte[] encrypted(int version,int payloadBytes){
    int sector=version==3?512:4096,perFat=sector/4;
    byte[] csp="Microsoft Enhanced RSA and AES Cryptographic Provider\0".getBytes(StandardCharsets.UTF_16LE);
    int headerSize=32+csp.length;byte[] info=new byte[12+headerSize+72];
    u16(info,0,4);u16(info,2,2);i32(info,4,0x24);i32(info,8,headerSize);i32(info,12,0x24);i32(info,20,0x660e);i32(info,24,0x8004);i32(info,28,128);i32(info,32,24);System.arraycopy(csp,0,info,44,csp.length);
    i32(info,12+headerSize,16);i32(info,12+headerSize+36,20);
    byte[] packageBytes=new byte[8+payloadBytes];i64(packageBytes,0,payloadBytes-7);for(int i=8;i<packageBytes.length;i++)packageBytes[i]=(byte)(i*31);
    boolean small=packageBytes.length<4096;int infoMinis=(info.length+63)/64,packageMinis=small?(packageBytes.length+63)/64:0,miniBytes=(infoMinis+packageMinis)*64;
    int miniFatSectors=(infoMinis+packageMinis+perFat-1)/perFat,rootSectors=(miniBytes+sector-1)/sector,packageSectors=small?0:(packageBytes.length+sector-1)/sector;
    int base=1+miniFatSectors+rootSectors+packageSectors,fatCount=1,difatCount=0;
    for(;;){int fat=(base+fatCount+difatCount+perFat-1)/perFat,difat=(Math.max(0,fat-109)+perFat-2)/(perFat-1);if(fat==fatCount&&difat==difatCount)break;fatCount=fat;difatCount=difat;}
    int dir=fatCount+difatCount,miniFirst=dir+1,rootFirst=miniFirst+miniFatSectors,packageFirst=rootFirst+rootSectors,count=packageFirst+packageSectors;
    byte[] data=new byte[(count+1)*sector];byte[] signature={(byte)0xd0,(byte)0xcf,0x11,(byte)0xe0,(byte)0xa1,(byte)0xb1,0x1a,(byte)0xe1};System.arraycopy(signature,0,data,0,8);
    u16(data,24,0x3e);u16(data,26,version);u16(data,28,0xfffe);u16(data,30,version==3?9:12);u16(data,32,6);i32(data,40,version==4?1:0);i32(data,44,fatCount);i32(data,48,dir);i32(data,56,4096);i32(data,60,miniFirst);i32(data,64,miniFatSectors);i32(data,68,difatCount==0?-2:fatCount);i32(data,72,difatCount);
    for(int i=0;i<109;i++)i32(data,76+4*i,i<fatCount?i:-1);
    for(int n=0;n<difatCount;n++){int offset=(fatCount+n+1)*sector;for(int i=0;i<perFat-1;i++){int index=109+n*(perFat-1)+i;i32(data,offset+4*i,index<fatCount?index:-1);}i32(data,offset+sector-4,n+1==difatCount?-2:fatCount+n+1);}
    int[] fat=new int[fatCount*perFat];Arrays.fill(fat,-1);for(int i=0;i<fatCount;i++)fat[i]=-3;for(int i=0;i<difatCount;i++)fat[fatCount+i]=-4;fat[dir]=-2;
    for(int i=0;i<miniFatSectors;i++)fat[miniFirst+i]=i+1==miniFatSectors?-2:miniFirst+i+1;
    for(int i=0;i<rootSectors;i++)fat[rootFirst+i]=i+1==rootSectors?-2:rootFirst+i+1;
    for(int i=0;i<packageSectors;i++)fat[packageFirst+i]=i+1==packageSectors?-2:packageFirst+i+1;
    for(int i=0;i<fat.length;i++)i32(data,sector+(i/perFat)*sector+4*(i%perFat),fat[i]);
    int directory=(dir+1)*sector;directory(data,directory,"Root Entry",5,-1,-1,1,rootFirst,miniBytes);directory(data,directory+128,"EncryptionInfo",2,-1,2,-1,0,info.length);directory(data,directory+256,"EncryptedPackage",2,-1,-1,-1,small?infoMinis:packageFirst,packageBytes.length);
    for(int i=0;i<miniFatSectors*perFat;i++)i32(data,(miniFirst+1)*sector+4*i,-1);
    for(int i=0;i<infoMinis;i++)i32(data,(miniFirst+1)*sector+4*i,i+1==infoMinis?-2:i+1);
    for(int i=0;i<packageMinis;i++)i32(data,(miniFirst+1)*sector+4*(infoMinis+i),i+1==packageMinis?-2:infoMinis+i+1);
    System.arraycopy(info,0,data,(rootFirst+1)*sector,info.length);System.arraycopy(packageBytes,0,data,small?(rootFirst+1)*sector+infoMinis*64:(packageFirst+1)*sector,packageBytes.length);return data;
  }
  interface Mutation {void apply(byte[] data);}
  static void rejectsEnvelope(File root,String label,byte[] original,Mutation mutation)throws Exception{
    byte[] data=original.clone();mutation.apply(data);File file=bytes(root,"encrypted-invalid.part",data);rejects(label,()->DownloadFileInfo.inspect(file,"report.docx",DownloadFileInfo.DOCX));
  }
  static void officeVariants(File root)throws Exception{
    String[][] cases={
      {"docm","word/document.xml","application/vnd.ms-word.document.macroEnabled.main+xml","application/vnd.ms-word.document.macroEnabled.12"},
      {"dotx","word/document.xml","application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml","application/vnd.openxmlformats-officedocument.wordprocessingml.template"},
      {"dotm","word/document.xml","application/vnd.ms-word.template.macroEnabledTemplate.main+xml","application/vnd.ms-word.template.macroEnabled.12"},
      {"xlsm","xl/workbook.xml","application/vnd.ms-excel.sheet.macroEnabled.main+xml","application/vnd.ms-excel.sheet.macroEnabled.12"},
      {"xltx","xl/workbook.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml","application/vnd.openxmlformats-officedocument.spreadsheetml.template"},
      {"xltm","xl/workbook.xml","application/vnd.ms-excel.template.macroEnabled.main+xml","application/vnd.ms-excel.template.macroEnabled.12"},
      {"xlam","xl/workbook.xml","application/vnd.ms-excel.addin.macroEnabled.main+xml","application/vnd.ms-excel.addin.macroEnabled.12"},
      {"xlsb","xl/workbook.bin","application/vnd.ms-excel.sheet.binary.macroEnabled.main","application/vnd.ms-excel.sheet.binary.macroEnabled.12"},
      {"pptm","ppt/presentation.xml","application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml","application/vnd.ms-powerpoint.presentation.macroEnabled.12"},
      {"potx","ppt/presentation.xml","application/vnd.openxmlformats-officedocument.presentationml.template.main+xml","application/vnd.openxmlformats-officedocument.presentationml.template"},
      {"potm","ppt/presentation.xml","application/vnd.ms-powerpoint.template.macroEnabled.main+xml","application/vnd.ms-powerpoint.template.macroEnabled.12"},
      {"ppsx","ppt/presentation.xml","application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml","application/vnd.openxmlformats-officedocument.presentationml.slideshow"},
      {"ppsm","ppt/presentation.xml","application/vnd.ms-powerpoint.slideshow.macroEnabled.main+xml","application/vnd.ms-powerpoint.slideshow.macroEnabled.12"}
    };
    for(String[] value:cases){
      File file=office(root,"variant.part",value[1],value[2]);byte[] original=Files.readAllBytes(file.toPath());String expectedMime=value[3].toLowerCase(Locale.ROOT);
      DownloadFileInfo.Info actual=DownloadFileInfo.inspect(file,"document."+value[0],value[3]);check(value[0]+" keeps its real extension and MIME",actual.name.equals("document."+value[0])&&actual.mime.equals(expectedMime));
      actual=DownloadFileInfo.inspect(file,"download.bin",DownloadFileInfo.BINARY);check(value[0]+" is identified from main content type",actual.name.equals("download."+value[0])&&actual.mime.equals(expectedMime));
      check(value[0]+" bytes are preserved",Arrays.equals(original,Files.readAllBytes(file.toPath())));
      String wrong=value[1].startsWith("word")?"docx":value[1].startsWith("xl")?"xlsx":"pptx";
      rejects(value[0]+" cannot masquerade as "+wrong,()->DownloadFileInfo.inspect(file,"wrong."+wrong,DownloadFileInfo.forExtension(wrong)));
    }
    File custom=office(root,"custom-main.part","content/main.xml","application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml");
    check("Main part identity does not require a conventional ZIP path",DownloadFileInfo.inspect(custom,"template.dotx",DownloadFileInfo.BINARY).name.equals("template.dotx"));
    String declaration="<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>";
    String open="<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">";
    String defaultDocx="<Default Extension=\"xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>";
    File defaultType=officeXml(root,"default.part","word/document.xml",open+defaultDocx+"</Types>",StandardCharsets.UTF_8);
    byte[] defaultBytes=Files.readAllBytes(defaultType.toPath());
    check("OPC Default can define the actual root Office main part",DownloadFileInfo.inspect(defaultType,"report.docx",DownloadFileInfo.DOCX).name.equals("report.docx"));
    check("Default-defined Office bytes are preserved",Arrays.equals(defaultBytes,Files.readAllBytes(defaultType.toPath())));
    File preferred=officeXml(root,"override-priority.part","word/document.xml",open+defaultDocx.replace("wordprocessingml.document.main+xml","wordprocessingml.template.main+xml")+declaration+"</Types>",StandardCharsets.UTF_8);
    check("The actual main part Override wins over its Default",DownloadFileInfo.inspect(preferred,"report.docx",DownloadFileInfo.DOCX).name.equals("report.docx"));
    File wrongOverride=officeXml(root,"wrong-override.part","word/document.xml",open+defaultDocx+declaration.replace("application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml","application/xml")+"</Types>",StandardCharsets.UTF_8);
    rejects("A non-Office Override cannot fall back to a default Office type",()->DownloadFileInfo.inspect(wrongOverride,"report.docx",DownloadFileInfo.DOCX));
    File defaultDuplicate=officeXml(root,"duplicate-default.part","word/document.xml",open+defaultDocx+defaultDocx+"</Types>",StandardCharsets.UTF_8);
    rejects("Duplicate defaults for the main part are ambiguous",()->DownloadFileInfo.inspect(defaultDuplicate,"report.docx",DownloadFileInfo.DOCX));
    File noRelations=officePackage(root,"no-relations.part","word/document.xml",open+defaultDocx+"</Types>",StandardCharsets.UTF_8,null);
    rejects("Default Office MIME without a root main relationship is insufficient",()->DownloadFileInfo.inspect(noRelations,"report.docx",DownloadFileInfo.DOCX));
    String relation=relationships("word/document.xml");
    File repeatedRelation=officePackage(root,"ambiguous-relations.part","word/document.xml",open+defaultDocx+"</Types>",StandardCharsets.UTF_8,relation.replace("</Relationships>",relation.substring(relation.indexOf("<Relationship Id"),relation.indexOf("</Relationships>"))+"</Relationships>"));
    rejects("More than one package Office main relationship is ambiguous",()->DownloadFileInfo.inspect(repeatedRelation,"report.docx",DownloadFileInfo.DOCX));
    File external=officePackage(root,"external-main.part","word/document.xml",open+defaultDocx+"</Types>",StandardCharsets.UTF_8,relation.replace("Target=","TargetMode=\"External\" Target="));
    rejects("An external Office main relationship cannot identify local bytes",()->DownloadFileInfo.inspect(external,"report.docx",DownloadFileInfo.DOCX));
    File strict=officePackage(root,"strict-main.part","word/document.xml",open+defaultDocx+"</Types>",StandardCharsets.UTF_8,relation.replace("http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument","http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument"));
    check("Strict OOXML root Office relationship is recognized",DownloadFileInfo.inspect(strict,"report.docx",DownloadFileInfo.DOCX).name.equals("report.docx"));
    File duplicate=officeXml(root,"duplicate.part","word/document.xml",open+declaration+declaration+"</Types>",StandardCharsets.UTF_8);
    rejects("Duplicate main part declarations are not silently accepted",()->DownloadFileInfo.inspect(duplicate,"report.docx",DownloadFileInfo.DOCX));
    File absent=officePackage(root,"missing-main.part","word/other.xml",open+declaration+"</Types>",StandardCharsets.UTF_8,relation);
    rejects("A declared main part must exist",()->DownloadFileInfo.inspect(absent,"report.docx",DownloadFileInfo.DOCX));
    File unknown=officeXml(root,"unknown-type.part","word/document.xml",open+"</Types>",StandardCharsets.UTF_8);
    rejects("ZIP paths alone cannot identify a Word document",()->DownloadFileInfo.inspect(unknown,"report.docx",DownloadFileInfo.DOCX));
    File namespace=officeXml(root,"wrong-namespace.part","word/document.xml","<Types>"+declaration+"</Types>",StandardCharsets.UTF_8);
    rejects("Content type declarations need the OPC namespace",()->DownloadFileInfo.inspect(namespace,"report.docx",DownloadFileInfo.DOCX));
    for(java.nio.charset.Charset encoding:new java.nio.charset.Charset[]{StandardCharsets.UTF_8,StandardCharsets.UTF_16LE,StandardCharsets.UTF_16BE}){
      String xml="<?xml version=\"1.0\" encoding=\""+encoding.name()+"\"?><!DOCTYPE Types [<!ENTITY ignored SYSTEM \"file:///missing\">]>"+open+declaration+"</Types>";
      File dtd=officeXml(root,"dtd.part","word/document.xml",xml,encoding);
      rejects("DTD rejected before expansion in "+encoding.name(),()->DownloadFileInfo.inspect(dtd,"report.docx",DownloadFileInfo.DOCX));
    }
  }
  static void encryptedOffice(File root)throws Exception{
    for(int version:new int[]{3,4})for(int payload:new int[]{80,4096}){
      byte[] original=encrypted(version,payload);File file=bytes(root,"encrypted.part",original);
      for(String extension:new String[]{"docx","docm","dotx","dotm","xlsx","xlsm","pptx","ppsm"}){
        DownloadFileInfo.Info result=DownloadFileInfo.inspect(file,"protected."+extension,DownloadFileInfo.forExtension(extension));
        check("CFB v"+version+" payload "+payload+" preserves explicit "+extension,result.name.equals("protected."+extension)&&result.mime.equals(DownloadFileInfo.forExtension(extension)));
      }
      check("CFB opaque bytes are never rewritten",Arrays.equals(original,Files.readAllBytes(file.toPath())));
      rejects("Encrypted Office is never classified as PDF",()->DownloadFileInfo.inspect(file,"wrong.pdf",DownloadFileInfo.PDF));
    }
    byte[] ordinary=encrypted(3,4096);int sector=512,dir=(get32(ordinary,48)+1)*sector,mini=(get32(ordinary,60)+1)*sector;
    int rootSector=get32(ordinary,dir+116),packageSector=get32(ordinary,dir+256+116);
    File legacyHigh=bytes(root,"legacy-high-dword.part",ordinary.clone());byte[] high=Files.readAllBytes(legacyHigh.toPath());i32(high,dir+128+124,0xdeadbeef);i32(high,dir+256+124,0xdeadbeef);Files.write(legacyHigh.toPath(),high);
    check("CFB v3 ignores legacy uninitialized high stream-size DWORD",DownloadFileInfo.inspect(legacyHigh,"protected.docx",DownloadFileInfo.DOCX).name.equals("protected.docx"));
    byte[] large=encrypted(3,8*1024*1024);check("Large fixture actually uses DIFAT",get32(large,72)>0);File difat=bytes(root,"difat.part",large);
    check("A full DIFAT chain identifies the encrypted wrapper",DownloadFileInfo.inspect(difat,"large.docx",DownloadFileInfo.DOCX).name.equals("large.docx"));
    rejectsEnvelope(root,"Missing root EncryptionInfo is not encrypted OOXML",ordinary,data->data[dir+128]='X');
    rejectsEnvelope(root,"Missing root EncryptedPackage is not encrypted OOXML",ordinary,data->data[dir+256]='X');
    rejectsEnvelope(root,"Directory cycles are rejected",ordinary,data->i32(data,dir+128+72,1));
    rejectsEnvelope(root,"Directory references outside its allocation are rejected",ordinary,data->i32(data,dir+128+72,Integer.MAX_VALUE));
    rejectsEnvelope(root,"The encryption descriptor cannot be a storage",ordinary,data->data[dir+128+66]=1);
    rejectsEnvelope(root,"EncryptionInfo MiniFAT cycles are rejected",ordinary,data->i32(data,mini,0));
    rejectsEnvelope(root,"A truncated encryption descriptor chain is rejected",ordinary,data->i32(data,mini,-2));
    rejectsEnvelope(root,"EncryptedPackage FAT cycles are rejected",ordinary,data->i32(data,sector+packageSector*4,packageSector));
    rejectsEnvelope(root,"EncryptedPackage cannot point into FAT metadata",ordinary,data->i32(data,dir+256+116,0));
    rejectsEnvelope(root,"Out-of-range encrypted stream sectors are rejected",ordinary,data->i32(data,dir+256+116,Integer.MAX_VALUE));
    rejectsEnvelope(root,"Oversized declared ciphertext is rejected",ordinary,data->i32(data,dir+256+120,600*1024*1024));
    rejectsEnvelope(root,"Unknown encryption headers are not accepted",ordinary,data->u16(data,(rootSector+1)*sector,99));
    rejectsEnvelope(root,"Impossible encrypted package plaintext lengths are rejected",ordinary,data->i64(data,(packageSector+1)*sector,100000));
    rejectsEnvelope(root,"FAT sectors require their actual marker",ordinary,data->i32(data,sector,0));
    rejectsEnvelope(root,"DIFAT cycles are rejected",large,data->{int id=get32(data,68);i32(data,(id+1)*512+508,id);});
    File cut=bytes(root,"truncated-cfb.part",Arrays.copyOf(ordinary,ordinary.length-17));rejects("Truncated CFB file is rejected",()->DownloadFileInfo.inspect(cut,"report.docx",DownloadFileInfo.DOCX));
    File magic=bytes(root,"ole-signature.part",Arrays.copyOf(ordinary,8));rejects("An OLE signature alone cannot authorize OOXML",()->DownloadFileInfo.inspect(magic,"report.docx",DownloadFileInfo.DOCX));
    Thread.currentThread().interrupt();try{rejects("CFB inspection honors cancellation",()->DownloadFileInfo.inspect(difat,"large.docx",DownloadFileInfo.DOCX));}finally{Thread.interrupted();}
  }
  static void externalEncryptedOffice(String[] paths)throws Exception{
    String[][] expected={
      {"ecma376standard_password.docx","7168","d265dcf02f7d552486229b8c67a627ef3752fe6802b02fd2d2d485fcfbbac5de","application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
      {"example_password.docx","18432","0605624697328060fdc75ca9929ea20b9d63ebed9387ff1a97aaf9979757234a","application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
      {"example_password.xlsx","14848","3f792e3902a615bf0e91771f3f3016b80d59098b8e492efcdc0752748e15b997","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
      {"ecma376agile_sha1_password.xlsx","13824","4d6437ede946382c471b681c7721e2874de569f829238c5a6b25321b172f104b","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    };
    check("All four independent encrypted samples are present",paths.length==expected.length);
    for(int i=0;i<expected.length;i++){
      String[] value=expected[i];File file=new File(paths[i]);byte[] original=Files.readAllBytes(file.toPath());StringBuilder hash=new StringBuilder();
      for(byte next:MessageDigest.getInstance("SHA-256").digest(original))hash.append(String.format(Locale.ROOT,"%02x",next&255));
      check(value[0]+" independently matches pinned source bytes",file.getName().equals(value[0])&&original.length==Integer.parseInt(value[1])&&hash.toString().equals(value[2]));
      DownloadFileInfo.Info result=DownloadFileInfo.inspect(file,value[0],value[3]);
      check(value[0]+" retains its name",result.name.equals(value[0]));check(value[0]+" retains its MIME",result.mime.equals(value[3]));
      check(value[0]+" retains every original byte",Arrays.equals(original,Files.readAllBytes(file.toPath())));
    }
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
      officeVariants(root);encryptedOffice(root);externalEncryptedOffice(args);
      System.out.println("{\"status\":\"passed\",\"checks\":"+passed+",\"actualAndroidExecution\":false,\"encryptedExternalSamples\":4,\"scope\":\"Actual production metadata and document checks on local byte streams, synthetic CFB boundary cases and four pinned independent encrypted Office files; no decryption, full Office or PDF renderer claim\"}");
    }finally{File[] files=root.listFiles();if(files!=null)for(File file:files)file.delete();root.delete();}
  }
}
