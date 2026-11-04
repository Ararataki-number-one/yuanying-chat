#!/usr/bin/env python3
"""Compile and execute the production command-search/focus policies on the JVM."""
import argparse
import pathlib
import shutil
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--java-home',type=pathlib.Path)
p.add_argument('--output',type=pathlib.Path,default=pathlib.Path('work/ux-shell-host'))
a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
out=(root/a.output).resolve();out.mkdir(parents=True,exist_ok=True)
def tool(name):
    return str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
production=root/'app/src/main/java/local/pocketchat'
subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(out),str(production/'ActionSearchPolicy.java'),str(production/'FocusReadingPolicy.java'),str(production/'UiFrameScheduler.java'),str(pathlib.Path(__file__).with_name('UxShellPolicyTest.java')),str(pathlib.Path(__file__).with_name('FrameSchedulerTest.java'))],check=True)
subprocess.run([tool('java'),'-cp',str(out),'local.pocketchat.UxShellPolicyTest'],check=True)
subprocess.run([tool('java'),'-cp',str(out),'local.pocketchat.FrameSchedulerTest'],check=True)
