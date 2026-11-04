#!/usr/bin/env python3
"""Full current event Store/Provider with real JVM IO and explicit Android adapters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
INPUTS = {
    'IntegrationEventStore.java': ROOT / 'tests/gecko/IntegrationEventStore.java',
    'IntegrationEvidenceProvider.java': ROOT / 'tests/gecko/IntegrationEvidenceProvider.java',
    'J.java': ROOT / 'app/src/main/java/local/pocketchat/J.java',
}
# Exact reviewed complete current classes, never historical replacement inputs.
PINS = {
    'IntegrationEventStore.java': 'ed7f0ed5e9784408cf557efd95145622061036012e2a1dcea257d55b4441d56a',
    'IntegrationEvidenceProvider.java': 'dfe2ba5371aa09bba59118afd2bf76a89ee3933d8a1709d81b895f41d6c68614',
    'J.java': '772bcc91b130ace1f33b529c2d828771ff9f12ba44805685a703df14f7d68493',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def member(source, needle):
    start = source.index(needle)
    opened = source.index('{', start)
    depth = 0
    quote = None
    escaped = line = block = False
    index = opened
    while index < len(source):
        char, pair = source[index], source[index:index + 2]
        if line:
            if char == '\n':
                line = False
        elif block:
            if pair == '*/':
                block = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif pair == '//':
            line = True
            index += 1
        elif pair == '/*':
            block = True
            index += 1
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
        index += 1
    raise ValueError('Incomplete member: ' + needle)


STUBS = {
    'android/content/Context.java': '''package android.content;
public final class Context {
  public String packageName="local.pocketchat.test";public final java.io.File directory;
  public Context(java.io.File value){directory=value;}
  public Context getApplicationContext(){return this;}
  public String getPackageName(){return packageName;}
  public java.io.File getFilesDir(){return directory;}
}''',
    'android/content/ContentProvider.java': '''package android.content;
public abstract class ContentProvider {
  public Context context;public Context getContext(){return context;}
  public abstract boolean onCreate();
  public abstract android.os.ParcelFileDescriptor openFile(android.net.Uri uri,String mode)throws java.io.FileNotFoundException;
  public abstract String getType(android.net.Uri uri);
  public abstract android.database.Cursor query(android.net.Uri uri,String[] projection,String selection,String[] args,String order);
  public abstract android.net.Uri insert(android.net.Uri uri,ContentValues values);
  public abstract int delete(android.net.Uri uri,String selection,String[] args);
  public abstract int update(android.net.Uri uri,ContentValues values,String selection,String[] args);
}''',
    'android/content/ContentValues.java': 'package android.content;public final class ContentValues {}',
    'android/database/Cursor.java': 'package android.database;public interface Cursor {}',
    'android/net/Uri.java': '''package android.net;
public final class Uri {
  final java.net.URI value;private Uri(String raw){value=java.net.URI.create(raw);}
  public static Uri parse(String raw){return new Uri(raw);}
  public String getPath(){return value.getPath();}
  public java.util.List<String> getPathSegments(){java.util.List<String> result=new java.util.ArrayList<>();for(String part:value.getRawPath().split("/"))if(!part.isEmpty())result.add(java.net.URLDecoder.decode(part,java.nio.charset.StandardCharsets.UTF_8));return result;}
}''',
    'android/os/SystemClock.java': '''package android.os;public final class SystemClock {public static long elapsedRealtime(){return java.util.concurrent.TimeUnit.NANOSECONDS.toMillis(System.nanoTime());}}''',
    'android/os/Binder.java': 'package android.os;public final class Binder {public static int uid=2000;public static int getCallingUid(){return uid;}}',
    'android/os/ParcelFileDescriptor.java': '''package android.os;
public final class ParcelFileDescriptor implements AutoCloseable {
  public static final int MODE_READ_ONLY=0x10000000;
  public static int pipes,opened;public final java.io.InputStream in;public final java.io.OutputStream out;
  private ParcelFileDescriptor(java.io.InputStream input,java.io.OutputStream output){in=input;out=output;}
  public static ParcelFileDescriptor open(java.io.File file,int mode)throws java.io.FileNotFoundException{if(mode!=MODE_READ_ONLY)throw new AssertionError("Not read only");opened++;return new ParcelFileDescriptor(new java.io.FileInputStream(file),null);}
  public static ParcelFileDescriptor[] createPipe()throws java.io.IOException{pipes++;java.io.PipedInputStream input=new java.io.PipedInputStream(1024);java.io.PipedOutputStream output=new java.io.PipedOutputStream(input);return new ParcelFileDescriptor[]{new ParcelFileDescriptor(input,null),new ParcelFileDescriptor(null,output)};}
  public byte[] bytes()throws java.io.IOException{return in.readAllBytes();}
  public void close()throws java.io.IOException{if(in!=null)in.close();if(out!=null)out.close();}
  public static final class AutoCloseOutputStream extends java.io.OutputStream {
    final ParcelFileDescriptor descriptor;public AutoCloseOutputStream(ParcelFileDescriptor value){descriptor=value;}
    public void write(int value)throws java.io.IOException{descriptor.out.write(value);}
    public void write(byte[] value,int offset,int length)throws java.io.IOException{descriptor.out.write(value,offset,length);}
    public void close()throws java.io.IOException{descriptor.close();}
  }
}''',
    'android/util/Log.java': '''package android.util;
public final class Log {
  public static final java.util.List<String> records=new java.util.concurrent.CopyOnWriteArrayList<>();
  public static int i(String tag,String value){AtomicFile.operations.add("log:"+value);records.add(value);return 0;}
  public static int e(String tag,String value){AtomicFile.operations.add("error:"+value);records.add(value);return 0;}
}''',
    'android/util/AtomicFile.java': '''package android.util;
/** Explicit host adapter: real temp bytes + rename; not Android durability evidence. */
public final class AtomicFile {
  public interface CommitHook {void run(java.io.File target)throws java.io.IOException;}
  public static final java.util.List<String> operations=new java.util.concurrent.CopyOnWriteArrayList<>();
  public static volatile CommitHook beforeCommit;
  public static volatile String failName,failPhase;
  public static volatile Thread lastWriter;
  public final java.io.File base,pending;
  public AtomicFile(java.io.File value){base=value;pending=new java.io.File(value.getPath()+".host-new");}
  static synchronized void fault(java.io.File target,String phase)throws java.io.IOException{
    if(failName!=null&&target.getName().contains(failName)&&phase.equals(failPhase)){failName=null;failPhase=null;throw new java.io.IOException("Controlled "+phase+" failure for "+target.getName());}
  }
  public java.io.FileOutputStream startWrite()throws java.io.IOException{
    lastWriter=Thread.currentThread();operations.add("start:"+base.getName());fault(base,"start");
    return new java.io.FileOutputStream(pending){
      public void write(byte[] bytes)throws java.io.IOException{fault(base,"write");super.write(bytes);}
      public void write(byte[] bytes,int offset,int count)throws java.io.IOException{fault(base,"write");super.write(bytes,offset,count);}
    };
  }
  public void finishWrite(java.io.FileOutputStream out)throws java.io.IOException{
    out.getFD().sync();out.close();fault(base,"finish");CommitHook hook=beforeCommit;if(hook!=null)hook.run(base);
    java.nio.file.Files.move(pending.toPath(),base.toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING,java.nio.file.StandardCopyOption.ATOMIC_MOVE);
    operations.add("finish:"+base.getName());
  }
  public void failWrite(java.io.FileOutputStream out){try{out.close();java.nio.file.Files.deleteIfExists(pending.toPath());}catch(java.io.IOException error){throw new IllegalStateException(error);}operations.add("fail:"+base.getName());}
}''',
    'local/pocketchat/Profiles.java': '''package local.pocketchat;final class Profiles {static final int MAX=8;static android.content.Context global(android.content.Context value){return value.getApplicationContext();}}''',
    'local/pocketchat/IntegrationBuildIdentity.java': '''package local.pocketchat;final class IntegrationBuildIdentity {static org.json.JSONObject read(android.content.Context ignored){return J.obj("sourceCommit","a".repeat(40));}}''',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    selected = {name: path.read_bytes() for name, path in INPUTS.items()}
    hashes = {name: digest(raw) for name, raw in selected.items()}
    assert PINS and hashes == PINS, 'Unreviewed complete current event journal sources'
    binary = lambda name: str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
    assert binary('java') and binary('javac'), 'JDK required'
    version = subprocess.check_output([binary('java'), '-version'], stderr=subprocess.STDOUT).decode()
    assert 'version "17.' in version, 'Use JDK 17 as CI does'
    jar = args.json_jar.resolve()
    assert jar.is_file(), 'Real JSON jar required'
    template = (HERE / 'JournalCases.java.in').read_bytes()
    runner_raw = Path(__file__).read_bytes()
    with tempfile.TemporaryDirectory(prefix='gecko-event-journal-host-') as directory:
        base = Path(directory)
        values = dict(STUBS)
        values.update({'local/pocketchat/' + name: raw.decode() for name, raw in selected.items()})
        values['local/pocketchat/JournalCases.java'] = template.decode()
        paths = []
        for name, text in values.items():
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            paths.append(str(path))
        classes = base / 'classes'
        subprocess.run([binary('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(classes), *paths], check=True)
        output = subprocess.check_output([binary('java'), '-cp', str(classes) + os.pathsep + str(jar), 'local.pocketchat.JournalCases'], timeout=90).decode()
    result = json.loads(output)
    assert all(path.read_bytes() == selected[name] for name, path in INPUTS.items()), 'Sources changed while tests ran'
    assert Path(__file__).read_bytes() == runner_raw and (HERE / 'JournalCases.java.in').read_bytes() == template, 'Host adapters changed while tests ran'
    methods = {}
    for name, needle in [('IntegrationEventStore.java', 'synchronized void emit('),
                         ('IntegrationEventStore.java', 'static File journalFile('),
                         ('IntegrationEvidenceProvider.java', '@Override public ParcelFileDescriptor openFile(')]:
        methods[name + ':' + needle] = digest(member(selected[name].decode(), needle).encode())
    result.update(schema=1, sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                  sourceHashes=hashes, sourceSha256=hashes, methodHashes=methods, adapterHash=digest(runner_raw),
                  caseTemplateHash=digest(template), jsonJarHash=digest(jar.read_bytes()), javaVersion=version.splitlines()[0],
                  actualAndroidExecution=False, sourceUnchangedDuringChecks=True,
                  boundary='Complete actual Store and Provider; real JVM worker/files; explicit Android AtomicFile/FD/Binder/Context adapters, no Android durability or device acceptance claim')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
