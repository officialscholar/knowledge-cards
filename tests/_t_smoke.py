# -*- coding: utf-8 -*-
"""冒烟：七个模式都能渲染、互切不炸（双端）。辅助脚本被清理后重建的最小守门砖。"""
import os
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")
results = []


def ck(cond, label, extra=""):
    results.append((bool(cond), label, str(extra)))


MODES = [("globalModeBtn", "全局"), ("readModeBtn", "阅读"), ("reciteModeBtn", "背诵"),
         ("nodeModeBtn", "节点"), ("outlineModeBtn", "目录"), ("editModeBtn", "录入"),
         ("gameModeBtn", "乐园")]
VIEWPORTS = [("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})]

with sync_playwright() as pw:
    b = pw.chromium.launch()
    for label, vp in VIEWPORTS:
        ctx = b.new_context(viewport=vp)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
        page.goto("file:///" + PAGE.replace("\\", "/"), timeout=60000)
        page.wait_for_timeout(1500)
        ck(page.evaluate("() => window.__KV__") == "2026-10-31g", "[%s] 版本号已更新" % label,
           page.evaluate("() => window.__KV__"))
        for btn, name in MODES:
            page.click("#" + btn)
            page.wait_for_timeout(900)
            ok = page.evaluate(
                "(m) => document.body.dataset.mode === m", btn.replace("ModeBtn", ""))
            ck(ok, "[%s] 切到「%s」模式正常" % (label, name), page.evaluate("() => document.body.dataset.mode"))
            # 每种模式下点一下页面中心，确认没有卡死脚本
            try:
                page.mouse.click(vp["width"] // 2, vp["height"] // 2)
            except Exception:
                pass
            page.wait_for_timeout(200)
        ck(not errs, "[%s] 全程无 JS 报错" % label, "; ".join(errs[:3])[:200])
        ctx.close()
    b.close()

ok = sum(1 for r in results if r[0])
for passed, lab, extra in results:
    print(("  ok  " if passed else "  FAIL") + " " + lab + (("   -> " + extra) if (extra and not passed) else ""))
print("\n通过 %d / %d" % (ok, len(results)))
if ok != len(results):
    raise SystemExit(1)
