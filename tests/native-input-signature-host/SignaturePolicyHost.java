import java.util.ArrayList;
import java.util.Arrays;
import java.util.function.Consumer;

/** Executes the production policy; synthetic facts do not claim cryptographic verification. */
public final class SignaturePolicyHost {
  static int count;
  static String cert="a".repeat(64), other="b".repeat(64);
  static VerifyNativeInputSignature.Facts valid() {
    VerifyNativeInputSignature.Facts f=new VerifyNativeInputSignature.Facts();f.verified=true;f.effective.add(cert);
    for(String name:VerifyNativeInputSignature.NAMES) {
      boolean used=name.equals("v2")||name.equals("v3");
      VerifyNativeInputSignature.Scheme s=new VerifyNativeInputSignature.Scheme(name,used,new ArrayList<>());
      if(used)VerifyNativeInputSignature.add(s,new VerifyNativeInputSignature.Signer(cert));
      f.schemes.add(s);
    }
    return f;
  }
  static void expect(String label,boolean accepted,Consumer<VerifyNativeInputSignature.Facts> change) {
    VerifyNativeInputSignature.Facts f=valid();change.accept(f);
    boolean actual=VerifyNativeInputSignature.rejection(f).isEmpty();
    if(actual!=accepted)throw new AssertionError(label+": "+VerifyNativeInputSignature.rejection(f));count++;
  }
  public static void main(String[] args) {
    expect("fresh-v2-v3",true,f->{});
    expect("unverified",false,f->f.verified=false);
    expect("global-errors",false,f->f.containsErrors=true);
    expect("no-effective",false,f->f.effective.clear());
    expect("two-effective",false,f->f.effective.add(other));
    expect("same-cert-two-signers",false,f->f.effective.add(cert));
    expect("bad-digest",false,f->f.effective.set(0,"invalid"));
    expect("lineage-present-even-one",false,f->f.lineagePresent=true);
    expect("lineage-hidden-global",false,f->f.lineage.add(cert));
    expect("v32",false,f->f.v32Detected=true);
    expect("ignored-v1",false,f->f.ignoredV1.add(cert));
    expect("missing-scheme",false,f->f.schemes.remove(0));
    expect("scheme-order",false,f->java.util.Collections.swap(f.schemes,0,1));
    for(int i=0;i<VerifyNativeInputSignature.NAMES.size();i++) {
      final int at=i;
      expect("fresh-single-"+i,true,f->{
        f.schemes.clear();for(int j=0;j<VerifyNativeInputSignature.NAMES.size();j++) {
          VerifyNativeInputSignature.Scheme s=new VerifyNativeInputSignature.Scheme(VerifyNativeInputSignature.NAMES.get(j),at==j,new ArrayList<>());
          if(at==j)VerifyNativeInputSignature.add(s,new VerifyNativeInputSignature.Signer(cert));f.schemes.add(s);
        }
      });
      expect("unverified-has-signer-"+i,false,f->{
        VerifyNativeInputSignature.Scheme s=new VerifyNativeInputSignature.Scheme(VerifyNativeInputSignature.NAMES.get(at),false,new ArrayList<>());
        VerifyNativeInputSignature.add(s,new VerifyNativeInputSignature.Signer(cert));f.schemes.set(at,s);
      });
      expect("verified-empty-"+i,false,f->f.schemes.set(at,new VerifyNativeInputSignature.Scheme(VerifyNativeInputSignature.NAMES.get(at),true,new ArrayList<>())));
      expect("verified-multiple-"+i,false,f->{
        VerifyNativeInputSignature.Scheme s=new VerifyNativeInputSignature.Scheme(VerifyNativeInputSignature.NAMES.get(at),true,new ArrayList<>());
        VerifyNativeInputSignature.add(s,new VerifyNativeInputSignature.Signer(cert));VerifyNativeInputSignature.add(s,new VerifyNativeInputSignature.Signer(cert));f.schemes.set(at,s);
      });
      expect("verified-other-"+i,false,f->{
        VerifyNativeInputSignature.Scheme s=new VerifyNativeInputSignature.Scheme(VerifyNativeInputSignature.NAMES.get(at),true,new ArrayList<>());
        VerifyNativeInputSignature.add(s,new VerifyNativeInputSignature.Signer(other));f.schemes.set(at,s);
      });
    }
    expect("no-schemes-verified",false,f->{
      f.schemes.clear();for(String n:VerifyNativeInputSignature.NAMES)f.schemes.add(new VerifyNativeInputSignature.Scheme(n,false,new ArrayList<>()));
    });
    expect("missing-signer-details",false,f->f.schemes.get(2).signers.clear());
    expect("different-leaf-detail",false,f->f.schemes.get(2).signers.get(0).certificate=other);
    expect("signer-errors",false,f->f.schemes.get(2).signers.get(0).errors=true);
    expect("empty-chain",false,f->f.schemes.get(2).signers.get(0).chain.clear());
    expect("multiple-chain",false,f->f.schemes.get(2).signers.get(0).chain.add(other));
    expect("different-chain",false,f->f.schemes.get(2).signers.get(0).chain.set(0,other));
    expect("per-signer-lineage-present",false,f->f.schemes.get(2).signers.get(0).lineagePresent=true);
    expect("per-signer-lineage-content",false,f->f.schemes.get(2).signers.get(0).lineage.add(cert));
    expect("rotation-dev",false,f->f.schemes.get(2).signers.get(0).rotationDev=true);
    expect("signer-dev",false,f->f.schemes.get(2).signers.get(0).signerDev=true);
    System.out.println("{\"status\":\"passed\",\"checkCount\":"+count+",\"scope\":\"actual production policy with synthetic facts; no cryptographic proof\"}");
  }
}
