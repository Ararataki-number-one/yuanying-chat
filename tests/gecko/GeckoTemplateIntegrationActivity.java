package local.pocketchat;

import java.io.IOException;
import java.util.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Separate 1.7 fixture: production adapter/controller acknowledgements and
 * real controlled page/frame/Workers/HTTP headers, never the 1.6 prototype verdict.
 * No real account, independent process isolation or RFP compatibility claim. */
public final class GeckoTemplateIntegrationActivity extends GeckoIdentityPrototypeIntegrationActivity {
  static final String[] TEMPLATES={BrowserIdentitySpec.MOBILE,BrowserIdentitySpec.DESKTOP,BrowserIdentitySpec.COMPATIBLE,BrowserIdentitySpec.COMPATIBLE_DESKTOP};
  final JSONArray appliedCases=new JSONArray();
  BrowserIdentitySpec selected;
  @Override String reportFile(){return "gecko-template-results.json";}
  @Override String reportTag(){return "PocketTemplateFixture";}
  @Override boolean caseDesktop(){return caseIndex==1||caseIndex==3;}
  @Override void prepareCase(int ticket,Runnable prepared){
    selected=BrowserIdentitySpec.preset(TEMPLATES[caseIndex]).withLocales(Arrays.asList(requestedLocales));
    final BrowserIdentitySpec specification=selected;
    owner.environmentIo.execute(()->{
      try{
        EnvironmentSpec desired=EnvironmentSpecRuntime.desireBrowser(owner.context,specification.json());
        // This fixture deliberately bypasses safe-idle/draft capture: the local
        // test document contains no user task. It does not certify those flows.
        if(!owner.prefs.edit().putInt("privacyLevel",specification.protectionLevel()).commit())throw new IOException("Synthetic privacy request persistence failed");
        ProfileCatalog.get(owner.context).browserDisplay(Profiles.slot(owner.context),specification.desktop());
        handler.post(()->{
          if(finished||ticket!=serial)return;
          try{
            check("Template "+caseIndex+" desired configuration retains requested locales",sameBrowser(desired.desired().browser(),specification.json()));
            owner.identity.cached=desired;owner.identityApplicationPending=false;owner.identity.queueUnavailable=false;
            view.configureIdentity(specification);view.configure(specification.desktop(),specification.protectionLevel());
            check("Template "+caseIndex+" SDK getter only acknowledges the request",view.getSettings().localesRequestAcknowledged&&Arrays.equals(requestedLocales,view.getSettings().requestedLocales)&&Arrays.equals(requestedLocales,view.runtime.getSettings().getLocales()));
            check("Template "+caseIndex+" SDK-normalized prediction is separate",Arrays.equals(view.getSettings().expectedSdkLocales,BrowserIdentitySpec.expectedSdkLocales(Arrays.asList(requestedLocales)).toArray(new String[0])));
            check("Template "+caseIndex+" applies production UA and phone-fit viewport",view.current.getSettings().getUserAgentMode()==(specification.desktop()?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE)&&view.current.getSettings().getViewportMode()==GeckoSessionSettings.VIEWPORT_MODE_MOBILE);
            check("Template "+caseIndex+" applies actual tracking-list policy",view.current.getSettings().getUseTrackingProtection()==(specification.protectionLevel()>0));
            prepared.run();
          }catch(Throwable failure){finish(failure);}
        });
      }catch(Throwable failure){handler.post(()->finish(failure));}
    });
  }
  @Override void completeCase(JSONArray sessions,Runnable next){
    final int ticket=serial,index=caseIndex;final BrowserIdentitySpec specification=selected;
    try{
      check("Template "+index+" receives the current native privacy acknowledgement",view.getSettings().policyAcknowledged&&view.getSettings().rfpAcknowledged&&!view.fingerprintingProtected&&view.protectionLevel==specification.protectionLevel());
      check("Template "+index+" accepted identity remains requested configuration",sameBrowser(view.getSettings().acceptedBrowserIdentity,specification.json()));
      owner.identity.acknowledge();
      owner.environmentIo.execute(()->{
        try{
          EnvironmentSpec applied=new EnvironmentSpecRepository(owner.context).load();
          handler.post(()->{
            if(finished||ticket!=serial)return;
            try{
              check("Template "+index+" actual production acknowledgement binds desired revision",applied.applied()!=null&&applied.appliedRevision==applied.desiredRevision&&sameBrowser(applied.applied().browser(),specification.json())&&GeckoWebView.VERSION.equals(applied.engineVersion));
              JSONObject actual=sessions.getJSONObject(0).getJSONObject("observed");
              JSONObject sample=J.obj("parent",actual.getJSONObject("parent"),"frame",actual.getJSONObject("frame"),"worker",actual.getJSONObject("worker"),"provenance","page-main-world","mainWorld",J.obj("observed",true));
              JSONObject report=AuditReport.build(sample,new JSONObject(),owner.audit.expected(),false,true);
              for(String key:new String[]{"ua","language","frame","worker","zone"})check("Template "+index+" actual observation report covers "+key,AuditReport.VERIFIED.equals(row(report,key).optString("state")));
              reportPut(report,"identityAppliedRevision",applied.appliedRevision);reportPut(report,"policy",owner.audit.policyStamp());reportPut(report,"route",owner.audit.routeStamp());
              reportPut(report,"controlledRequestHeaders",sessions.getJSONObject(0).getJSONArray("requestHeaders"));
              reportPut(report,"scope","Controlled actual Gecko document/same-origin frame/Dedicated Worker JS fields; local server HTTP header roles remain separate. Worker fetch headers use the independent SDK mobile build default and do not certify uniform desktop HTTP UA. No ChatGPT, cross-origin or real network acceptance.");
              owner.identity.observe(report);
              owner.environmentIo.execute(()->{
                try{
                  EnvironmentSpec observed=new EnvironmentSpecRepository(owner.context).load();
                  handler.post(()->{
                    if(finished||ticket!=serial)return;
                    try{
                      check("Template "+index+" production controller records the observed revision",observed.observedRevision==applied.appliedRevision&&observed.observations().optLong("identityAppliedRevision")==applied.appliedRevision);
                      JSONObject nativePolicy=J.obj("requested",specification.json(),"accepted",view.getSettings().acceptedBrowserIdentity,"requestedLocales",new JSONArray(Arrays.asList(view.getSettings().requestedLocales)),"expectedSdkLocales",new JSONArray(Arrays.asList(view.getSettings().expectedSdkLocales)),"getterScope","requested-descriptor-only","rfpAcknowledged",view.getSettings().rfpAcknowledged,"fingerprintingProtected",view.fingerprintingProtected,"trackingProtection",view.current.getSettings().getUseTrackingProtection());
                      appliedCases.put(J.obj("index",index,"templateId",specification.templateId,"privacy",specification.privacy,"identity",observed.identity.json(),"nativePolicy",nativePolicy,"desiredRevision",observed.desiredRevision,"appliedRevision",observed.appliedRevision,"observedRevision",observed.observedRevision,"report",report));next.run();
                    }catch(Throwable failure){finish(failure);}
                  });
                }catch(Throwable failure){handler.post(()->finish(failure));}
              });
            }catch(Throwable failure){finish(failure);}
          });
        }catch(Throwable failure){handler.post(()->finish(failure));}
      });
    }catch(Throwable failure){finish(failure);}
  }
  static boolean sameBrowser(JSONObject a,JSONObject b){EnvironmentSpec.NetworkBinding route=new EnvironmentSpec.NetworkBinding("external","","","","","","");return new EnvironmentSpec.Configuration(a,route).equals(new EnvironmentSpec.Configuration(b,route));}
  static JSONObject row(JSONObject report,String key)throws JSONException{JSONArray rows=report.getJSONArray("rows");for(int i=0;i<rows.length();i++){JSONObject value=rows.getJSONObject(i);if(key.equals(value.optString("key")))return value;}throw new JSONException("Missing observation row "+key);}
  @Override void configureReport(JSONObject report){
    reportPut(report,"fixtureType","production-template-controlled-contexts-v1");reportPut(report,"diagnosticOnly",false);reportPut(report,"releaseAcceptance",false);
    reportPut(report,"controlledTemplateAcceptance","passed".equals(report.optString("status"))&&appliedCases.length()==4);
    reportPut(report,"fingerprintTemplateAcceptance",false);reportPut(report,"realAccountLogin",false);reportPut(report,"safeIdleApplicationAcceptance",false);
    reportPut(report,"fullDesktopUaConsistency",false);
    reportPut(report,"appliedCases",appliedCases);reportPut(report,"templateIds",new JSONArray(Arrays.asList(TEMPLATES)));
    reportPut(report,"independentTimezone","unsupported; observations use the real system timezone");
    reportPut(report,"uncovered",J.arr("cross-origin frame","Shared Worker","Service Worker","RFP compatibility","real account login","native IME","separate environment isolation","restart persistence","safe-idle application during real tasks","desktop Worker fetch UA consistency"));
    reportPut(report,"scope","Four standard/compatibility mobile/desktop display templates applied by production GeckoPolicyAdapter; controller applied/observed acknowledgement on actual local JS contexts and document/script/page-fetch headers. Worker fetch headers are checked against independent GeckoSession.getDefaultUserAgent build evidence; desktop mismatch is retained, not aligned or rewritten. Full desktop HTTP UA consistency, real ChatGPT, process isolation, restart and experimental RFP remain unaccepted.");
  }
}
