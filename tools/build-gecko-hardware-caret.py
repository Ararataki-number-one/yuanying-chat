#!/usr/bin/env python3
"""Build a hash-pinned per-action synthesized-insertion candidate; Android acceptance is required."""
import argparse,hashlib,io,json,os,pathlib,struct,subprocess,urllib.request,zipfile
VERSION='157.0.20260924084938'
AAR_SHA='25de06a6204382c08e405adc36da7373098bdc230d6d768f17a6fe971f0dece0'
JAR_SHA='ef426e105fd4e65efdc45d41671d57c4a0c34d64bad15d5b70b82fccb30c7595'
CLASS_SHA='608461e22cae3ed19572aa43a0dc38d4926d48709bd456c91853935462f5fa54'
CODE_SHA='6cf3168f315761d3da0c836773526f05d82974dd7fc175820e2caa77a27fd28a'
TARGET='org/mozilla/geckoview/GeckoEditable.class'
HELPER='org/mozilla/geckoview/PocketSynthesizedInsertionScope.class'
ASM={'asm':'876eab6a83daecad5ca67eb9fcabb063c97b5aeb8cf1fca7a989ecde17522051','asm-tree':'14b7880cb7c85eed101e2710432fc3ffb83275532a6a894dc4c4095d49ad59f1'}
CONTEXT=bytes.fromhex('2bb400592bb4005ca000231c1da0001e2bb400591c2bb40070b900c40100b600d560a000090236040236052ab40080150415052bb40070b900c40100b900c70400a7000d')
def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def method_code(data):
 require(data[:4]==b'\xca\xfe\xba\xbe','Not a Java class');p=8;n=struct.unpack_from('>H',data,p)[0];p+=2;pool=[None]*n;i=1
 while i<n:
  tag=data[p];p+=1
  if tag==1:size=struct.unpack_from('>H',data,p)[0];p+=2;pool[i]=data[p:p+size];p+=size
  elif tag in (3,4):p+=4
  elif tag in (5,6):p+=8;i+=1
  elif tag in (7,8,16,19,20):p+=2
  elif tag in (9,10,11,12,17,18):p+=4
  elif tag==15:p+=3
  else:raise ValueError('Unsupported constant tag')
  i+=1
 p+=6;interfaces=struct.unpack_from('>H',data,p)[0];p+=2+2*interfaces;found=[];names=0
 for kind in ('field','method'):
  count=struct.unpack_from('>H',data,p)[0];p+=2
  for _ in range(count):
   flags,name,desc,attrs=struct.unpack_from('>HHHH',data,p);p+=8;target=kind=='method' and pool[name]==b'icPerformAction'
   if target:names+=1;require(flags==2 and pool[desc]==b'(Lorg/mozilla/geckoview/GeckoEditable$Action;)V','Predicate signature changed')
   for _ in range(attrs):
    attr,size=struct.unpack_from('>HI',data,p);p+=6
    if target and pool[attr]==b'Code':length=struct.unpack_from('>I',data,p+4)[0];found.append(data[p+8:p+8+length])
    p+=size
 require(names==1 and len(found)==1,'Predicate method not unique');return found[0]
def layout(data):
 end=data.rfind(b'PK\x05\x06');require(end>=0,'Missing ZIP EOCD');eocd=data[end:];disk,central_disk,n_disk,n,size,start,comment=struct.unpack_from('<HHHHIIH',eocd,4)
 require(disk==central_disk==0 and n_disk==n and n<65535 and start+size==end and len(eocd)==22+comment,'Unsupported ZIP layout')
 records=[];p=start
 for _ in range(n):
  require(data[p:p+4]==b'PK\x01\x02','Bad central record');names,extra,comments=struct.unpack_from('<HHH',data,p+28);length=46+names+extra+comments;flags=struct.unpack_from('<H',data,p+8)[0];name=data[p+46:p+46+names].decode('utf-8' if flags&0x800 else 'cp437');offset=struct.unpack_from('<I',data,p+42)[0];records.append({'name':name,'offset':offset,'central':data[p:p+length]});p+=length
 require(p==end and len({r['name']for r in records})==n,'Duplicate/extra ZIP entries');ordered=sorted(records,key=lambda r:r['offset'])
 for i,r in enumerate(ordered):r['end']=ordered[i+1]['offset']if i+1<len(ordered)else start
 return records,eocd
