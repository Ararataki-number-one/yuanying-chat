#!/usr/bin/env python3
"""Execute the complete website-permission helper with explicit Android adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
STUBS={
 'android/Manifest.java':'package android;public final class Manifest {public static final class permission {public static final String CAMERA="android.permission.CAMERA",RECORD_AUDIO="android.permission.RECORD_AUDIO",ACCESS_COARSE_LOCATION="android.permission.ACCESS_COARSE_LOCATION";}}',
 'android/os/Bundle.java':'package android.os;public class Bundle {}',
 'android/content/pm/PackageManager.java':'package android.content.pm;public final class PackageManager {public static final int PERMISSION_GRANTED=0;}',
 'android/net/Uri.java':'package android.net;public final class Uri {private String value;public static Uri parse(String text){Uri uri=new Uri();uri.value=text;return uri;}public String toString(){return value;}}',
 'android/content/DialogInterface.java':'package android.content;public interface DialogInterface {interface OnClickListener {void onClick(DialogInterface dialog,int which);}interface OnCancelListener {void onCancel(DialogInterface dialog);}interface OnDismissListener {void onDismiss(DialogInterface dialog);}}',
 'android/app/Application.java':'''package android.app;import android.os.Bundle;import java.util.*;public class Application {public final List<ActivityLifecycleCallbacks> callbacks=new ArrayList<>();public void registerActivityLifecycleCallbacks(ActivityLifecycleCallbacks c){callbacks.add(c);}public void unregisterActivityLifecycleCallbacks(ActivityLifecycleCallbacks c){callbacks.remove(c);}public void pause(Activity a){for(ActivityLifecycleCallbacks c:new ArrayList<>(callbacks))c.onActivityPaused(a);}public void resume(Activity a){for(ActivityLifecycleCallbacks c:new ArrayList<>(callbacks))c.onActivityResumed(a);}public void stop(Activity a){for(ActivityLifecycleCallbacks c:new ArrayList<>(callbacks))c.onActivityStopped(a);}public interface ActivityLifecycleCallbacks {void onActivityCreated(Activity a,Bundle b);void onActivityStarted(Activity a);void onActivityResumed(Activity a);void onActivityPaused(Activity a);void onActivityStopped(Activity a);void onActivitySaveInstanceState(Activity a,Bundle b);void onActivityDestroyed(Activity a);}}''',
 'android/app/Activity.java':'''package android.app;import java.util.*;public class Activity {public final Application application=new Application();public final Set<String> granted=new HashSet<>();public boolean finishing,destroyed,focus=true,throwRequest;public int requests,lastCode;public String[] lastPermissions;public Application getApplication(){return application;}public boolean hasWindowFocus(){return focus;}public boolean isFinishing(){return finishing;}public boolean isDestroyed(){return destroyed;}public int checkSelfPermission(String permission){return granted.contains(permission)?0:-1;}public void requestPermissions(String[] names,int code){if(throwRequest)throw new SecurityException("controlled permission failure");requests++;lastCode=code;lastPermissions=names;}}''',
 'android/app/AlertDialog.java':'''package android.app;import android.content.DialogInterface;public class AlertDialog implements DialogInterface {public String title,message;public boolean showing;DialogInterface.OnClickListener yes,no;DialogInterface.OnCancelListener cancelled;DialogInterface.OnDismissListener dismissed;public void setOnCancelListener(DialogInterface.OnCancelListener listener){cancelled=listener;}public void setOnDismissListener(DialogInterface.OnDismissListener listener){dismissed=listener;}public void show(){showing=true;}public void dismiss(){if(!showing)return;showing=false;if(dismissed!=null)dismissed.onDismiss(this);}public void positive(){yes.onClick(this,1);dismiss();}public void negative(){no.onClick(this,0);dismiss();}public static class Builder {final AlertDialog dialog=new AlertDialog();public Builder(Activity activity){}public Builder setTitle(String text){dialog.title=text;return this;}public Builder setMessage(String text){dialog.message=text;return this;}public Builder setPositiveButton(String text,DialogInterface.OnClickListener action){dialog.yes=action;return this;}public Builder setNegativeButton(String text,DialogInterface.OnClickListener action){dialog.no=action;return this;}public AlertDialog create(){return dialog;}}}''',
 'android/webkit/WebView.java':'package android.webkit;public class WebView {public String url;public WebView(String url){this.url=url;}public String getUrl(){return url;}}',
 'android/webkit/PermissionRequest.java':'package android.webkit;import android.net.Uri;public abstract class PermissionRequest {public static final String RESOURCE_VIDEO_CAPTURE="android.webkit.resource.VIDEO_CAPTURE",RESOURCE_AUDIO_CAPTURE="android.webkit.resource.AUDIO_CAPTURE";public abstract Uri getOrigin();public abstract String[] getResources();public abstract void grant(String[] resources);public abstract void deny();}',
 'android/webkit/GeolocationPermissions.java':'package android.webkit;public final class GeolocationPermissions {public interface Callback {void invoke(String origin,boolean allow,boolean retain);}}',
}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-browser-permissions/results.json',help='JSON report file')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    source=ROOT/'app/src/main/java/local/pocketchat'
    production=[source/'BrowserPermissions.java',source/'BrowserAddressPolicy.java']
    inputs=[*production,HERE/'BrowserPermissionsHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs}
    with tempfile.TemporaryDirectory(prefix='browser-permissions-host-') as temporary:
        work=Path(temporary);stubs=[]
        for name,text in STUBS.items():
            target=work/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text+'\n');stubs.append(target)
        classes=work/'classes'
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),*[str(path) for path in [*production,HERE/'BrowserPermissionsHost.java',*stubs]]],text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        ran=subprocess.run([tool('java'),'-cp',str(classes),'local.pocketchat.BrowserPermissionsHost'],text=True,capture_output=True)
        if ran.returncode:raise RuntimeError(ran.stderr)
        report=json.loads(ran.stdout)
    unchanged=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report.update(status='passed' if unchanged else 'source-changed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,executionInputsUnchanged=unchanged,scope='Complete production BrowserPermissions and BrowserAddressPolicy with explicit Activity/Application lifecycle, site dialogs, Android runtime permission state/results, WebView URL identity and native permission/geolocation callback adapters. No actual Android permission prompt, camera, microphone, geolocation, Chromium or network execution.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],actualAndroidExecution=False,output=str(args.output)),ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
