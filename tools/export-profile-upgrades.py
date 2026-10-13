#!/usr/bin/env python3
"""Export reviewable sequential patches and changed source; no build or publication."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
BASE = "a6c60f38fa51c107706626bae6707d2bd317c803"
VERSIONS = [("1.6.0", "codex/v1.6-network-environments"),
            ("1.7.0", "codex/v1.7-templates-audit"),
            ("2.0.0", "codex/v2.0-maintenance-capabilities")]

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/profile-upgrades")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT.is_relative_to(output):
        parser.error("Output must not contain or replace the source repository")
    output.mkdir(parents=True, exist_ok=True)
    (output / "patches").mkdir(exist_ok=True)
    prior = BASE
    release_records = []
    for version, branch in VERSIONS:
        commit = git("rev-parse", branch).decode().strip()
        git("merge-base", "--is-ancestor", prior, commit)
        patch = git("format-patch", "--stdout", prior + ".." + commit)
        if not patch:
            raise ValueError("Missing implementation commits for " + version)
        name = "patches/" + version + ".patch"
        (output / name).write_bytes(patch)
        release_records.append({"version": version, "branch": branch, "commit": commit,
                                "tree": git("rev-parse", commit + "^{tree}").decode().strip(),
                                "parent": prior, "patch": name})
        prior = commit
    changed = git("diff", "--name-only", "--diff-filter=ACMRT", "-z", BASE, prior).decode().split("\0")
    for name in filter(None, changed):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or any(part in {"work", "private", "secrets", "dist"} for part in path.parts):
            raise ValueError("Unsafe source export path")
        destination = output / "source-delta" / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(git("show", prior + ":" + name))
    deleted = git("diff", "--name-only", "--diff-filter=D", BASE, prior).decode().splitlines()
    (output / "deleted-files.json").write_text(json.dumps(deleted, indent=2) + "\n")
    if args.evidence_dir:
        evidence = args.evidence_dir.resolve()
        for path in evidence.glob("*.json"):
            json.loads(path.read_text())
            destination = output / "verification" / path.name
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(path.read_bytes())
    readme = """PocketChat 1.6 → 1.7 → 2.0 候选源码交付

基于正式 v1.5.21-gecko，未合并主分支、未发布 APK。
在干净分支执行：
  git switch -c review/profile-upgrades v1.5.21-gecko
  git am /交付目录/patches/1.6.0.patch
  git am /交付目录/patches/1.7.0.patch
  git am /交付目录/patches/2.0.0.patch
有你自己的修改时先审查冲突，保留原签名和数据目录。

source-delta 是三个版本累计变更的源码和文档，补丁保留完整差异与提交。
逐版范围、剩余工作、运行方法见 source-delta/docs/IMPLEMENTATION-*.md
及 MERGE-AND-ACCEPTANCE.md。verification 是限定范围的主机检查，
不能代替完整 APK、官方 SDK、Android/ARM 真机或真实 Google 登录验收。

2.0 为官方 SDK 阶段：资源保护、能力清单和维护框架；独立原生时区及
Canvas/WebGL/音频/字体自定义仍待实现与真机验证，没有伪装成已完成。
"""
    (output / "README.txt").write_text(readme, encoding="utf-8")
    manifest = {"schema": 1, "baseline": BASE, "releases": release_records,
                "published": False, "actualAndroidExecution": False,
                "files": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(output.rglob("*")) if path.is_file() and path.suffix != ".zip" and path.name != "manifest.json"}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    archive = output / "PocketChat-1.6-1.7-2.0-review.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path != archive:
                bundle.write(path, "PocketChat-profile-upgrades/" + str(path.relative_to(output)))
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size,
                      "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "releases": release_records}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
