# -*- coding: utf-8 -*-
"""语法自检：抽出 index.html 里最大的一段内联 JS，交给 node --check"""
import io
import os
import re
import subprocess
import tempfile

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
SRC = os.path.join(BASE, "index.html")

with io.open(SRC, "r", encoding="utf-8") as f:
    html = f.read()

blocks = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html)
blocks = [b for b in blocks if b.strip()]
if not blocks:
    print("没有找到内联脚本")
    raise SystemExit(1)

# 主逻辑就是最长的一段
main = max(blocks, key=len)
lines = main.count("\n") + 1
print("inline blocks: %d, main lines: %d (%d chars)" % (len(blocks), lines, len(main)))

fd, path = tempfile.mkstemp(suffix=".js", dir=BASE)
os.close(fd)
with io.open(path, "w", encoding="utf-8") as f:
    f.write(main)

try:
    r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    if r.returncode == 0:
        print("syntax OK")
    else:
        print("syntax FAILED")
        print((r.stdout or "")[-3000:])
        print((r.stderr or "")[-3000:])
        raise SystemExit(1)
finally:
    try:
        os.remove(path)
    except OSError:
        pass
