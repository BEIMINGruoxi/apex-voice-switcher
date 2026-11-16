# -*- coding: utf-8 -*-
"""exe 防伪标记二进制级验证：三层（PE 版本资源 / PyInstaller 归档解压 / 全文件 zlib 流扫描）

用法：
    python _verify_mark.py [exe 路径]
    不带参数时，默认读取与本脚本同目录的 Apex语音切换器.exe
"""
import struct, zlib, re, sys
from pathlib import Path

EXE = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "Apex语音切换器.exe")
data = open(EXE, "rb").read()
print('exe size:', len(data))

MARKS = ['北冥若曦', 'BEIMINGruoxi', '蝶梦影', 'diemengying']
B64 = 'YXBleC12b2ljZS1zd2l0Y2hlcj'  # ANTI_FAKE_MARK_B64 的开头片段

print('\n== 第 0 层：exe 原始字节直搜（UTF-8/ASCII 明文，预期 MISSING——归档压缩所致）==')
for s in MARKS + [B64]:
    print(('FOUND  ' if s.encode('utf-8') in data else 'MISSING'), s)

print('\n== 第 1 层：PE 版本资源（UTF-16LE，未压缩 = 文件属性可见）==')
ok16 = 0
targets16 = MARKS + ['仅供个人使用，禁止商用', '© 2026 北冥若曦']
for s in targets16:
    found = s.encode('utf-16-le') in data
    ok16 += found
    print(('FOUND  ' if found else 'MISSING'), s)
print(f'-> {ok16}/{len(targets16)}')

print('\n== 第 2 层：PyInstaller 归档逐条目解压后搜索 ==')
MAGIC = b'MEI\x0c\x0b\x0a\x0b\x0e'
pos = data.rfind(MAGIC)
assert pos > 0, 'not a PyInstaller onefile exe'
pkg_len, toc_off, toc_len, pyver = struct.unpack_from('!IIII', data, pos + 8)
pylib = data[pos + 24:pos + 88].rstrip(b'\x00')
pkg_start = pos + 88 - pkg_len
print(f'cookie@{pos}  pkg_len={pkg_len}  toc_len={toc_len}  pylib={pylib.decode(errors="replace")}')
hits, n = [], 0
p, end = pkg_start + toc_off, pkg_start + toc_off + toc_len
while p + 18 <= end:
    (esz,) = struct.unpack_from('!I', data, p)
    if esz < 18 or p + esz > end:
        break
    off, csize, usize = struct.unpack_from('!III', data, p + 4)
    flag = data[p + 16]
    typ = data[p + 17:p + 18]
    name = data[p + 18:p + esz].rstrip(b'\x00').decode('utf-8', 'replace')
    raw = data[pkg_start + off: pkg_start + off + csize]
    if flag == 1:
        try:
            raw = zlib.decompress(raw)
        except Exception:
            raw = b''
    n += 1
    if typ in (b's', b'm', b'M'):
        found = [s for s in MARKS + [B64] if s.encode('utf-8') in raw]
        if found:
            hits.append((f'{name} [{typ.decode()} {usize}B]', found))
    p += esz
print(f'scanned {n} archive entries')
for name, found in hits:
    print('FOUND in', name, '->', ', '.join(found))
if not hits:
    print('(script/module entries: no marks)')

print('\n== 第 3 层：全文件 zlib 流暴力扫描（覆盖 PYZ 内部条目等）==')
total, scanned = set(), 0
mv = memoryview(data)
for m in re.finditer(b'\x78\x01|\x78\x9c|\x78\xda', data):
    d = zlib.decompressobj()
    try:
        out = d.decompress(mv[m.start():], 4 << 20)
    except Exception:
        continue
    scanned += 1
    for s in MARKS + [B64]:
        if s.encode('utf-8') in out:
            total.add(s)
print(f'zlib streams decompressed OK: {scanned}')
print('marks found across all streams:', ', '.join(sorted(total)) if total else '(none)')

print('\n== 结论 ==')
verdict = ok16 >= 4 and bool(hits or total)
print('VERDICT:', 'PASS - 防伪标记可从 exe 二进制溯源' if verdict else 'FAIL')
