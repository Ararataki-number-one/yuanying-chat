import com.android.apksig.ApkVerifier;
import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Read-only SDK 37 verifier for the newly generated, unrotated test driver. */
public final class VerifyNativeInputSignature {
  static final List<String> NAMES = Arrays.asList("v1", "v2", "v3", "v31", "v4");
  static final class Scheme {
    final String name; final boolean verified; final List<String> certificates;
    final List<Signer> signers=new ArrayList<>();
    Scheme(String name, boolean verified, List<String> certificates) {
      this.name=name; this.verified=verified; this.certificates=certificates;
    }
  }
  static final class Signer {
    String certificate; List<String> chain; boolean errors, lineagePresent, rotationDev, signerDev;
    List<String> lineage=new ArrayList<>();
    Signer(X509Certificate leaf,List<X509Certificate> chain,boolean errors) throws Exception {
      this.certificate=certificate(leaf);this.chain=certificates(chain);this.errors=errors;
    }
    Signer(String leaf) {certificate=leaf;chain=new ArrayList<>(Arrays.asList(leaf));}
  }
  static final class Facts {
    boolean verified, containsErrors, lineagePresent, v32Detected;
    final List<String> effective=new ArrayList<>(), lineage=new ArrayList<>(), ignoredV1=new ArrayList<>();
    final List<Scheme> schemes=new ArrayList<>();
  }
  static String rejection(Facts f) {
    if(!f.verified || f.containsErrors) return "APK signature verification failed";
    if(f.effective.size()!=1) return "Exactly one effective signer required";
    String signer=f.effective.get(0);
    if(!signer.matches("[0-9a-f]{64}")) return "Invalid certificate digest";
    if(f.lineagePresent || !f.lineage.isEmpty()) return "Fresh input driver cannot have a signing lineage";
    if(f.v32Detected) return "V3.2/PQC signing is outside the fresh RSA driver contract";
    if(!f.ignoredV1.isEmpty()) return "Ignored V1 signer is not permitted";
    if(f.schemes.size()!=NAMES.size()) return "Incomplete signature scheme evidence";
    boolean any=false;
    for(int i=0;i<NAMES.size();i++) {
      Scheme s=f.schemes.get(i);
      if(!NAMES.get(i).equals(s.name)) return "Signature scheme order differs";
      if(s.signers.size()!=s.certificates.size()) return "Incomplete signer details: "+s.name;
      for(int j=0;j<s.signers.size();j++) {
        Signer info=s.signers.get(j);
        if(!s.certificates.get(j).equals(info.certificate) || info.errors || info.chain.size()!=1
            || !info.certificate.equals(info.chain.get(0)) || info.lineagePresent || !info.lineage.isEmpty()
            || info.rotationDev || info.signerDev) return "Signer is not a fresh single-certificate signer: "+s.name;
      }
      if(s.verified) {
        any=true;
        if(s.certificates.size()!=1 || !signer.equals(s.certificates.get(0)))
          return "Verified scheme must have exactly the same sole certificate: "+s.name;
      } else if(!s.certificates.isEmpty()) return "Unverified scheme contains signer evidence: "+s.name;
    }
    return any ? "" : "No verified signature scheme";
  }
  static String hex(byte[] bytes) {
    StringBuilder text=new StringBuilder();
    for(byte b:bytes) text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
    return text.toString();
  }
  static String digest(Path path) throws Exception {
    MessageDigest value=MessageDigest.getInstance("SHA-256");
    try(InputStream input=Files.newInputStream(path)) {
      byte[] buffer=new byte[1024*1024]; int length;
      while((length=input.read(buffer))!=-1) value.update(buffer,0,length);
    }
    return hex(value.digest());
  }
  static String certificate(X509Certificate value) throws Exception {
    return hex(MessageDigest.getInstance("SHA-256").digest(value.getEncoded()));
  }
  static List<String> certificates(List<X509Certificate> values) throws Exception {
    List<String> result=new ArrayList<>();
    for(X509Certificate value:values) result.add(certificate(value));
    return result;
  }
  static Map<String,Object> map(Object... values) {
    Map<String,Object> result=new LinkedHashMap<>();
    for(int i=0;i<values.length;i+=2) result.put((String)values[i],values[i+1]);
    return result;
  }
  static Facts facts(ApkVerifier.Result result) throws Exception {
    Facts f=new Facts(); f.verified=result.isVerified(); f.containsErrors=result.containsErrors();
    f.effective.addAll(certificates(result.getSignerCertificates()));
    f.lineagePresent=result.getSigningCertificateLineage()!=null;
    if(f.lineagePresent) f.lineage.addAll(certificates(result.getSigningCertificateLineage().getCertificatesInLineage()));
    f.v32Detected=result.isVerifiedUsingV32Scheme() || result.getV32SchemeSigner()!=null;
    for(ApkVerifier.Result.V1SchemeSignerInfo s:result.getV1SchemeIgnoredSigners()) f.ignoredV1.add(certificate(s.getCertificate()));
    Scheme v1=new Scheme("v1",result.isVerifiedUsingV1Scheme(),new ArrayList<>());
    Scheme v2=new Scheme("v2",result.isVerifiedUsingV2Scheme(),new ArrayList<>());
    Scheme v3=new Scheme("v3",result.isVerifiedUsingV3Scheme(),new ArrayList<>());
    Scheme v31=new Scheme("v31",result.isVerifiedUsingV31Scheme(),new ArrayList<>());
    Scheme v4=new Scheme("v4",result.isVerifiedUsingV4Scheme(),new ArrayList<>());
    for(ApkVerifier.Result.V1SchemeSignerInfo info:result.getV1SchemeSigners()) add(v1,new Signer(info.getCertificate(),info.getCertificateChain(),info.containsErrors()));
    for(ApkVerifier.Result.V2SchemeSignerInfo info:result.getV2SchemeSigners()) add(v2,new Signer(info.getCertificate(),info.getCertificates(),info.containsErrors()));
    for(ApkVerifier.Result.V3SchemeSignerInfo info:result.getV3SchemeSigners()) add(v3,v3Signer(info));
    for(ApkVerifier.Result.V3SchemeSignerInfo info:result.getV31SchemeSigners()) add(v31,v3Signer(info));
    for(ApkVerifier.Result.V4SchemeSignerInfo info:result.getV4SchemeSigners()) add(v4,new Signer(info.getCertificate(),info.getCertificates(),info.containsErrors()));
    f.schemes.addAll(Arrays.asList(v1,v2,v3,v31,v4));
    return f;
  }
  static void add(Scheme scheme,Signer info) {scheme.signers.add(info);scheme.certificates.add(info.certificate);}
  static Signer v3Signer(ApkVerifier.Result.V3SchemeSignerInfo info) throws Exception {
    Signer signer=new Signer(info.getCertificate(),info.getCertificates(),info.containsErrors());
    signer.lineagePresent=info.getSigningCertificateLineage()!=null;
    if(signer.lineagePresent)signer.lineage=certificates(info.getSigningCertificateLineage().getCertificatesInLineage());
    signer.rotationDev=info.getRotationTargetsDevRelease();signer.signerDev=info.getSignerTargetsDevRelease();
    return signer;
  }
  static String json(Object value) {
    if(value==null) return "null";
    if(value instanceof Boolean || value instanceof Number) return value.toString();
    if(value instanceof Map) {
      StringBuilder out=new StringBuilder("{"); boolean first=true;
      for(Map.Entry<?,?> item:((Map<?,?>)value).entrySet()) {
        if(!first)out.append(',');first=false;out.append(json(item.getKey())).append(':').append(json(item.getValue()));
      }
      return out.append('}').toString();
    }
    if(value instanceof Iterable) {
      StringBuilder out=new StringBuilder("["); boolean first=true;
      for(Object item:(Iterable<?>)value) {if(!first)out.append(',');first=false;out.append(json(item));}
      return out.append(']').toString();
    }
    StringBuilder out=new StringBuilder("\"");
    for(char c:value.toString().toCharArray()) {
      if(c=='"'||c=='\\')out.append('\\').append(c);
      else if(c<32 || c>=127)out.append(String.format(java.util.Locale.ROOT,"\\u%04x",(int)c));
      else out.append(c);
    }
    return out.append('"').toString();
  }
  public static void main(String[] args) {
    Map<String,Object> out=map("schema",1,"status","failed","error",""); int code=1;
    try {
      if(args.length!=6)throw new IllegalArgumentException("APK, verifier source and four source/run identifiers required");
      if(!args[2].matches("[0-9a-f]{40}") || !args[3].matches("[0-9a-f]{40}") || !args[4].matches("[0-9]+") || !args[5].matches("[0-9]+"))
        throw new IllegalArgumentException("Invalid source/run identity");
      out.putAll(map("sourceCommit",args[2],"sourceTree",args[3],"runId",args[4],"runAttempt",args[5]));
      Path apk=new File(args[0]).toPath(), source=new File(args[1]).toPath();
      Path jar=new File(ApkVerifier.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toPath().toRealPath();
      out.put("loadedApksignerJarPath",jar.toString());
      if(!Files.isRegularFile(jar))throw new IllegalArgumentException("Verifier implementation must load from the pinned JAR");
      String apkHash=digest(apk), sourceHash=digest(source), jarHash=digest(jar); long bytes=Files.size(apk);
      out.putAll(map("apkSha256",apkHash,"apkBytes",bytes,"apksignerJarSha256",jarHash,"verifierSourceSha256",sourceHash));
      Facts f=facts(new ApkVerifier.Builder(apk.toFile()).build().verify());
      List<Object> schemes=new ArrayList<>();
      for(Scheme scheme:f.schemes) {
        List<Object> details=new ArrayList<>();
        for(Signer signer:scheme.signers)details.add(map("certificateSha256",signer.certificate,"certificateChainSha256",signer.chain,
          "containsErrors",signer.errors,"lineagePresent",signer.lineagePresent,"lineageCertificateSha256",signer.lineage,
          "rotationTargetsDevRelease",signer.rotationDev,"signerTargetsDevRelease",signer.signerDev));
        schemes.add(map("name",scheme.name,"verified",scheme.verified,"signerCertificateSha256",scheme.certificates,"signers",details));
      }
      out.putAll(map("verified",f.verified,"containsErrors",f.containsErrors,
        "effectiveSignerCertificateSha256",f.effective,"schemes",schemes,"lineagePresent",f.lineagePresent,
        "lineageCertificateSha256",f.lineage,"noRotation",!f.lineagePresent&&f.lineage.isEmpty(),
        "ignoredV1SignerCertificateSha256",f.ignoredV1,"v32Detected",f.v32Detected,"signerCertificateSha256",""));
      boolean stable=bytes==Files.size(apk)&&apkHash.equals(digest(apk))&&sourceHash.equals(digest(source))&&jarHash.equals(digest(jar));
      out.put("inputsUnchangedDuringVerification",stable);
      if(!stable)throw new IllegalStateException("Signature verification inputs changed");
      String error=rejection(f);
      if(!error.isEmpty())throw new IllegalStateException(error);
      out.put("signerCertificateSha256",f.effective.get(0));out.put("status","passed");code=0;
    } catch(Throwable failure) {
      out.put("error",failure.getClass().getName()+": "+String.valueOf(failure.getMessage()));
    }
    System.out.println(json(out));
    if(code!=0)System.exit(code);
  }
}
