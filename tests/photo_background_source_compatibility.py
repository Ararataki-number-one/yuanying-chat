"""Only the reviewed photo host route is removed for the old IP source proof.

This is a test-only, complete-source inverse. It neither supplies production
code nor replaces a current behavior test with historical bytes. The original
IP/timezone/protection guards must survive byte-for-byte outside the two exact
photo additions; every unknown edit is rejected before either replacement.
"""
import hashlib

PATH = 'app/src/main/assets/gecko/background.js'
PREVIOUS_SHA256 = '1416e78530713d63891ea4b3992ce084919326b662d16f49ec0c6f09e5f0a09c'
PREVIOUS_BYTES = 13688
CURRENT_SHA256 = 'b1fe412e092a6470c3d45a09e5e6181136f24a7b39e0b8bd1ecda8e38902ccce'
CURRENT_BYTES = 14143

PHOTO_ROUTE = b"""  if(['photoCanvasCapture','photoCanvasGrant','photoCanvasRelease'].includes(message.kind)&&Number.isInteger(message.id)&&message.id>0){
    let result;
    try{result=await globalThis.PocketNativePhotoBridge?.handle(message)??{schema:1,status:'failed'};}
    catch(_){result={schema:1,status:'failed'};}
    postHost(port,{kind:'photoCanvasReady',id:message.id,result:JSON.stringify(result)});return;
  }
"""
PHOTO_DISCONNECT = b"    globalThis.PocketNativePhotoBridge?.clear();\n"
ROUTE_BEFORE = b"""    postHost(port,{kind:'timezoneReady',id:message.id,result:JSON.stringify(result)});return;
  }
"""
ROUTE_AFTER = b"  if(message.kind==='prepare'){\n"
DISCONNECT_BEFORE = b"    timezoneIp?.close();timezoneIp=null;\n"
DISCONNECT_AFTER = b"    globalThis.PocketGeckoRequestHeaders?.clear(port);\n"
DELTAS = (
    (ROUTE_BEFORE + PHOTO_ROUTE + ROUTE_AFTER, ROUTE_BEFORE + ROUTE_AFTER),
    (DISCONNECT_BEFORE + PHOTO_DISCONNECT + DISCONNECT_AFTER,
     DISCONNECT_BEFORE + DISCONNECT_AFTER),
)


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative != PATH:
        raise ValueError('Photo source inverse requires complete bytes of the one owned path')
    identity = (len(raw), hashlib.sha256(raw).hexdigest())
    if identity == (PREVIOUS_BYTES, PREVIOUS_SHA256):
        return raw
    if identity != (CURRENT_BYTES, CURRENT_SHA256):
        raise ValueError('Photo source inverse rejects unknown complete source bytes')
    for current, previous in DELTAS:
        if raw.count(current) != 1:
            raise ValueError('Photo source inverse requires each exact addition in its original context')
        raw = raw.replace(current, previous, 1)
    if (len(raw), hashlib.sha256(raw).hexdigest()) != (PREVIOUS_BYTES, PREVIOUS_SHA256):
        raise ValueError('Photo source inverse did not preserve the complete original guard file')
    return raw
