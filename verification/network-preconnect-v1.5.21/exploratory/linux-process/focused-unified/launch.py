#!/usr/bin/env python3
import json,os,pathlib,sys
config=pathlib.Path(sys.argv[sys.argv.index('-f')+1]);value=json.loads(config.read_text());value['unified-delay']=True;config.write_text(json.dumps(value,indent=2)+'\n')
core=pathlib.Path(__file__).resolve().parents[2]/'mihomo-build/bin/mihomo-linux-amd64'
# Scope is only this ignored fixture configuration; then execute the exact frozen core.
os.execv(str(core),[str(core),*sys.argv[1:]])
