# -*- coding: utf-8 -*-
"""第 140 条：朗读设置面板截图（桌面 / 手机）"""
from playwright.sync_api import sync_playwright

import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")

MOCK = """(function(){
  var s = window.speechSynthesis;
  if (!s) return;
  s.getVoices = function () { return [
    { name: 'Microsoft Huihui - Chinese (Simplified, PRC)', lang: 'zh-CN', localService: true },
    { name: 'Microsoft Kangkang - Chinese (Simplified, PRC)', lang: 'zh-CN', localService: true },
    { name: 'Google 普通话（中国大陆）', lang: 'zh-CN', localService: false }
  ]; };
  s.speak = function () {}; s.cancel = function () {}; s.resume = function () {}; s.pause = function () {};
})();"""

with sync_playwright() as p:
    b = p.chromium.launch()
    for label, vw in (("d", {"width": 1440, "height": 900}), ("m", {"width": 390, "height": 844})):
        ctx = b.new_context(viewport=vw)
        ctx.add_init_script(MOCK)
        pg = ctx.new_page()
        pg.goto(URL, timeout=90000)
        pg.wait_for_timeout(1200)
        pg.click("#readModeBtn")
        pg.wait_for_selector(".read-scroll")
        pg.wait_for_timeout(400)
        pg.evaluate("() => __T.speech.ttsSetCloud({ on: true, key: 'k' })")
        pg.click('[data-action="speak-set"]')
        pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(BASE, "tests", "_shots", "voice_%s.png" % label))
        print(label, pg.evaluate("() => __T.speech.previewState()")["opts"])
        ctx.close()
    b.close()
print("ok")
