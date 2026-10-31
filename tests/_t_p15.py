# -*- coding: utf-8 -*-
"""【已归档】本脚本断言的是第 132~138 条的旧整页朗读实现（分句引擎 / 看门狗计数 / 继续朗读）。
   第 139 条已把播放原子改为「整条知识点」并重写推进逻辑，等价覆盖见 _t_p19.py（normal / noend / mute
   三模型）、_t_p19b.py（云端 audio 与失败回退）、_t_p19c.py（单条朗读）。此脚本仅作历史参考。"""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")

MOCK = r"""
(function(){
  if (!window.speechSynthesis) return;
  var s = window.speechSynthesis;
  window.__spoken = [];
  window.__pending = null;
  window.__spk = false;
  window.__mode = 'normal';          // normal | silent | mute
  Object.defineProperty(s, 'speaking', { configurable: true, get: function () { return window.__spk; } });
  s.getVoices = function () { return [{ name: 'Mock Chinese', lang: 'zh-CN', localService: true }]; };
  s.resume = function () {};
  s.pause = function () {};
  s.cancel = function () { window.__pending = null; window.__spk = false; };
  s.speak = function (u) {
    window.__spoken.push(String(u.text));
    if (window.__mode === 'mute') return;                       // 完全静音：没有任何动静
    window.__pending = u;
    window.__spk = true;
    try { if (u.onstart) u.onstart({}); } catch (e) {}
    if (window.__mode === 'silent') {                            // iOS 症状：播完了、speaking 落回 false，但永远不给 onend
      setTimeout(function () { window.__spk = false; }, 60);
    }
  };
  window.__finish = function () {
    var u = window.__pending; window.__pending = null; window.__spk = false;
    if (u && u.onend) u.onend({});
  };
})();
"""

results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

STATE_JS = """() => ({
    seq: __T.speech.readSeq(),
    speakingId: __T.speech.speakingId(),
    tick: __T.speech.tickOn(),
    diag: __T.speech.diag(),
    n: window.__spoken.length,
    btn: __T.speech.readBtn()
})"""

def pump(page, mode, budget_ms=45000):
    """推进到整页读完（或超时），返回到达的最大条目下标"""
    best = -1
    t0 = time.time()
    while (time.time() - t0) * 1000 < budget_ms:
        st = page.evaluate(STATE_JS)
        if st["seq"] is None:
            return best, True, st
        best = max(best, st["seq"]["i"])
        if mode == "normal":
            if page.evaluate("() => !!window.__pending"):
                page.evaluate("() => window.__finish()")
            else:
                page.wait_for_timeout(40)
        else:
            page.wait_for_timeout(80)
    return best, False, page.evaluate(STATE_JS)

def run(label, mode, page, titles, ids):
    lab = "%s/%s" % (label, mode)
    page.evaluate("(m) => { window.__mode = m; window.__spoken = []; }", mode)
    page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
    page.wait_for_timeout(200)
    best, finished, st = pump(page, mode)
    spk = " || ".join(page.evaluate("() => window.__spoken"))
    hit = [t for t in titles if t and t in spk]
    if mode == "mute":
        # 第 137 条：完全无声的设备不再静默刷完一整页（那会谎报「本页已读完」），
        # 改为最多两次「点一下继续」后明确收场。这里断言的是「不卡死 + 不无限空转」。
        check(lab + " 1 不卡在第 1 条（推到第 %d 条）" % (best + 1),
              best >= 1 or page.evaluate("() => __T.speech.needTap()"))
        check(lab + " 2 不无限空转（收场或请求手势）",
              finished or page.evaluate("() => __T.speech.needTap()"))
        for _ in range(3):
            if page.evaluate("() => __T.speech.readSeq()") is None:
                break
            page.evaluate("() => __T.speech.resume()")
            page.wait_for_timeout(300)
            b2, f2, st2 = pump(page, mode, 20000)
            best = max(best, b2)
            if f2:
                break
        st = page.evaluate(STATE_JS)
        check(lab + " 3 两次手势后干净收场", st["seq"] is None)
        check(lab + " 4 收场后无后台轮询", st["tick"] is False)
        check(lab + " 5 收场后按钮复位", st["btn"]["on"] is False)
        d = st["diag"]
        used = ((d.get("pollDone") or 0) + (d.get("giveUp") or 0) + (d.get("heal") or 0)
                + (d.get("recover") or 0) + (d.get("deadItems") or 0))
        check(lab + " 6 兜底被触发（计数 %d）" % used, used > 0)
        return st
    check(lab + " 1 不止读第 1 条（推到第 %d 条）" % (best + 1), best >= 2)
    check(lab + " 2 整页读完并自动收场", finished)
    check(lab + " 3 每条内容都送进合成器（%d/%d）" % (len(hit), len(titles)), len(hit) >= len(titles))
    check(lab + " 4 收场后无后台轮询", st["tick"] is False)
    check(lab + " 5 收场后按钮复位", st["btn"]["on"] is False)
    if mode != "normal":
        d = st["diag"]
        used = (d.get("pollDone") or 0) + (d.get("giveUp") or 0) + (d.get("heal") or 0) + (d.get("recover") or 0)
        check(lab + " 6 兜底被触发（计数 %d）" % used, used > 0)
    return st

with sync_playwright() as pw:
    b = pw.chromium.launch()
    for label, vw in [("桌面", {"width": 1440, "height": 900}), ("移动", {"width": 390, "height": 844})]:
        ctx = b.new_context(viewport=vw)
        ctx.add_init_script(MOCK)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto("file:///" + PAGE.replace("\\", "/"), timeout=60000)
        page.wait_for_timeout(1300)
        page.click("#readModeBtn")
        page.wait_for_selector(".read-scroll")
        page.wait_for_timeout(600)
        ids = page.evaluate("() => __T.speech.readIds()")
        titles = page.evaluate("(ids) => ids.map(id => { const it = __T.play.items().find(x => x.id === id); return it ? it.title : ''; })", ids)
        check(label + " 0 本页有 >=3 条可朗读内容", len(ids) >= 3)

        run(label, "normal", page, titles, ids)
        run(label, "silent", page, titles, ids)
        run(label, "mute", page, titles, ids)

        # D 停止必须干净收场
        page.evaluate("() => { window.__mode = 'normal'; }")
        page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
        page.wait_for_timeout(500)
        page.evaluate("() => __T.speech.readStop()")
        page.wait_for_timeout(400)
        st = page.evaluate(STATE_JS)
        check(label + " D1 停止后序列清空", st["seq"] is None)
        check(label + " D2 停止后轮询关闭", st["tick"] is False)
        check(label + " D3 停止后按钮复位", st["btn"]["on"] is False)

        # E 诊断快照（真机取证入口）
        snap = page.evaluate("() => __T.speech.snapshot()")
        txt = page.evaluate("() => __T.speech.snapshotText()")
        check(label + " E1 快照含关键字段", isinstance(snap, dict) and "ver" in snap and "ua" in snap and "counters" in snap)
        check(label + " E2 快照文本是可粘贴 JSON", txt.strip().startswith("{") and "tickRuns" in txt)

        check(label + " Z1 零 JS 报错", len(errs) == 0)
        if errs: print("   errors:", errs[:3])
        ctx.close()
    b.close()

fails = [n for n, ok in results if not ok]
print("\n==== 总计 %d 项，失败 %d 项 ====" % (len(results), len(fails)))
for n in fails: print("  FAIL:", n)
sys.exit(1 if fails else 0)