def replace(data,replacements):
 original,eocd=layout(data);buf=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(data))as archive:infos={i.filename:i for i in archive.infolist()}
 with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as archive:
  for name,raw in replacements.items():
   prior=infos.get(name);entry=zipfile.ZipInfo(name,prior.date_time if prior else(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.create_system=prior.create_system if prior else 3;entry.external_attr=prior.external_attr if prior else(0o100644<<16);archive.writestr(entry,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 changed=buf.getvalue();new={r['name']:r for r in layout(changed)[0]};output=io.BytesIO();records=[];original_names={r['name']for r in original}
 for row in sorted(original,key=lambda r:r['offset']):
  source,record=(changed,new[row['name']])if row['name']in new else(data,row);offset=output.tell();output.write(source[record['offset']:record['end']]);central=bytearray(record['central']);struct.pack_into('<I',central,42,offset);records.append(bytes(central))
 for name,row in new.items():
  if name in original_names:continue
  offset=output.tell();output.write(changed[row['offset']:row['end']]);central=bytearray(row['central']);struct.pack_into('<I',central,42,offset);records.append(bytes(central))
 start=output.tell()
 for record in records:output.write(record)
 end=bytearray(eocd);struct.pack_into('<HHII',end,8,len(records),len(records),output.tell()-start,start);output.write(end);result=output.getvalue();after={r['name']:r for r in layout(result)[0]}
 with zipfile.ZipFile(io.BytesIO(data))as a,zipfile.ZipFile(io.BytesIO(result))as b:
  for row in original:
   name=row['name'];other=after[name]
   if name in replacements:require(b.read(name)==replacements[name],'Changed payload mismatch');continue
   require(data[row['offset']:row['end']]==result[other['offset']:other['end']],'Unchanged raw record changed: '+name);require(a.read(name)==b.read(name),'Unchanged payload changed: '+name)
 return result,len(original)-len(set(original_names)&set(replacements))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for option in ['aar','android-jar','out','receipt']:p.add_argument('--'+option,type=pathlib.Path,required=True)
 p.add_argument('--javac',default='javac');p.add_argument('--java',default='java');p.add_argument('--gradle',type=pathlib.Path,help='Compatibility only; ASM is independently hash-pinned');a=p.parse_args()
 require(a.out.resolve()!=a.aar.resolve(),'Do not overwrite the official SDK');raw=a.aar.read_bytes();require(sha(raw)==AAR_SHA,'Official AAR hash mismatch')
 with zipfile.ZipFile(io.BytesIO(raw))as archive:jar=archive.read('classes.jar')
 require(sha(jar)==JAR_SHA,'Official classes.jar hash mismatch')
 with zipfile.ZipFile(io.BytesIO(jar))as archive:editable=archive.read(TARGET);require(HELPER not in archive.namelist(),'SDK already modified')
 require(sha(editable)==CLASS_SHA,'Official editable class mismatch');code=method_code(editable);require(len(code)==442 and sha(code)==CODE_SHA and code[363:431]==CONTEXT and code[396]==0x60,'Original predicate instruction graph changed')
 work=a.out.parent/'hardware-caret-build';work.mkdir(parents=True,exist_ok=True);asm=[]
 for name,digest in ASM.items():
  artifact=work/(name+'-9.8.jar')
  if not artifact.exists():
   with urllib.request.urlopen('https://repo.maven.apache.org/maven2/org/ow2/asm/'+name+'/9.8/'+name+'-9.8.jar',timeout=60)as response:artifact.write_bytes(response.read())
  require(sha(artifact.read_bytes())==digest,'Pinned ASM hash mismatch: '+name);asm.append(str(artifact.resolve()))
 official=work/'official-classes.jar';official.write_bytes(jar);original=work/'GeckoEditable-original.class';original.write_bytes(editable);candidate=work/'GeckoEditable-candidate.class';classes=work/'classes';classes.mkdir(exist_ok=True)
 source=pathlib.Path(__file__).resolve().parent/'gecko/hardware_caret';cp=os.pathsep.join(asm+[str(official.resolve()),str(a.android_jar.resolve())])
 subprocess.run([a.javac,'--release','17','-cp',cp,'-d',str(classes),str(source/'TransformHardwareCaret.java')],check=True)
 subprocess.run([a.javac,'--release','8','-d',str(classes),str(source/'PocketSynthesizedInsertionScope.java')],check=True)
 recipe=json.loads(subprocess.check_output([a.java,'-cp',str(classes.resolve())+os.pathsep+cp,'TransformHardwareCaret',str(original),str(candidate)],text=True))
 patched_jar,unchanged_jar=replace(jar,{TARGET:candidate.read_bytes(),HELPER:(classes/HELPER).read_bytes()});sdk=work/'candidate-classes.jar';sdk.write_bytes(patched_jar)
 subprocess.run([a.javac,'--release','17','-cp',os.pathsep.join([str(sdk.resolve()),str(a.android_jar.resolve())]),'-d',str(classes),str(source/'VerifyHardwareCaretScope.java')],check=True)
 verification=json.loads(subprocess.check_output([a.java,'-Xverify:all','-cp',os.pathsep.join([str(classes.resolve()),str(sdk.resolve()),str(a.android_jar.resolve())]),'org.mozilla.geckoview.VerifyHardwareCaretScope'],text=True))
 require(verification['jvmBytecodeVerification'] and verification['scopeChecks']>=30 and verification['actualSdkGuardedEarlyReturns']==3 and not verification['actualAndroidExecution'],'Candidate verifier incomplete')
 modified,unchanged_aar=replace(raw,{'classes.jar':patched_jar});a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(modified)
 with zipfile.ZipFile(io.BytesIO(modified))as archive:require(archive.read('classes.jar')==patched_jar,'Final classes.jar mismatch')
 files=['TransformHardwareCaret.java','PocketSynthesizedInsertionScope.java','VerifyHardwareCaretScope.java'];receipt={'schema':1,'candidateOnly':True,'releaseAcceptance':False,'officialVersion':VERSION,'officialAarSha256':AAR_SHA,'officialJarSha256':JAR_SHA,'officialEditableSha256':CLASS_SHA,'candidateAarSha256':sha(modified),'candidateJarSha256':sha(patched_jar),'candidateEditableSha256':sha(candidate.read_bytes()),'helperSha256':sha((classes/HELPER).read_bytes()),'asmVersion':'9.8','asmSha256':ASM,'transform':recipe,'jvmAndScopeVerification':verification,'sourceSha256':{name:sha((source/name).read_bytes())for name in files},'builderSha256':sha(pathlib.Path(__file__).read_bytes()),'originalPredicate':{'method':'icPerformAction','descriptor':'(Lorg/mozilla/geckoview/GeckoEditable$Action;)V','codeSha256':CODE_SHA,'codeBytes':442,'opcodeOffset':396,'opcode':'iadd','neighborStart':363,'neighborEndExclusive':431,'neighborHex':CONTEXT.hex()},'unchangedRawJarEntries':unchanged_jar,'unchangedRawAarEntries':unchanged_aar,'allNativeAndResourceEntriesUnchanged':True,'onlyOriginalClassAndOneHelperChanged':True,'normalCandidateContainsObserver':False,'origin':'Only the original non-composition TYPE_REPLACE_TEXT branch. The original processKey, InputConnection, batch mode, handler and dispatch/ACK ordering are unchanged.','eligibility':'Fresh frame per action; count original non-modifier synthesized DOWN calls only after normal return. Exactly one DOWN and length1 may use operand-1 at the existing collapsed action/shadow predicate. No extra batch/origin restriction. Composition, styled, multicharacter, no-key and multiple-DOWN paths retain the original predicate; single-DOWN dead-key characters are not categorically excluded.','scopeCleanup':'Nested ThreadLocal frame entered only after original composition early exit; restored after original replacement call or via catch-all rethrow of the original throwable. Single-use offset; no new posts, sleep, pacing, resend, DOM/selection write or shared cross-thread eligibility.','actualAndroidExecution':False,'requiredActualAcceptance':'Actual primitive trace must show operand1 to-1 and the matching native(-1,-1) call on the unchanged real 11-character burst; the original observer-free strict burst and real caret/reversed selection, rejected edits, soft IME/Chinese composition and clipboard paste must independently pass. A candidate diagnostic pass is not release acceptance.'}
 a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'candidateOnly':True,'out':str(a.out),'receipt':str(a.receipt),'sha256':sha(modified),'scopeChecks':verification['scopeChecks']}))
if __name__=='__main__':main()
