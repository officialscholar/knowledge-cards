# -*- coding: utf-8 -*-
"""生成 README 用截图（docs/images/）"""
import os
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")
OUT = os.path.join(BASE, "docs", "images")
os.makedirs(OUT, exist_ok=True)

SHOTS = [
    ("01-recite", "reciteModeBtn", 900),
    ("02-global", "globalModeBtn", 1200),
    ("03-read", "readModeBtn", 1200),
    ("04-node", "nodeModeBtn", 1600),
    ("05-outline", "outlineModeBtn", 1200),
    ("06-edit", "editModeBtn", 1200),
    ("07-game", "gameModeBtn", 1600),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, timeout=90000)
    pg.wait_for_timeout(1500)
    for name, btn, wait in SHOTS:
        pg.click("#" + btn)
        pg.wait_for_timeout(wait)
        pg.screenshot(path=os.path.join(OUT, name + ".png"))
        print("shot", name)
    # 手机端一张（阅读模式）
    ctx2 = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                         is_mobile=True, has_touch=True)
    p2 = ctx2.new_page()
    p2.goto(URL, timeout=90000)
    p2.wait_for_timeout(1500)
    p2.click("#readModeBtn")
    p2.wait_for_timeout(1200)
    p2.screenshot(path=os.path.join(OUT, "08-mobile-read.png"))
    print("shot 08-mobile-read")
    print("errors:", errs)
    b.close()
