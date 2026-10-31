# -*- coding: utf-8 -*-
"""第 139 条补充：背诵模式单条朗读也走整条播放层（一次 utter，读完自动复位）"""
import os, sys
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")

MOCK = r"""(function(){
  if (!window.speechSynthesis) return;
  var s = window.speechSynthesis;
  window.__spoken=[]; window.__pending=null; window.__spk=false;
  Object.defineProperty(s,'speaking',{configurable:true,get:function(){return window.__spk;}});
  Object.defineProperty(s,'pending',{configurable:true,get:function(){return false;}});
  s.getVoices=function(){return [{name:'Microsoft Huihui - Chinese',lang:'zh-CN',localService:true}];};
  s.resume=function(){}; s.pause=function(){};
  s.cancel=function(){ window.__pending=null; window.__spk=false; };
  s.speak=function(u){ window.__spoken.push(String(u.text)); window.__pending=u; window.__spk=true;
    try{if(u.onstart)u.onstart({});}catch(e){} };
  window.__finish=function(){ var u=window.__pending; window.__pending=null; window.__spk=false; if(u&&u.onend)u.onend({}); };
})();"""

R = {"pass": 0, "fail": 0, "msg": []}


def check(ok, label, extra=None):
    if ok:
        R["pass"] += 1
    else:
        R["fail"] += 1
        R["msg"].append("FAIL " + label + ("  << " + str(extra)[:200] if extra is not None else ""))
        print("  FAIL", label, str(extra)[:200] if extra is not None else "")


with sync_playwright() as pw:
    b = pw.chromium.launch()
    for label, vw, ua in [("桌面", {"width": 1440, "height": 900}, None),
                          ("手机", {"width": 390, "height": 844},
                           "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1")]:
        ctx = b.new_context(viewport=vw, user_agent=ua)
        ctx.add_init_script(MOCK)
        p = ctx.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto(URL, timeout=90000)
        p.wait_for_timeout(1400)
        p.click("#reciteModeBtn")
        p.wait_for_timeout(800)

        btn = p.query_selector(".speak-btn[data-speak-id]")
        check(btn is not None, "[%s] 背诵模式有朗读按钮" % label)
        if not btn:
            ctx.close()
            continue
        sid = btn.get_attribute("data-speak-id")
        expect = p.evaluate("(id) => __T.speech.readText(id)", sid)
        btn.click()
        p.wait_for_timeout(350)

        spoken = p.evaluate("() => window.__spoken")
        check(len(spoken) == 1, "[%s] A1 整条只发声一次（%d 次）" % (label, len(spoken)), spoken and len(spoken[0]))
        check(spoken and spoken[0] == expect, "[%s] A2 发声内容 = 整条全文" % label,
              {"len": len(spoken[0]) if spoken else 0, "expect": len(expect)})
        check(p.evaluate("() => __T.speech.speakingId()") == sid, "[%s] A3 speakingId 已置位" % label)
        check(btn.inner_text().strip() == "停止", "[%s] A4 按钮变「停止」" % label, btn.inner_text())

        p.evaluate("() => window.__finish()")
        p.wait_for_timeout(400)
        check(p.evaluate("() => __T.speech.speakingId()") is None, "[%s] B1 读完自动复位" % label)
        check(p.evaluate("() => !!window.__pending") is False, "[%s] B2 无残留播放" % label)
        check(len(errs) == 0, "[%s] B3 零 JS 报错" % label, errs[:2])
        ctx.close()
    b.close()

print("\nTOTAL pass=%d fail=%d" % (R["pass"], R["fail"]))
for m in R["msg"]:
    print(m)
sys.exit(1 if R["fail"] else 0)
