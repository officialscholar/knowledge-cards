# -*- coding: utf-8 -*-
"""【已归档】本脚本断言的是第 132~138 条的旧整页朗读实现（分句引擎 / 看门狗计数 / 继续朗读）。
   第 139 条已把播放原子改为「整条知识点」并重写推进逻辑，等价覆盖见 _t_p19.py（normal / noend / mute
   三模型）、_t_p19b.py（云端 audio 与失败回退）、_t_p19c.py（单条朗读）。此脚本仅作历史参考。"""
import os
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")
SHOTS = os.path.join(BASE, "tests", "_shots")
os.makedirs(SHOTS, exist_ok=True)

results = []


def ck(cond, label, extra=""):
    results.append((bool(cond), label, str(extra)))


SET_JS = "try{localStorage.setItem('knowledge_card_speech_settings_v1', %s)}catch(e){}" % (
    '{"voice":"","rate":0.95,"gap":0}')

MOCK_SPEECH = """(function(){
  window.__spoken = [];
  window.__pending = null;
  window.__silent = false;   /* true: 出声登记但不回调 onend */
  window.__dead = false;     /* true: 完全不出声、无回调 */
  window.__finish = function () {
    var u = window.__pending;
    window.__pending = null;
    if (!u) return;
    if (u.onstart) u.onstart({});
    if (u.onend) u.onend({});
  };
  var s = window.speechSynthesis;
  if (!s) return;
  s.speak = function (u) {
    window.__spoken.push(String(u.text));
    if (window.__dead) return;              /* 全哑：既不出声也不回调 */
    window.__pending = u;
    if (window.__silent) {
      /* 模拟 iOS：声音出来了（onstart + 若干 boundary），但读完不给 onend */
      setTimeout(function () { try { if (u.onstart) u.onstart({}); } catch (e) {} }, 0);
      var n = 0;
      var h = window.setInterval(function () {
        n++;
        try { if (u.onboundary) u.onboundary({}); } catch (e) {}
        if (n >= 4) window.clearInterval(h);
      }, 200);
    }
  };
  s.cancel = function () { window.__pending = null; };
  s.resume = function () {};
  Object.defineProperty(s, 'paused', { get: function () { return false; }, configurable: true });
})();"""

