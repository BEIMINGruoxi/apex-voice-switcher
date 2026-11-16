#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键发布：升级版本号 → 同步各处 → 提交 → 打 tag → 推送。

tag 推送后，GitHub Actions 会自动构建 Windows exe 并发布 Release。

用法（在仓库根目录执行）：

    python scripts/release.py patch -m "修复备份页勾选框错位"
    python scripts/release.py minor -m "新增批量恢复功能"
    python scripts/release.py major -m "配置文件格式不兼容变更"

版本规则（语义化版本）：
    patch  1.12.0 → 1.12.1   缺陷修复、文案调整
    minor  1.12.0 → 1.13.0   新增功能、向后兼容
    major  1.12.0 → 2.0.0    不兼容变更

脚本同步以下位置，避免版本号不一致：
    1. apex_voice_switcher.py  → APP_VERSION
    2. version_info.txt        → filevers / prodvers / FileVersion / ProductVersion
    3. README.md               → v1.x.y 形式的版本号
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "apex_voice_switcher.py"
VERSION_INFO = ROOT / "version_info.txt"
README = ROOT / "README.md"


def git(*args, check=True):
    """执行 git 命令。"""
    return subprocess.run(["git", *args], cwd=ROOT, check=check,
                          capture_output=True, text=True)


def read_version():
    text = SRC.read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION = "(\d+)\.(\d+)\.(\d+)"', text)
    if not match:
        sys.exit("错误：在 apex_voice_switcher.py 中未找到 APP_VERSION")
    return tuple(int(part) for part in match.groups())


def bump(version, kind):
    major, minor, patch = version
    if kind == "major":
        return major + 1, 0, 0
    if kind == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def write_version(source_text, old, new):
    new_str = ".".join(map(str, new))
    SRC.write_text(
        source_text.replace(f'APP_VERSION = "{old}"', f'APP_VERSION = "{new_str}"'),
        encoding="utf-8")

    vi = VERSION_INFO.read_text(encoding="utf-8")
    a, b, c, d = (*new, 0)
    vi = re.sub(r"filevers=\(\d+, \d+, \d+, \d+\)",
                f"filevers=({a}, {b}, {c}, {d})", vi)
    vi = re.sub(r"prodvers=\(\d+, \d+, \d+, \d+\)",
                f"prodvers=({a}, {b}, {c}, {d})", vi)
    vi = re.sub(r"StringStruct\('FileVersion', '[^']*'\)",
                f"StringStruct('FileVersion', '{new_str}.0')", vi)
    vi = re.sub(r"StringStruct\('ProductVersion', '[^']*'\)",
                f"StringStruct('ProductVersion', '{new_str}.0')", vi)
    VERSION_INFO.write_text(vi, encoding="utf-8")

    README.write_text(
        README.read_text(encoding="utf-8").replace(f"v{old}", f"v{new_str}"),
        encoding="utf-8")
    return new_str


def main():
    parser = argparse.ArgumentParser(description="升级版本号并发布")
    parser.add_argument("kind", choices=["patch", "minor", "major"])
    parser.add_argument("-m", "--message", default="", help="本次改动说明")
    args = parser.parse_args()

    old_tuple = read_version()
    old = ".".join(map(str, old_tuple))
    new_tuple = bump(old_tuple, args.kind)
    new_str = write_version(SRC.read_text(encoding="utf-8"), old, new_tuple)
    print(f"版本号：v{old} → v{new_str}")

    # 版本号变化后重新构建才生效；提交与打 tag
    note = args.message or "版本更新"
    git("add", "-A")
    git("commit", "-m", f"chore(release): v{new_str} — {note}", check=False)
    tag = f"v{new_str}"
    if git("rev-parse", "--verify", f"refs/tags/{tag}", check=False).returncode == 0:
        print(f"tag {tag} 已存在，跳过创建")
    else:
        git("tag", "-a", tag, "-m", f"{tag} {note}")
        print(f"已创建 tag：{tag}")

    git("push")
    git("push", "origin", tag)
    print("已推送。GitHub Actions 将自动构建 exe 并发布 Release。")


if __name__ == "__main__":
    main()
