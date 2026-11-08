package local.pocketchat;

import android.graphics.Bitmap;

/** Same transparent curved coating for software canvases and API 26–32.
 * A raster is built only for new geometry/theme or a new press, never per frame.
 * This fallback deliberately does not pretend to refract the native backdrop.
 */
final class GlassMaterialRaster {
  static Bitmap create(int width,int height,float density,float radius,boolean dark,
      float lightX,float lightY,float bumpX,float bumpY,float touchX,float touchY,float pressure,float bend){
    float scale=Math.min(1f,2f/density);
    int margin=(int)Math.ceil(LiquidGlassDrawable.RENDER_MARGIN_DP*density);
    int w=Math.max(1,(int)Math.ceil((width+2*margin)*scale)),h=Math.max(1,(int)Math.ceil((height+2*margin)*scale));
    int[] colors=new int[w*h];
    // The caller draws this padded bitmap into the matching expanded bounds.
    // Keep the material and touch coordinates in the original control space.
    double sampleX=(width+2d*margin)/w,sampleY=(height+2d*margin)/h;
    double bx=width*.5-4*density,by=height*.5-4*density;
    double bevel=Math.max(2*density,Math.min((dark?6.5:4.5)*density,Math.min(bx,by)*.30));
    double sigma=Math.max(8*density,Math.min(by*1.15,32*density)),sigma2=sigma*sigma;
    double ll=Math.hypot(lightX,lightY),lx=lightX/ll,ly=lightY/ll;
    double veil=dark?.15:.38,shadowStrength=dark?.12:.022,shadowFalloff=dark?1.8:1.25;
    double tr=dark?.12:.995,tg=dark?.15:.998,tb=dark?.20:1;
    double aa=Math.max(.7,density*.28);
    for(int y=0;y<h;y++)for(int x=0;x<w;x++){
      double px=(x+.5)*sampleX-margin,py=(y+.5)*sampleY-margin,dx=px-width*.5,dy=py-height*.5;
      double qx=Math.abs(dx)-bx+radius,qy=Math.abs(dy)-by+radius;
      double ox=Math.max(qx,0),oy=Math.max(qy,0),length=Math.hypot(ox,oy);
      double d=length+Math.min(Math.max(qx,qy),0)-radius;
      double nx,ny;
      if(length>.0001){nx=Math.copySign(ox/length,dx);ny=Math.copySign(oy/length,dy);}
      else if(qx>qy){nx=Math.copySign(1,dx);ny=0;}
      else{nx=0;ny=Math.copySign(1,dy);}
      if(Math.abs(bend)>.0001){
        double nearX=px-bumpX,nearY=py-bumpY,farX=px-(width-bumpX),farY=py-(height-bumpY);
        double near=Math.exp(-(nearX*nearX+nearY*nearY)/sigma2);
        double far=Math.exp(-(farX*farX+farY*farY)/sigma2);
        d-=bend*density*(3.6*near-.7*far);
        nx-=bend*density*(-7.2*nearX*near+1.4*farX*far)/sigma2;
        ny-=bend*density*(-7.2*nearY*near+1.4*farY*far)/sigma2;
        double normalLength=Math.hypot(nx,ny);nx/=normalLength;ny/=normalLength;
      }
      double cover=1-smooth(-aa,aa,d);
      // First-order shadow offset is sufficient for the static cached fallback.
      double shadowD=d-ny*density;
      double ambient=0;
      if(!dark){
        double ambientQy=Math.abs(dy-3*density)-by+radius;
        double ambientD=Math.hypot(ox,Math.max(ambientQy,0))+Math.min(Math.max(qx,ambientQy),0)-radius;
        ambient=Math.exp(-square(Math.max(ambientD,0)/(8*density)))*.060;
      }
      double shadow=(ambient+Math.exp(-Math.max(shadowD,0)/(shadowFalloff*density))*shadowStrength)*(1-cover);
      if(cover<.001){colors[y*w+x]=byteValue(shadow)<<24;continue;}
      double edge=clamp(1+d/bevel,0,1),slope=Math.pow(edge,1.45)*.96;
      double fx=clamp(dx/Math.max(bx,1),-1,1),fy=clamp(dy/Math.max(by,1),-1,1);
      double normalX=nx*slope+fx*.035*(1-edge),normalY=ny*slope+fy*.035*(1-edge);
      double nz=Math.sqrt(Math.max(1-normalX*normalX-normalY*normalY,.001));
      double fresnel=.03+.97*Math.pow(1-nz,5);
      double dot=nx*lx+ny*ly,key=Math.pow(Math.max(dot,0),5),back=Math.pow(Math.max(-dot,0),5)*.58;
      double side=Math.pow(Math.abs(nx*-ly+ny*lx),2.4),sideMix=side*.55;
      double lit=clamp(key+back*.8,0,1);
      double er=mix(mix(.99,dark?.63:.88,sideMix),1,lit),eg=mix(mix(.995,dark?.70:.91,sideMix),1,lit),eb=mix(mix(1,dark?.80:.95,sideMix),1,lit);
      double reflection=clamp(fresnel*.72+Math.pow(edge,5)*(.015+side*.045),0,.32);
      double a=reflection+(1-reflection)*veil;
      double r=reflection*er+(1-reflection)*veil*tr;
      double g=reflection*eg+(1-reflection)*veil*tg;
      double b=reflection*eb+(1-reflection)*veil*tb;
      double rim=Math.exp(-square((d+.75*density)/((dark?.65:.85)*density)));
      double soft=Math.exp(-Math.max(-d,0)/(1.8*density))*Math.pow(edge,.6);
      double caustic=Math.exp(-square((d+2.2*density)/(.85*density)));
      double shine=clamp(rim*((dark?0:.50)+key*(dark?.68:.30)+back*(dark?.40:.32))
        +soft*((dark?0:.025)+key*.07+back*.04)+caustic*back*.07,0,.86);
      double broad=Math.exp(-square((fx*.55+fy*.8-lx*.4)*1.6));
      double touchRadius=Math.max(14*density,Math.min(by*1.35,34*density))*(.72+pressure*.28);
      double touchDx=(px-touchX)/touchRadius,touchDy=(py-touchY)/touchRadius;
      double contact=Math.exp(-(touchDx*touchDx+touchDy*touchDy));
      double touchRim=contact*Math.exp(-square((d+1.1*density)/(1.25*density)));
      double crestRadius=Math.max(10*density,Math.min(by*.70,22*density));
      double crestDx=(px-bumpX)/crestRadius,crestDy=(py-bumpY)/crestRadius;
      double crestContact=Math.exp(-(crestDx*crestDx+crestDy*crestDy));
      double crest=crestContact*Math.exp(-square((d+.8*density)/(.9*density)));
      shine=Math.min(.90,shine+broad*(dark?.004:.024)+pressure*(contact*.085+touchRim*.42+crest*.42));
      r=shine+(1-shine)*r;g=shine+(1-shine)*g;b=shine+(1-shine)*b;
      a=shine+(1-shine)*a;
      double cool=pressure*crestContact*Math.exp(-square((d+2.7*density)/(1.9*density)))*(dark?.12:.14);
      r=cool*(dark?.42:.50)+(1-cool)*r;g=cool*(dark?.68:.74)+(1-cool)*g;b=cool+(1-cool)*b;
      a=cool+(1-cool)*a;
      double surfaceAlpha=a*cover,alpha=surfaceAlpha+shadow*(1-surfaceAlpha);
      // setPixels accepts straight ARGB; the shader equivalent uses premultiplied P.
      colors[y*w+x]=alpha<.00001?0:(byteValue(alpha)<<24)
        |(byteValue(r*cover/alpha)<<16)|(byteValue(g*cover/alpha)<<8)|byteValue(b*cover/alpha);
    }
    Bitmap bitmap=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);
    bitmap.setDensity(Bitmap.DENSITY_NONE);bitmap.setPixels(colors,0,w,0,0,w,h);
    return bitmap;
  }
  private static int byteValue(double x){return (int)Math.round(clamp(x,0,1)*255);}
  private static double mix(double a,double b,double t){return a+(b-a)*t;}
  private static double clamp(double x,double a,double b){return Math.max(a,Math.min(b,x));}
  private static double square(double x){return x*x;}
  private static double smooth(double a,double b,double x){double t=clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);}
}
