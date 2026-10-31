# -*- coding: utf-8 -*-
"""第 139 条：整页朗读引擎重构（整条为播放原子）回归
   三种系统模型：normal（正常回调）/ noend（出声但永不回调，iOS 症状）/ mute（完全静音）
   重点断言：① 每条只发声一次（不再逐句切碎）② 能真正读完本页 ③ 跳过立刻生效 ④ 浮条可点中
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")
URL = "file:///" + PAGE.replace("\\", "/")

MOCK = r"""(function(){
  if (!window.speechSynthesis) return;
  var s = window.speechSynthesis;
  window.__spoken = [];
  window.__pending = null;
  window.__spk = false;
  window.__mode = 'normal';
  window.__speakCount = 0;
  Object.defineProperty(s, 'speaking', { configurable: true, get: function () { return window.__spk; } });
  Object.defineProperty(s, 'pending', { configurable: true, get: function () { return false; } });
  s.getVoices = function () { return [
    { name: 'Microsoft Huihui - Chinese', lang: 'zh-CN', localService: true },
    { name: 'Mock Online Neural', lang: 'zh-CN', localService: false }
  ]; };
  s.resume = function () {};
  s.pause = function () {};
  s.cancel = function () { window.__pending = null; window.__spk = false; };
  s.speak = function (u) {
    window.__speakCount++;
    window.__spoken.push(String(u.text));
    if (window.__mode === 'mute') return;          /* 完全静音：不发任何事件，speaking 永远 false */
    window.__pending = u;
    window.__spk = true;
    try { if (u.onstart) u.onstart({}); } catch (e) {}
  };
  /* silentOnly=true 时只把 speaking 变 false，不触发 onend —— iOS 的典型症状 */
  window.__finish = function (silentOnly) {
    var u = window.__pending;
    window.__pending = null;
    window.__spk = false;
    if (silentOnly) return;
    try { if (u && u.onend) u.onend({}); } catch (e) {}
  };
})();"""

STATE = """() => {
  const sp = window.speechSynthesis;
  return {
    seq: __T.speech.readSeq(),
    spk: !!sp.speaking,
    mode: __T.speech.play().mode,
    heard: __T.speech.play().heard,
    polling: __T.speech.play().polling,
    needTap: __T.speech.needTap(),
    bar: __T.speech.readBar(),
    btn: __T.speech.readBtn(),
    mark: __T.speech.readMark(),
    n: window.__speakCount,
    diag: __T.speech.diag()
  };
}"""

RESULT = {"pass": 0, "fail": 0, "msgs": []}


def check(ok, label, extra=None):
    if ok:
        RESULT["pass"] += 1
    else:
        RESULT["fail"] += 1
        RESULT["msgs"].append("FAIL " + label + ("" if extra is None else "  << " + str(extra)))
        print("  FAIL", label, "" if extra is None else str(extra)[:220])


def pump(page, mode, budget_ms=40000, stop_after_items=None):
    """推进 mock 播放，直到整页读完 / 需要手势 / 超预算"""
    t0 = time.time()
    seen = -1
    while (time.time() - t0) * 1000 < budget_ms:
        st = page.evaluate(STATE)
        if st["seq"] is None or st["needTap"]:
            return st, seen
        if st["seq"]["i"] != seen:
            seen = st["seq"]["i"]
        if page.evaluate("() => !!window.__pending"):
            page.evaluate("(s) => window.__finish(s)", mode == "noend")
            page.wait_for_timeout(40)
        else:
            page.wait_for_timeout(70)
        if stop_after_items is not None and seen >= stop_after_items:
            return page.evaluate(STATE), seen
    return page.evaluate(STATE), seen


def run_case(browser, label, vw, ua, mode):
    ctx = browser.new_context(viewport=vw, user_agent=ua)
    ctx.add_init_script(MOCK)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(URL, timeout=90000)
    p.wait_for_timeout(1500)
    p.evaluate("() => { window.__mode = '%s'; }" % mode)
    # 加速「从未出声」的兜底，否则静音模型要等 8 秒/条
    p.evaluate("() => __T.speech.playTune({ idle: 900 })")

    p.click("#readModeBtn")
    p.wait_for_selector(".read-scroll")
    p.wait_for_timeout(700)

    ids = p.evaluate("() => __T.speech.readIds()")
    texts = p.evaluate("(a) => a.map(id => __T.speech.readText(id))", ids)
    real = [(i, t) for i, t in zip(ids, texts) if t]
    check(len(real) >= 3, "[%s] 至少 3 条可朗读内容" % label, len(real))

    # ---------- A 启动 ----------
    p.evaluate("(id) => __T.speech.readStart(id)", real[0][0])
    p.wait_for_timeout(260)
    st = p.evaluate(STATE)
    check(st["seq"] is not None and st["seq"]["i"] == 0, "[%s] A1 序列从第 1 条开始" % label, st["seq"])
    check(st["bar"]["vis"], "[%s] A2 浮条立刻出现" % label, st["bar"])
    check("1/" in st["bar"]["txt"], "[%s] A3 浮条显示第 1/N 条" % label, st["bar"]["txt"])
    check(st["btn"]["on"], "[%s] A4 顶栏按钮变「停止」" % label, st["btn"])

    # ---------- B 浮条按钮可点中（真机上点不到是历史 bug） ----------
    hit = p.evaluate("""() => {
        const b = document.getElementById('readSpeakNext');
        if (!b) return { err: 'no button' };
        const r = b.getBoundingClientRect();
        const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return { topIsBtn: !!top && (top === b || b.contains(top)), z: getComputedStyle(document.getElementById('readSpeakBar')).zIndex,
                 inView: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth };
    }""")
    check(hit.get("topIsBtn") is True, "[%s] B1 跳过按钮是最上层可点元素" % label, hit)
    check(hit.get("z") == "300", "[%s] B2 浮条 z-index=300（不被内容层遮挡）" % label, hit.get("z"))
    check(hit.get("inView") is True, "[%s] B3 浮条完整在屏内" % label, hit)

    if mode == "mute":
        # ---------- 静音：不无限空转，最多两次手势后明确收场 ----------
        st, _ = pump(p, mode, 15000)
        check(st["needTap"] or st["seq"] is None, "[%s] C1 静音时不无限空转（请求手势或收场）" % label, st)
        taps = 0
        while taps < 3 and st["seq"] is not None:
            p.evaluate("() => __T.speech.resume()")
            taps += 1
            st, _ = pump(p, mode, 6000)
        st = p.evaluate(STATE)
        check(st["seq"] is None, "[%s] C2 两次手势仍无声 → 干净收场" % label, st["seq"])
        check(st["btn"]["on"] is False, "[%s] C3 收场后顶栏按钮复位" % label, st["btn"])
        check(st["bar"]["vis"] is False, "[%s] C4 收场后浮条消失" % label, st["bar"])
        check(len(errs) == 0, "[%s] C5 零 JS 报错" % label, errs[:2])
        ctx.close()
        return

    # ---------- C 跳过：立刻生效 ----------
    before = p.evaluate("() => window.__speakCount")
    p.evaluate("() => { const b = document.getElementById('readSpeakNext'); b.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, cancelable:true})); }")
    p.wait_for_timeout(420)
    st2 = p.evaluate(STATE)
    check(st2["seq"]["i"] == 1, "[%s] C1 跳过后游标 +1" % label, st2["seq"])
    check("第 2/" in st2["bar"]["txt"], "[%s] C2 浮条立刻显示第 2 条" % label, st2["bar"]["txt"])
    check(p.evaluate("() => window.__speakCount") > before, "[%s] C3 跳过后立刻发起下一条朗读" % label, before)
    check(st2["mark"] == real[1][0], "[%s] C4 高亮切到第 2 条" % label, st2["mark"])

    # ---------- D 连读到本页最后一条 ----------
    last_id = real[-1][0]
    st3, best = pump(p, mode, 60000)
    spoken = p.evaluate("() => window.__spoken")
    joined = " || ".join(spoken)
    check(real[-1][0] == last_id and any(real[-1][1] in s for s in spoken),
          "[%s] D1 读到本页最后一条" % label, {"last": last_id, "n": len(spoken), "seq": st3["seq"]})
    check(st3["seq"] is None, "[%s] D2 读完自动收场" % label, st3["seq"])
    check(st3["bar"]["vis"] is False, "[%s] D3 收场后浮条消失" % label, st3["bar"])
    check(st3["btn"]["on"] is False, "[%s] D4 收场后按钮复位" % label, st3["btn"])

    # ---------- E 关键：整条为原子，不再逐句切碎 ----------
    check(len(spoken) <= len(real) + 2,
          "[%s] E1 每条只发声一次（发声 %d 次 / %d 条）" % (label, len(spoken), len(real)),
          {"spoken": len(spoken), "items": len(real)})
    first = real[0][1]
    check(any(first == s for s in spoken),
          "[%s] E2 首次发声内容 = 整条第 1 条全文" % label,
          {"expect_len": len(first), "got_len": [len(x) for x in spoken[:2]]})

    # ---------- F 停止 ----------
    p.evaluate("(id) => __T.speech.readStart(id)", real[0][0])
    p.wait_for_timeout(250)
    p.evaluate("() => { const b = document.getElementById('readSpeakStop'); b.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, cancelable:true})); }")
    p.wait_for_timeout(350)
    st4 = p.evaluate(STATE)
    check(st4["seq"] is None, "[%s] F1 停止后序列清空" % label, st4["seq"])
    check(st4["spk"] is False and p.evaluate("() => !!window.__pending") is False,
          "[%s] F2 停止后合成器已静音" % label, {"spk": st4["spk"]})
    check(st4["btn"]["on"] is False and st4["bar"]["vis"] is False, "[%s] F3 停止后界面复位" % label, st4)

    check(len(errs) == 0, "[%s] G1 零 JS 报错" % label, errs[:2])
    ctx.close()


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        cases = [
            ("桌面-normal", {"width": 1440, "height": 900}, None, "normal"),
            ("桌面-noend", {"width": 1440, "height": 900}, None, "noend"),
            ("手机-normal", {"width": 390, "height": 844},
             "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
             "normal"),
            ("手机-noend", {"width": 390, "height": 844},
             "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
             "noend"),
            ("手机-mute", {"width": 390, "height": 844},
             "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
             "mute"),
        ]
        for label, vw, ua, mode in cases:
            print("=== %s ===" % label)
            try:
                run_case(b, label, vw, ua, mode)
            except Exception as e:
                check(False, "[%s] 用例异常" % label, repr(e)[:300])
        b.close()
    print("\nTOTAL  pass=%d  fail=%d" % (RESULT["pass"], RESULT["fail"]))
    for m in RESULT["msgs"]:
        print(m)
    sys.exit(1 if RESULT["fail"] else 0)


main()
