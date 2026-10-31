# -*- coding: utf-8 -*-
"""【已归档】本脚本断言的是第 132~138 条的旧整页朗读实现（分句引擎 / 看门狗计数 / 继续朗读）。
   第 139 条已把播放原子改为「整条知识点」并重写推进逻辑，等价覆盖见 _t_p19.py（normal / noend / mute
   三模型）、_t_p19b.py（云端 audio 与失败回退）、_t_p19c.py（单条朗读）。此脚本仅作历史参考。"""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")

MOCK = r"""(function(){
  if (!window.speechSynthesis) return;
  var s = window.speechSynthesis;
  window.__spoken = []; window.__spk = false; window.__pend = false;
  window.__mode = 'normal';        // normal | slow | chrome
  window.__swallowed = 0; window.__lastCancel = 0; window.__count = 0;
  Object.defineProperty(s,'speaking',{configurable:true,get:function(){return window.__spk;}});
  Object.defineProperty(s,'pending',{configurable:true,get:function(){return window.__pend;}});
  s.getVoices=function(){return [{name:'Mock Online',lang:'zh-CN',localService:false},
                                 {name:'Mock Local',lang:'zh-CN',localService:true}];};
  s.resume=function(){}; s.pause=function(){};
  var t1=0,t2=0;
  function clear(){ clearTimeout(t1); clearTimeout(t2); }
  s.cancel=function(){ clear(); window.__spk=false; window.__pend=false; window.__lastCancel=Date.now(); };
  s.speak=function(u){
    window.__count++;
    if (window.__mode === 'chrome' && (Date.now() - window.__lastCancel) < 120) {
      window.__swallowed++;                       /* Chrome：cancel 后紧跟的 speak 被吞 */
      return;
    }
    window.__spoken.push(String(u.text));
    var start = function(){
      window.__pend = false; window.__spk = true;
      try { if (u.onstart) u.onstart({}); } catch(e){}
      t2 = setTimeout(function(){
        window.__spk = false;
        try { if (u.onend) u.onend({}); } catch(e){}
      }, 150);
    };
    if (window.__mode === 'slow') { window.__pend = true; t1 = setTimeout(start, 2000); }
    else start();
  };
})();"""

RESULTS = []
def ck(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    if not cond:
        print("  FAIL %s   %s" % (label, extra))

STATE_JS = """() => ({
    seq: __T.speech.readSeq(), sp: __T.speech.speakingId(), d: __T.speech.diag(),
    needTap: __T.speech.needTap(), cnt: window.__count })"""

def pump(page, budget_ms=90000):
    t0 = time.time()
    while (time.time() - t0) * 1000 < budget_ms:
        page.wait_for_timeout(70)
        if page.evaluate("() => __T.speech.readSeq()") is None:
            return True
        if page.evaluate("() => __T.speech.needTap()"):
            return False
    return False

def run(label, mode, page, ids, titles):
    lab = "%s/%s" % (label, mode)
    page.evaluate("(m) => { window.__mode = m; window.__spoken = []; window.__swallowed = 0; window.__count = 0; }", mode)
    page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
    page.wait_for_timeout(200)
    ok = pump(page)
    st = page.evaluate(STATE_JS)
    spk = " || ".join(page.evaluate("() => window.__spoken"))
    hit = [t for t in titles if t and t in spk]
    ck(ok, lab + " 1 整页连读到收场", st)
    ck(len(hit) >= len(titles), lab + " 2 每条内容都出声（%d/%d）" % (len(hit), len(titles)), spk[:160])
    ck(st["cnt"] >= len(titles), lab + " 3 发声次数不少于条目数（%d）" % st["cnt"], st["cnt"])
    if mode == "slow":
        ck(st["d"]["wd"] == 0, lab + " 4 慢启动不被误判哑火（wd=%d）" % st["d"]["wd"], st["d"])
        ck(st["d"]["heal"] == 0, lab + " 5 没有触发唤醒重读（heal=%d）" % st["d"]["heal"], st["d"])
        ck(st["d"]["giveUp"] == 0, lab + " 6 没有丢句（giveUp=%d）" % st["d"]["giveUp"], st["d"])
    if mode == "chrome":
        ck(page.evaluate("() => window.__swallowed") == 0,
           lab + " 4 没有被 cancel 吞掉的语句（%d）" % page.evaluate("() => window.__swallowed"),
           page.evaluate("() => __T.speech.snapshot().log"))
    ck(page.evaluate("() => __T.speech.diag().deadItems") == 0,
       lab + " 7 没有整条被放弃（deadItems=%d）" % page.evaluate("() => __T.speech.diag().deadItems"))
    page.evaluate("() => __T.speech.readStop()")
    page.wait_for_timeout(200)

def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for label, vw in [("桌面", {"width": 1440, "height": 900}),
                          ("移动", {"width": 390, "height": 844})]:
            ctx = b.new_context(viewport=vw)
            ctx.add_init_script(MOCK)
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
            page.goto("file:///" + PAGE.replace("\\", "/"), timeout=60000)
            page.wait_for_timeout(1300)
            ck(page.evaluate("() => window.__KV__") == "2026-10-31e", "[%s] 版本 2026-10-31e" % label,
               page.evaluate("() => window.__KV__"))
            page.click("#readModeBtn")
            page.wait_for_selector(".read-scroll")
            page.wait_for_timeout(700)
            ids = page.evaluate("() => __T.speech.readIds()")
            titles = page.evaluate(
                "(ids) => ids.map(id => { const it = __T.play.items().find(x => x.id === id); return it ? it.title : ''; })", ids)
            ck(len(ids) >= 3, "[%s] 至少 3 条可朗读内容" % label, len(ids))
            run(label, "slow", page, ids, titles)
            run(label, "chrome", page, ids, titles)
            run(label, "normal", page, ids, titles)
            ck(not errs, "[%s] Z 无 JS 报错" % label, errs[:3])
            ctx.close()
        b.close()
    bad = [r for r in RESULTS if not r[0]]
    print("\n总计 %d 项，失败 %d 项" % (len(RESULTS), len(bad)))
    for _, l in bad:
        print("  FAILED:", l)
    return 1 if bad else 0

sys.exit(main())
