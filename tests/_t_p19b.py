# -*- coding: utf-8 -*-
"""第 139 条补充：云端整条播放（audio 路径）与云端失败回退系统音色"""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")

MOCK_SP = r"""(function(){
  if (!window.speechSynthesis) return;
  var s = window.speechSynthesis;
  window.__spoken = []; window.__pending = null; window.__spk = false;
  Object.defineProperty(s,'speaking',{configurable:true,get:function(){return window.__spk;}});
  Object.defineProperty(s,'pending',{configurable:true,get:function(){return false;}});
  s.getVoices=function(){return [{name:'Microsoft Huihui - Chinese',lang:'zh-CN',localService:true}];};
  s.resume=function(){}; s.pause=function(){};
  s.cancel=function(){ window.__pending=null; window.__spk=false; };
  s.speak=function(u){ window.__spoken.push(String(u.text)); if(window.__mode==='mute')return;
    window.__pending=u; window.__spk=true; try{if(u.onstart)u.onstart({});}catch(e){} };
  window.__finish=function(){ var u=window.__pending; window.__pending=null; window.__spk=false; if(u&&u.onend)u.onend({}); };
})();"""

MOCK_AUDIO = r"""(function(){
  window.__audioPlays = 0;
  window.Audio = function () {
    var self = this;
    this.preload=''; this.muted=false; this.src=''; this.paused=true; this.ended=false; this.currentTime=0;
    this.onended=null; this.onerror=null; this.ontimeupdate=null;
    this.play = function () {
      self.paused = false; self.ended = false; self.currentTime = 0;
      window.__audioPlays++;
      window.__audioCtl = { finish: function () {
        self.currentTime = 9;
        if (self.ontimeupdate) self.ontimeupdate({});
        self.paused = true; self.ended = true;
        if (self.onended) self.onended({});
      } };
      return Promise.resolve();
    };
    this.pause = function () { self.paused = true; };
  };
})();"""

STATE = """() => ({
  seq: __T.speech.readSeq(),
  mode: __T.speech.play().mode,
  heard: __T.speech.play().heard,
  bar: __T.speech.readBar(),
  plays: window.__audioPlays,
  spoken: (window.__spoken || []).length
})"""

R = {"pass": 0, "fail": 0, "msg": []}


def check(ok, label, extra=None):
    if ok:
        R["pass"] += 1
    else:
        R["fail"] += 1
        R["msg"].append("FAIL " + label + ("  << " + str(extra)[:200] if extra is not None else ""))
        print("  FAIL", label, str(extra)[:200] if extra is not None else "")


def run(browser, label, status, expect_mode, use_audio_mock):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(MOCK_SP)
    if use_audio_mock:
        ctx.add_init_script(MOCK_AUDIO)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))

    def handler(route, request):
        if request.method == "OPTIONS":
            route.fulfill(status=204, headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS"})
        elif status == 200:
            route.fulfill(status=200, headers={
                "Access-Control-Allow-Origin": "*", "Content-Type": "audio/mpeg"}, body=b"\x00" * 4096)
        else:
            route.fulfill(status=status, headers={"Access-Control-Allow-Origin": "*"}, body=b"denied")

    p.route("**/*.tts.speech.microsoft.com/**", handler)
    p.goto(URL, timeout=90000)
    p.wait_for_timeout(1400)
    p.evaluate("() => __T.speech.ttsSetCloud({ on: true, key: 'testkey', region: 'eastasia' })")
    check(p.evaluate("() => __T.speech.ttsReady()") is True, "[%s] 云端已就绪" % label)

    p.click("#readModeBtn")
    p.wait_for_selector(".read-scroll")
    p.wait_for_timeout(700)
    ids = p.evaluate("() => __T.speech.readIds()")
    texts = p.evaluate("(a) => a.map(i => __T.speech.readText(i))", ids)
    real = [(i, t) for i, t in zip(ids, texts) if t]

    p.evaluate("(id) => __T.speech.readStart(id)", real[0][0])
    p.wait_for_timeout(700)
    st = p.evaluate(STATE)
    ok_mode = st["mode"] in (expect_mode if isinstance(expect_mode, (list, tuple)) else [expect_mode])
    check(ok_mode, "[%s] 引擎模式 ∈ %s" % (label, expect_mode), st["mode"])

    t0 = time.time()
    guard = 0
    while (time.time() - t0) < 70 and guard < 400:
        guard += 1
        st = p.evaluate(STATE)
        if st["seq"] is None:
            break
        if st["mode"] == "cloud" and use_audio_mock:
            if p.evaluate("() => !!(window.__audioCtl)"):
                p.evaluate("() => window.__audioCtl.finish()")
                page_ok = True
        elif p.evaluate("() => !!window.__pending"):
            p.evaluate("() => window.__finish()")
        p.wait_for_timeout(80)

    st = p.evaluate(STATE)
    if status == 200:
        check(p.evaluate("() => window.__audioPlays") >= len(real) - 1,
              "[%s] 每条一个 audio（播放 %d 次 / %d 条）" % (label, p.evaluate("() => window.__audioPlays"), len(real)))
        reqs = p.evaluate("() => window.__ttsReqCount || 0")
        check(reqs <= len(real) + 2, "[%s] 云端请求数 ≈ 条数（整条一次，含预取）%d" % (label, reqs), reqs)
    check(st["seq"] is None, "[%s] 读完整页自动收场" % label, st["seq"])
    spoken = p.evaluate("() => window.__spoken")
    check(len(spoken) > 0 or status == 200, "[%s] 回退后确实发声了（%d 次）" % (label, len(spoken)), len(spoken))
    check(len(errs) == 0, "[%s] 零 JS 报错" % label, errs[:2])
    ctx.close()


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        print("=== 云端 audio 正常路径 ===")
        run(b, "cloud-audio", 200, "cloud", True)
        print("=== 云端 401 回退 ===")
        run(b, "cloud-401", 401, ["cloud", "system"], False)
        b.close()
    print("\nTOTAL pass=%d fail=%d" % (R["pass"], R["fail"]))
    for m in R["msg"]:
        print(m)
    sys.exit(1 if R["fail"] else 0)


main()
