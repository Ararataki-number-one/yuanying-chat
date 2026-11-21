#!/usr/bin/env python3
"""Run the production AI route with controlled Android/service/connection doubles. No sockets."""
import hashlib, importlib.util, json, os, pathlib, shutil, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat'
HERE = pathlib.Path(__file__).resolve().parent
BASE = ROOT / 'tests/native-download-route-host'
spec = importlib.util.spec_from_file_location('members', ROOT / 'tests/download-resume-host/run.py')
members = importlib.util.module_from_spec(spec); spec.loader.exec_module(members)
java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
jar = pathlib.Path(os.environ['PROFILE_JSON_JAR'])
guard = (SOURCE / 'BrowserNetworkGuard.java').read_text()
native = (SOURCE / 'NativeNetwork.java').read_text()
selected = {'GUARD_ROUTE':members.member(guard,'boolean routeProtected()'), 'GUARD_ALLOWED':members.member(guard,'boolean allowed()'), 'DOWNLOAD_ROUTE':members.member((SOURCE/'FileDownloads.java').read_text(),'Proxy route()'), 'RECEIPT':members.member(native,'static final class ExitRouteReceipt'), 'INVALIDATE':members.member(native,'void invalidateVerifiedRoute()'), 'ADMISSION':members.member(native,'NetworkHealthPolicy.Admission connectionAdmission()'), 'CURRENT':members.member(native,'boolean verifiedRouteCurrent()'), 'CLOSER':members.member((SOURCE/'AppUpdateTransfer.java').read_text(),'static void disconnectLater(')}
with tempfile.TemporaryDirectory(prefix='ai-diagnostic-route-host-') as directory:
    temp=pathlib.Path(directory); package=temp/'local/pocketchat'; package.mkdir(parents=True)
    for name in ('AiDiagnosticRoute.java','NativeDownloadRoute.java','NetworkPoolIdentity.java','NetworkHealthPolicy.java','EnvironmentSpec.java'):
        (package/name).write_bytes((SOURCE/name).read_bytes())
    template=(BASE/'NativeDownloadRouteHost.java.in').read_text()
    for marker,code in selected.items(): template=template.replace('/* '+marker+' */',code)
    extra='\n'.join(members.member(guard,name) for name in ('static boolean publicHttps(', 'static boolean localHost(', 'static boolean privateV4(', 'static boolean needsVpn('))
    template=template.replace('class BrowserNetworkGuard {','class BrowserNetworkGuard {\n'+extra)
    (package/'NativeDownloadRouteHost.java').write_text(template)
    (package/'AiDiagnosticRouteHost.java').write_bytes((HERE/'AiDiagnosticRouteHost.java').read_bytes())
    shutil.copytree(BASE/'android',temp/'android')
    uri=temp/'android/net/Uri.java'; uri.write_text(uri.read_text().replace('public String getHost()', 'public String getUserInfo(){return java.net.URI.create(value).getUserInfo();}public String getHost()'))
    net=temp/'android/net/Network.java'; net.write_text(net.read_text().replace('public int opens;', 'public int opens;public Proxy lastProxy;').replace('opens++;','opens++;lastProxy=proxy;'))
    (temp/'android/net/LinkProperties.java').write_text('package android.net; public final class LinkProperties {final String id;public LinkProperties(String id){this.id=id;}public boolean equals(Object other){return other instanceof LinkProperties&&id.equals(((LinkProperties)other).id);}public int hashCode(){return id.hashCode();}}')
    (temp/'android/net/ConnectivityManager.java').write_text('''package android.net;
public final class ConnectivityManager {
 public Network active;public NetworkCapabilities caps=new NetworkCapabilities();public LinkProperties links=new LinkProperties("initial");public NetworkCallback callback;public int unregisters;public boolean failRegister;
 public Network getActiveNetwork(){return active;}public NetworkCapabilities getNetworkCapabilities(Network value){return value!=null&&value.equals(active)?caps:null;}
 public LinkProperties getLinkProperties(Network value){return value!=null&&value.equals(active)?links:null;}
 public void registerDefaultNetworkCallback(NetworkCallback value){if(failRegister)throw new SecurityException("controlled registration denied");callback=value;}
 public void unregisterNetworkCallback(NetworkCallback value){if(callback==value){callback=null;unregisters++;}}
 public static class NetworkCallback {public void onAvailable(Network n){}public void onLost(Network n){}public void onCapabilitiesChanged(Network n,NetworkCapabilities c){}public void onLinkPropertiesChanged(Network n,LinkProperties p){}}
}''')
    inputs=list(package.glob('*.java'))+list((temp/'android').rglob('*.java'))
    subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(temp),*map(str,inputs)],check=True,timeout=40)
    run=subprocess.run([java,'-cp',str(temp)+os.pathsep+str(jar),'local.pocketchat.AiDiagnosticRouteHost'],check=True,capture_output=True,text=True,timeout=30)
    report=json.loads(run.stdout)
    report['sourceSha256']=hashlib.sha256((SOURCE/'AiDiagnosticRoute.java').read_bytes()).hexdigest()
    print(json.dumps(report,ensure_ascii=False))
# Static exclusions complement behavioral fixtures; they are not network privacy acceptance.
source=(SOURCE/'AiDiagnosticRoute.java').read_text()
for prohibited in ('getByName(', 'new InetSocketAddress("', 'requireDownloadNetwork(', 'setSSLSocketFactory(', 'setHostnameVerifier(', 'ProxySelector'):
    assert prohibited not in source,prohibited
