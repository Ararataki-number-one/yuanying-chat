#!/usr/bin/env python3
"""Build only a pinned diagnostic GeckoEditable observer; never a production SDK."""
import argparse,hashlib,io,json,os,pathlib,struct,subprocess,urllib.request,zipfile
VERSION='157.0.20260924084938'
AAR_SHA='25de06a6204382c08e405adc36da7373098bdc230d6d768f17a6fe971f0dece0'
JAR_SHA='ef426e105fd4e65efdc45d41671d57c4a0c34d64bad15d5b70b82fccb30c7595'
CLASS_SHA='608461e22cae3ed19572aa43a0dc38d4926d48709bd456c91853935462f5fa54'
TARGET='org/mozilla/geckoview/GeckoEditable.class'
HELPER='org/mozilla/geckoview/PocketGeckoEditableTrace.class'
ASM={'asm':'876eab6a83daecad5ca67eb9fcabb063c97b5aeb8cf1fca7a989ecde17522051','asm-tree':'14b7880cb7c85eed101e2710432fc3ffb83275532a6a894dc4c4095d49ad59f1'}
def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def layout(data):
 end=data.rfind(b'PK\x05\x06');require(end>=0,'Missing ZIP EOCD');eocd=data[end:]
 disk,central_disk,n_disk,n,size,start,comment=struct.unpack_from('<HHHHIIH',eocd,4)
 require(disk==central_disk==0 and n_disk==n and n<65535 and start+size==end and len(eocd)==22+comment,'Unsupported ZIP layout')
 records=[];cursor=start
 for _ in range(n):
  require(data[cursor:cursor+4]==b'PK\x01\x02','Bad central record');name_len,extra_len,comment_len=struct.unpack_from('<HHH',data,cursor+28);length=46+name_len+extra_len+comment_len
  flags=struct.unpack_from('<H',data,cursor+8)[0];name=data[cursor+46:cursor+46+name_len].decode('utf-8' if flags&0x800 else 'cp437');offset=struct.unpack_from('<I',data,cursor+42)[0]
  records.append({'name':name,'offset':offset,'central':data[cursor:cursor+length]});cursor+=length
 require(cursor==end and len({r['name'] for r in records})==n,'Duplicate/extra ZIP entries')
 ordered=sorted(records,key=lambda r:r['offset'])
 for i,r in enumerate(ordered):r['end']=ordered[i+1]['offset'] if i+1<len(ordered) else start
 return records,eocd