VIEWPORTS = [("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})]

STATE_JS = """() => ({
  ids: __T.speech.readIds(),
  q: __T.speech.readSeq(),
  speakingId: __T.speech.speakingId(),
  bar: __T.speech.readBar(),
  btn: __T.speech.readBtn(),
  diag: __T.speech.diag(),
  spoken: (window.__spoken || []).slice()
})"""

TITLES_JS = """(ids) => {
  const m = {};
  __T.play.items().forEach(i => { m[i.id] = (i.title || '').trim(); });
  return ids.map(id => m[id] !== undefined ? m[id] : '');
}"""


def enter_read(page):
    page.click("#readModeBtn")
    page.wait_for_selector(".read-scroll", timeout=15000)
    page.wait_for_timeout(600)


def scroll_top(page):
    page.evaluate("() => { const sc = document.querySelector('.read-scroll'); if (sc) sc.scrollTop = 0; }")
    page.wait_for_timeout(300)


def pump(page, rounds, stop_at=None):
    for _ in range(rounds):
        st = page.evaluate("() => ({ q: __T.speech.readSeq(), p: !!window.__pending })")
        if not st["q"]:
            break
        if stop_at and st["q"] and stop_at(st["q"]["i"]):
            break
        if st["p"]:
            page.evaluate("() => window.__finish()")
            page.wait_for_timeout(110)
        else:
            page.wait_for_timeout(140)


def wait_progress(page, want_titles, cap_rounds=160):
    """等到 spoken 里出现期望的标题（按序），返回已命中的数量"""
    hit = 0
    for _ in range(cap_rounds):
        st = page.evaluate("() => ({ q: __T.speech.readSeq(), spoken: window.__spoken })" if False else STATE_JS)
        spk = " || ".join(st["spoken"])
        while hit < len(want_titles) and want_titles[hit] and want_titles[hit] in spk:
            hit += 1
        if hit >= len(want_titles):
            break
        if st["q"] is None:
            break
        page.wait_for_timeout(250)
    return hit


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for label, vp in VIEWPORTS:
            ctx = browser.new_context(viewport=vp)
            ctx.add_init_script(SET_JS)
            ctx.add_init_script(MOCK_SPEECH)
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
            page.goto("file:///" + PAGE.replace("\\", "/"), timeout=60000)
            page.wait_for_timeout(1500)
            enter_read(page)
            ids = page.evaluate("() => __T.speech.readIds()")
            titles = page.evaluate(TITLES_JS, ids)
            # 把看门狗宽容量调小，测试不用真等几秒一句
            page.evaluate("() => __T.speech.setWd(200, 1200)")
            ck(len(titles) >= 3 and all(titles[:3]), "[%s] 取到至少 3 条标题" % label, titles[:3])

            # ---------- A 正常连读 ----------
            scroll_top(page)
            page.click("#readSpeakBtn")
            page.wait_for_timeout(400)
            st = page.evaluate(STATE_JS)
            ck(st["q"] and st["q"]["i"] == 0, "[%s] A1 整页朗读从第一条开始" % label, st["q"])
            ck(st["diag"]["heart"], "[%s] A2 序列心跳已启动" % label, st["diag"])
            pump(page, 120, stop_at=lambda i: i >= 2)
            page.wait_for_timeout(250)
            st = page.evaluate(STATE_JS)
            spk = " || ".join(st["spoken"])
            ck(all(t and t in spk for t in titles[0:3]),
               "[%s] A3 正常连读跨到第 3 条" % label, spk[:120])
            ck(st["diag"]["wd"] == 0, "[%s] A4 正常情况看门狗不误触发" % label, st["diag"])
            i_before = st["q"]["i"]
            page.click("#readSpeakNext")
            page.wait_for_timeout(700)
            st2 = page.evaluate(STATE_JS)
            ck(st2["q"] and st2["q"]["i"] == i_before + 1, "[%s] A5 跳过仍然有效" % label, (i_before, st2["q"] and st2["q"]["i"]))
            page.click("#readSpeakStop")
            page.wait_for_timeout(350)
            st3 = page.evaluate(STATE_JS)
            ck(st3["q"] is None and st3["diag"]["heart"] is False, "[%s] A6 停止后序列与心跳都收掉" % label, (st3["q"], st3["diag"]))

            # ---------- B 半哑：第一条读完后 onend 永不再触发（iOS 症状） ----------
            scroll_top(page)
            page.evaluate("() => { window.__spoken = []; window.__silent = true; }")
            page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
            page.wait_for_timeout(200)
            # 第一条手动推进读完之后，回调就再也不会来了（iOS 症状）
            hit = 0
            for _ in range(170):
                st = page.evaluate(STATE_JS)
                spk = " || ".join(st["spoken"])
                while hit < 3 and titles[hit] and titles[hit] in spk:
                    hit += 1
                if hit >= 3 or st["q"] is None:
                    break
                if hit <= 1 and st["diag"]["queue"] and page.evaluate("() => !!window.__pending"):
                    page.evaluate("() => window.__finish()")   # 第一条手动推进
                page.wait_for_timeout(200)
            st = page.evaluate(STATE_JS)
            ck(hit >= 2, "[%s] B1 回调断掉后仍读到第 2 条（自愈生效）" % label, (hit, st["diag"]))
            ck(hit >= 3, "[%s] B2 回调断掉后继续推进到第 3 条" % label, (hit, st["diag"]))
            # 第 136 条：新引擎由轮询接管「读完判定」，计数落在 pollDone；旧计数仍可能非零
            ck((st["diag"]["wd"] + st["diag"]["pollDone"]) > 0, "[%s] B3 看门狗确实被触发" % label, st["diag"])
            ck((st["diag"]["heal"] + st["diag"]["giveUp"] + st["diag"]["recover"] + st["diag"]["pollDone"]) > 0,
               "[%s] B4 有自愈动作（轮询判定/重读/跳句/心跳）" % label, st["diag"])
            page.evaluate("() => __T.speech.readStop()")
            page.wait_for_timeout(300)

            # ---------- C 全哑：彻底不发声也不回调 ----------
            scroll_top(page)
            page.evaluate("() => { window.__spoken = []; window.__dead = true; window.__silent = false; }")
            page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
            page.wait_for_timeout(300)
            hitc = 0
            for _ in range(170):
                st = page.evaluate(STATE_JS)
                spk = " || ".join(st["spoken"])
                while hitc < 2 and titles[hitc] and titles[hitc] in spk:
                    hitc += 1
                if hitc >= 2 or st["q"] is None:
                    break
                page.wait_for_timeout(250)
            st = page.evaluate(STATE_JS)
            ck(hitc >= 2, "[%s] C1 完全静音也不冻结，推进到第 2 条" % label, (hitc, st["diag"]))
            ck(st["diag"]["giveUp"] > 0, "[%s] C2 静音时按「跳句」兜底" % label, st["diag"])
            page.evaluate("() => __T.speech.readStop()")
            page.wait_for_timeout(300)
            st = page.evaluate(STATE_JS)
            ck(st["q"] is None, "[%s] C3 恢复后可正常停止" % label, st["q"])

            page.screenshot(path=os.path.join(SHOTS, "p12_%s.png" % label))
            ck(not errs, "[%s] 无 JS 报错" % label, "; ".join(errs[:3])[:200])
            ctx.close()
        browser.close()

    ok = sum(1 for r in results if r[0])
    bad = [r for r in results if not r[0]]
    for passed, lab, extra in results:
        print(("  ok  " if passed else "  FAIL") + " " + lab + (("   -> " + extra) if (extra and not passed) else ""))
    print("\n通过 %d / %d" % (ok, len(results)))
    if bad:
        print("失败项：")
        for _, lab, extra in bad:
            print("  - " + lab + "  -> " + extra)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
