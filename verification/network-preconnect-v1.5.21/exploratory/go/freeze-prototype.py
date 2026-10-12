import difflib,hashlib,json,tarfile
from pathlib import Path
root=Path('/workspace/yuanying-chat');work=root/'work/network-preconnect-native';source=work/'source';archive=root/'third-party/source/mihomo-v1.19.31.tar.gz'
production=['adapter/adapter.go','component/urltesttrace/trace.go','hub/route/proxies.go','adapter/outbound/socks5.go','adapter/outbound/socks5_preconnect.go','adapter/outboundgroup/selector.go','component/proxydialer/pocket_route.go','tunnel/tunnel.go','transport/socks5/socks5.go']
tests=['adapter/urltest_probe_test.go','adapter/outbound/socks5_preconnect_test.go','adapter/outboundgroup/selector_preconnect_test.go','component/proxydialer/pocket_route_test.go','transport/socks5/socks5_preconnect_test.go','tunnel/pocket_preconnect_test.go','tunnel/pocket_export_test.go']
sha=lambda b:hashlib.sha256(b).hexdigest();original={}
with tarfile.open(archive) as tf:
 for member in tf.getmembers():
  name=member.name.split('/',1)[-1]
  if member.isfile() and name in production+tests: original[name]=tf.extractfile(member).read()
parts=[];files={}
for name in sorted(production+tests):
 before=original.get(name,b'');after=(source/name).read_bytes()
 if before==after:raise ValueError('unexpected unchanged file '+name)
 diff=''.join(difflib.unified_diff(before.decode().splitlines(keepends=True),after.decode().splitlines(keepends=True),fromfile='a/'+name if name in original else '/dev/null',tofile='b/'+name))
 parts.append(diff);files[name]={'sha256':sha(after),'originalSha256':sha(before) if name in original else None,'bytes':len(after),'test':name in tests}
patch=''.join(parts).encode();out=work/'mihomo-v1.19.31-preconnect.patch';out.write_bytes(patch)
identity=sha(json.dumps(files,sort_keys=True,separators=(',',':')).encode())
receipt={'schema':1,'prototypeOnly':True,'productionNativeInstalled':False,'upstreamRevision':'ab405bad5beeeac8b003bb01f60f134f6df54471','upstreamArchiveSha256':sha(archive.read_bytes()),'originalProbePatchSha256':sha((root/'third-party/patches/mihomo-v1.19.31-probe.patch').read_bytes()),'combinedPatchPath':str(out.relative_to(root)),'combinedPatchSha256':sha(patch),'sourceIdentitySha256':identity,'productionFiles':production,'testFiles':tests,'files':files,'poolContract':{'readyMaximum':1,'preparingMaximum':1,'ttlMilliseconds':8000,'ttlStarts':'preparation-start-including-auth','networkPollMilliseconds':50,'missingBlockedEpoch':'ordinary-protected-chain-no-pool','unsupportedRoute':'ordinary-protected-chain-no-pool','routeKey':['implicit-fixed-adapter-instance','captured-parent-reference','captured-actual-flat-leaf-reference','selector-monotonic-revision','tunnel-config-monotonic-generation','private-network-epoch'],'traceBypass':'no-consumption-no-refill','outerRetry':'scoped-no-retry-only-eligible-frozen-route-errors','deadIdleRetry':'one-fresh-same-frozen-route-before-any-caller-payload','postReturn':'never-return-to-pool-or-payload-replay'}}
(work/'prototype-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'combinedPatchSha256':receipt['combinedPatchSha256'],'sourceIdentitySha256':identity,'files':len(files),'patchBytes':len(patch)}))