def replace(data,replacements):
 original,eocd=layout(data);buf=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(data)) as archive:original_info={row.filename:row for row in archive.infolist()}
 with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
  for name,raw in replacements.items():
   previous=original_info.get(name);entry=zipfile.ZipInfo(name,previous.date_time if previous else (1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.create_system=previous.create_system if previous else 3;entry.external_attr=previous.external_attr if previous else (0o100644<<16)
   archive.writestr(entry,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 changed=buf.getvalue();new,_=layout(changed);new={r['name']:r for r in new};output=io.BytesIO();records=[]
 for row in sorted(original,key=lambda r:r['offset']):
  src,replacement=(changed,new[row['name']]) if row['name'] in new else (data,row)
  offset=output.tell();output.write(src[replacement['offset']:replacement['end']]);central=bytearray(replacement['central']);struct.pack_into('<I',central,42,offset);records.append(bytes(central))
 for name,row in new.items():
  if name in {r['name'] for r in original}:continue
  offset=output.tell();output.write(changed[row['offset']:row['end']]);central=bytearray(row['central']);struct.pack_into('<I',central,42,offset);records.append(bytes(central))
 start=output.tell()
 for central in records:output.write(central)
 end=bytearray(eocd);struct.pack_into('<HHII',end,8,len(records),len(records),output.tell()-start,start);output.write(end);result=output.getvalue()
 before={r['name']:r for r in original};after={r['name']:r for r in layout(result)[0]}
 with zipfile.ZipFile(io.BytesIO(data)) as a,zipfile.ZipFile(io.BytesIO(result)) as b:
  for name,row in before.items():
   if name in replacements:require(b.read(name)==replacements[name],'Changed ZIP payload mismatch');continue
   other=after[name];require(data[row['offset']:row['end']]==result[other['offset']:other['end']],'Unchanged raw ZIP record changed: '+name);require(a.read(name)==b.read(name),'Unchanged payload changed: '+name)
 return result,len(before)-len(set(before)&set(replacements))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--aar',type=pathlib.Path,required=True);p.add_argument('--gradle',type=pathlib.Path,help='Accepted for the diagnostic workflow; ASM is downloaded and hash-pinned independently');p.add_argument('--android-jar',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--receipt',type=pathlib.Path,required=True);p.add_argument('--javac',default='javac');p.add_argument('--java',default='java');p.add_argument('--candidate-receipt',type=pathlib.Path);p.add_argument('--official-aar',type=pathlib.Path);a=p.parse_args()
 require(a.out.resolve()!=a.aar.resolve(),'Never overwrite the SDK input');raw=a.aar.read_bytes()
 work=a.out.parent/'sdk-trace-build';work.mkdir(parents=True,exist_ok=True)
 candidate=None;expected_aar,expected_jar,expected_class=AAR_SHA,JAR_SHA,CLASS_SHA
 if a.candidate_receipt:
  require(a.official_aar is not None,'Candidate trace requires the pinned official AAR to reconstruct the complete recipe')
  supplied=json.loads(a.candidate_receipt.read_text())
  rebuilt=work/'reconstructed-hardware-candidate.aar';rebuilt_receipt=work/'reconstructed-hardware-candidate-receipt.json'
  builder=pathlib.Path(__file__).resolve().parent/'build-gecko-hardware-caret.py'
  subprocess.run([__import__('sys').executable,str(builder),'--aar',str(a.official_aar),'--android-jar',str(a.android_jar),'--out',str(rebuilt),'--receipt',str(rebuilt_receipt),'--java',a.java,'--javac',a.javac],check=True)
  candidate=json.loads(rebuilt_receipt.read_text())
  for key,value in [('officialAarSha256',AAR_SHA),('officialJarSha256',JAR_SHA),('officialEditableSha256',CLASS_SHA)]:
   require(supplied.get(key)==candidate.get(key)==value,'Candidate official pin mismatch: '+key)
  for key in ['candidateAarSha256','candidateJarSha256','candidateEditableSha256','sourceSha256']:
   require(key in candidate and supplied.get(key)==candidate[key],'Candidate receipt does not match the reproducible checked-out recipe: '+key)
  require(raw==rebuilt.read_bytes(),'Candidate AAR differs from a complete reconstruction of the pinned recipe')
  expected_aar,expected_jar,expected_class=(candidate[key] for key in ['candidateAarSha256','candidateJarSha256','candidateEditableSha256'])
 else:require(a.official_aar is None,'--official-aar is only accepted together with --candidate-receipt')
 require(sha(raw)==expected_aar,'SDK AAR hash mismatch')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:jar=z.read('classes.jar')
 require(sha(jar)==expected_jar,'SDK classes.jar hash mismatch')
 with zipfile.ZipFile(io.BytesIO(jar)) as z:editable=z.read(TARGET);require(HELPER not in z.namelist(),'SDK already instrumented')
 require(sha(editable)==expected_class,'SDK GeckoEditable class mismatch')
 asm=[]
 for name,digest in ASM.items():
  path=work/(name+'-9.8.jar')
  if not path.exists():
   with urllib.request.urlopen('https://repo.maven.apache.org/maven2/org/ow2/asm/'+name+'/9.8/'+name+'-9.8.jar',timeout=60) as response:path.write_bytes(response.read())
  require(sha(path.read_bytes())==digest,'Pinned ASM hash mismatch: '+name);asm.append(str(path.resolve()))
 official=work/'official-classes.jar';official.write_bytes(jar);original=work/'GeckoEditable-original.class';original.write_bytes(editable);instrumented=work/'GeckoEditable-instrumented.class';classes=work/'classes';classes.mkdir(exist_ok=True)
 source=pathlib.Path(__file__).resolve().parent/'gecko/ime_trace';cp=os.pathsep.join(asm+[str(official.resolve()),str(a.android_jar.resolve())])
 subprocess.run([a.javac,'--release','17','-cp',cp,'-d',str(classes),str(source/'InstrumentEditable.java')],check=True)
 subprocess.run([a.javac,'--release','8','-d',str(classes),str(source/'PocketGeckoEditableTrace.java')],check=True)
 transform=json.loads(subprocess.check_output([a.java,'-cp',str(classes.resolve())+os.pathsep+cp,'InstrumentEditable',str(original),str(instrumented)],text=True))
 require(transform['candidateOffsetCallsites']==(1 if candidate else 0),'Expected exactly one actual candidate offset observer, or zero for the official SDK')
 modified,unchanged_jar=replace(jar,{TARGET:instrumented.read_bytes(),HELPER:(classes/HELPER).read_bytes()})
 traced_jar=work/'trace-classes.jar';traced_jar.write_bytes(modified)
 subprocess.run([a.javac,'--release','17','-cp',str(traced_jar),'-d',str(classes),str(source/'VerifyTrace.java')],check=True)
 validation=json.loads(subprocess.check_output([a.java,'-Xverify:all','-cp',os.pathsep.join([str(classes.resolve()),str(traced_jar.resolve()),str(a.android_jar.resolve())]),'VerifyTrace'],text=True))
 require(validation['jvmBytecodeVerification'] and not validation['actualAndroidExecution'],'JVM verifier did not confirm diagnostic bytecode')
 patched,unchanged_aar=replace(raw,{'classes.jar':modified});a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(patched)
 with zipfile.ZipFile(io.BytesIO(patched)) as archive:require(archive.read('classes.jar')==modified,'Final classes.jar mismatch')
 receipt={'schema':1,'diagnosticOnly':True,'releaseAcceptance':False,'officialVersion':VERSION,'officialAarSha256':AAR_SHA,'officialJarSha256':JAR_SHA,'officialEditableSha256':CLASS_SHA,'instrumentedAarSha256':sha(patched),'instrumentedJarSha256':sha(modified),'instrumentedEditableSha256':sha(instrumented.read_bytes()),'helperSha256':sha((classes/HELPER).read_bytes()),'asmVersion':'9.8','asmSha256':ASM,'transform':transform,'jvmAndPrimitiveRingVerification':validation,'sourceSha256':{name:sha((source/name).read_bytes()) for name in ['InstrumentEditable.java','PocketGeckoEditableTrace.java','VerifyTrace.java']},'unchangedRawJarEntries':unchanged_jar,'unchangedRawAarEntries':unchanged_aar,'allNativeAndResourceEntriesUnchanged':True,'rowFields':['code','edge','nanoTime','threadId','argStart','argEnd','argFlags','argTextLength','currentStart','currentEnd','shadowStart','shadowEnd','actionQueueSize','sequence'],'codes':{'10':'onTextChange','11':'onSelectionChange','12':'notifyIME(type in argStart)','13':'icSyncShadowText','14':'outgoing onImeReplaceText','15':'outgoing onImeUpdateComposition','16':'candidate offset: argStart input length, argEnd returned operand, argTextLength input length','17':'sendCharKeyEvents: argStart/end original action range; shift8 successful actual nonmodifier DOWN count; argTextLength sequence length','18':'geckoActionReply','19':'icOfferAction','20':'processKey: argStart action, argEnd original source, shift8 original keyCode, argTextLength original flags (full signed int)','21':'Editable.sendKeyEvent: argStart action, argEnd original source, shift8 original keyCode, argTextLength original flags (full signed int)','22':'setBatchMode: argStart requested boolean; low state flags are before/after actual original call','23':'icPerformAction: original action range/type/length'},'flags':{'1':'mNeedSync','2':'mInBatchMode','4':'mActions.isEmpty','8':'mIgnoreSelectionChange','16':'mLastTextChangeReplacedSelection','32':'Original causedOnlyByComposition for codes10/11','shift8':'Original composition flags/action type for codes15/18/19/23; original keyCode for20/21; successful original synthesized nonmodifier DOWN count for17'},'edges':{'0':'entry/before actual original call','1':'normal return/after actual original call','2':'explicit original ATHROW'},'capacity':4096,'selectionReadPolicy':'Current and shadow only on original IC looper; current read holds existing AsyncText monitor. Other callbacks keep selection -1. No cross-thread shadow reads.','observerEffect':'Primitive observation, Atomic counters, queue size and IC current-text monitor can perturb timing. This is diagnostic-only evidence, never a fix or release acceptance.','originalCallsPreservedOnce':True,'productionSdkChanged':False,'actualAndroidExecution':False,'candidateRecipe':candidate,'inputAarSha256':expected_aar,'inputJarSha256':expected_jar,'inputEditableSha256':expected_class}
 a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'diagnosticOnly':True,'out':str(a.out),'receipt':str(a.receipt),'sha256':sha(patched)}))
if __name__=='__main__':main()
