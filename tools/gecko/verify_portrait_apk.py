"""Check the binary Android manifests and actual resource values in a supplied APK."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
NS = "{http://schemas.android.com/apk/res/android}"
SDK_DIALOG = "com.google.android.gms.common.api.GoogleApiActivity"


def checked(condition, text):
    if not condition:
        raise ValueError(text)


def dump(aapt2,*args):
    return subprocess.check_output([str(aapt2), "dump", *map(str,args)]).decode("utf-8",errors="strict")


def activity_records(xml_tree):
    records = []
    attrs = None
    depth = -1
    for line in xml_tree.splitlines():
        text = line.lstrip()
        indent = len(line)-len(text)
        if text.startswith("E: "):
            if indent <= depth:
                attrs = None
            if re.match(r"E: activity(?:-alias)? \(",text):
                attrs = {"tag":text.split()[1]}
                records.append(attrs)
                depth = indent
        if attrs is not None and indent == depth+2:
            match = re.match(r"A: http://schemas.android.com/apk/res/android:(\w+)\(0x[0-9a-fA-F]+\)=(.*)",text)
            if match:
                attrs[match[1]]=match[2].split(" (Raw: ")[0].strip('"')
    return records


def values_for_id(resources, rid):
    lines = resources.splitlines()
    i = next(index for index,line in enumerate(lines)
             if re.search(r"\bresource "+re.escape(rid)+r"\s+(?:\S+:)?integer/transparent_activity_orientation\b",line))
    rows = {}
    for line in lines[i+1:]:
        if re.match(r"\s*(?:resource\s|type\s|Package )",line):
            break
        matching=re.match(r"\s*\(([^)]*)\)\s+(?:\(int[^)]*\)\s*)?(0x[0-9a-fA-F]+|\d+)\s*$",line)
        if matching:
            rows[matching[1]]=int(matching[2],0)
    return rows


def dex_declares(dex, descriptor):
    # A type reference alone doesn't prove that the APK supplies the SDK activity.
    if descriptor+b"\0" not in dex: return False
    checked(dex.startswith(b"dex\n") and len(dex)>=112,"Unsupported DEX header")
    string_count,string_table,type_count,type_table=struct.unpack_from("<4I",dex,0x38)
    count,table=struct.unpack_from("<2I",dex,0x60)
    for entry in range(count):
        type_id=struct.unpack_from("<I",dex,table+32*entry)[0]
        checked(type_id<type_count,"Invalid class definition")
        string_id=struct.unpack_from("<I",dex,type_table+4*type_id)[0]
        checked(string_id<string_count,"Invalid DEX type descriptor")
        pos=struct.unpack_from("<I",dex,string_table+4*string_id)[0]
        while dex[pos]&0x80:pos+=1
        if dex[pos+1:pos+len(descriptor)+2]==descriptor+b"\0":
            return True
    return False


def run(apk,role,aapt2):
    info = dump(aapt2,"badging",apk).splitlines()[0]
    version = int(re.search(r"versionCode='(\d+)'",info)[1])
    checked(version>=122,"This contract applies to the portrait-only release line.")
    package = re.search(r"name='([^']+)'",info)[1]
    test_package=role in ("integration","integration-chromium")
    feature=role in ("chromium","integration-chromium")
    checked(package == ("local.pocketchat.test" if test_package else "local.pocketchat"),package)
    module = "chromium" if feature else "app"
    declared = ET.parse(ROOT/module/"src/main/AndroidManifest.xml")
    expected = {a.get(NS+"name") for a in declared.findall("application/activity")
                if a.get(NS+"name","").startswith("local.pocketchat.")}
    records=activity_records(dump(aapt2,"xmltree","--file","AndroidManifest.xml",apk))
    names={r["name"] for r in records}
    checked(len(names)==len(records) and expected<=names,"Missing or duplicate activity in built APK")
    if not test_package or feature:
        checked(names==(expected if feature else expected|{SDK_DIALOG}),"Unexpected activities: "+str(names-expected))
    for record in records:
        if record["name"] in expected:
            checked(record["tag"]=="activity" and int(record.get("screenOrientation","-1"),0)==1,
                    "Not portrait: "+record["name"])
    dialog=None
    if module=="app":
        reference=next(r for r in records if r["name"]==SDK_DIALOG).get("screenOrientation","")
        checked(re.fullmatch(r"@0x[0-9a-fA-F]+",reference),"Invalid resolution activity resource: "+reference)
        dialog=values_for_id(dump(aapt2,"resources",apk),reference[1:])
        checked(dialog=={"":3,"v27":1},"Unexpected resolution overlay orientation qualifiers: "+str(dialog))
        with ZipFile(apk) as archive:
            checked(any(dex_declares(archive.read(name),b"Lcom/google/android/gms/common/api/GoogleApiActivity;")
                        for name in archive.namelist() if re.fullmatch(r"classes\d*\.dex",name)),
                    "Resolution activity is missing from the packaged DEX files.")
    with apk.open("rb") as f: digest=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(status="passed",role=role,package=package,versionCode=version,apk=apk.name,sha256=digest,
                portraitActivities=sorted(expected),transparentSdkDialogByQualifier=dialog)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk",type=Path)
    parser.add_argument("--role",choices=("base","chromium","integration","integration-chromium"),required=True)
    parser.add_argument("--aapt2",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    report=run(args.apk,args.role,args.aapt2)
    if args.output: args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"{len(report['portraitActivities'])} compiled activities request portrait in {report['apk']}.")
