# -*- coding: utf-8 -*-
"""【已归档】本脚本断言的是第 132~138 条的旧整页朗读实现（分句引擎 / 看门狗计数 / 继续朗读）。
   第 139 条已把播放原子改为「整条知识点」并重写推进逻辑，等价覆盖见 _t_p19.py（normal / noend / mute
   三模型）、_t_p19b.py（云端 audio 与失败回退）、_t_p19c.py（单条朗读）。此脚本仅作历史参考。"""
import os, sys
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")
SHOTS = os.path.join(BASE, "tests", "_shots")

MOCK = r"""(function(){
  if (!window.speechSynthesis) return;
  var s = window.speechSynthesis;
  window.__spoken = []; window.__pending = null; window.__spk = false;
  window.__count = 0; window.__mode = 'normal'; window.__dropAfter = 0;
  window.__errs = [];
  Object.defineProperty(s,'speaking',{configurable:true,get:function(){return window.__spk;}});
  s.getVoices=function(){return [{name:'Mock Chinese',lang:'zh-CN',localService:true}];};
  s.resume=function(){}; s.pause=function(){};
  s.cancel=function(){ window.__pending=null; window.__spk=false; };
  s.speak=function(u){
    window.__count++;
    var n = window.__count, t = String(u.text);
    window.__spoken.push(t);
    if (window.__mode === 'mute') return;
    if (window.__mode === 'ios' && n > window.__dropAfter) return;   /* 静默丢弃，无任何事件 */
    window.__pending = u; window.__spk = true;
    try { if (u.onstart) u.onstart({}); } catch(e){}
  };
  window.__finish=function(){ var u=window.__pending; window.__pending=null; window.__spk=false; if(u&&u.onend)u.onend({}); };
})();"""

RESULTS = []
def ck(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    if not cond:
        print("  FAIL %s  %s" % (label, extra))
    return bool(cond)

def state_js():
    return """() => ({
        seq: __T.speech.readSeq(), sp: __T.speech.speakingId(), bar: __T.speech.readBar(),
        needTap: __T.speech.needTap(), dead: __T.speech.deadItems(),
        d: __T.speech.diag(), cnt: window.__count })"""

def wait_seq_gone(page, rounds=120):
    for _ in range(rounds):
        page.wait_for_timeout(150)
        if page.evaluate("() => __T.speech.readSeq()") is None:
            return True
    return False

def pump_normal(page, rounds=140):
    """正常模型：有待播就手动 finish 推进"""
    for _ in range(rounds):
        page.wait_for_timeout(90)
        if page.evaluate("() => !!window.__pending"):
            page.evaluate("() => window.__finish()")
        if page.evaluate("() => __T.speech.readSeq()") is None:
            return True
    return False

def pump_ios(page, budget_ms):
    """iOS 模型：不能手动推进（被丢弃），只观察；出现 needTap 或序列推进就返回"""
    step = 150
    seen_i = 0
    for _ in range(int(budget_ms / step)):
        page.wait_for_timeout(step)
        st = page.evaluate(state_js())
        if st["seq"] is None:
            return {"end": True, "i": seen_i, "st": st}
        seen_i = max(seen_i, st["seq"]["i"])
        if st["needTap"]:
            return {"end": False, "i": seen_i, "st": st}
    return {"end": False, "i": seen_i, "st": page.evaluate(state_js())}

def run(pw, vw, label):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=vw)
    ctx.add_init_script(MOCK)
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    page.goto("file:///" + PAGE.replace("\\", "/"), timeout=60000)
    page.wait_for_timeout(1300)
    ck(page.evaluate("() => window.__KV__") == "2026-10-31e",
       "[%s] 版本 2026-10-31e" % label, page.evaluate("() => window.__KV__"))

    page.click("#readModeBtn")
    page.wait_for_selector(".read-scroll")
    page.wait_for_timeout(700)
    ids = page.evaluate("() => __T.speech.readIds()")
    items = page.evaluate("() => __T.play.items()")
    title_of = dict((str(i["id"]), (i.get("title") or "")) for i in items)
    ck(len(ids) >= 3, "[%s] 至少有 3 条可朗读内容" % label, len(ids))

    # ---------------- A 正常模型：整页读完
    page.evaluate("() => { window.__mode='normal'; window.__spoken=[]; }")
    page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
    done = pump_normal(page)
    spoken_all = " || ".join(page.evaluate("() => window.__spoken"))
    ck(done, "[%s] A1 整页朗读能读到收场" % label, page.evaluate(state_js()))
    hit3 = [bool(title_of.get(i)) and title_of[i] in spoken_all for i in ids[:3]]
    ck(sum(1 for x in hit3 if x) >= 3, "[%s] A2 前 3 条都发声了" % label, spoken_all[:200])
    ck(page.evaluate("() => __T.speech.readSeq()") is None,
       "[%s] A3 收场后序列清空" % label)

    # ---------------- B 跳过按钮（朗读中）
    page.evaluate("() => { window.__mode='normal'; window.__spoken=[]; }")
    page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
    page.wait_for_timeout(300)
    hit = page.evaluate("""() => {
        const btn = document.getElementById('readSpeakNext');
        if (!btn) return {err:'no btn'};
        const r = btn.getBoundingClientRect();
        const top = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
        return { ok: top === btn || btn.contains(top), tag: top ? top.tagName + '.' + top.className : null };
    }""")
    ck(hit.get("ok") is True, "[%s] B1 「跳过」按钮可被点中（无遮挡）" % label, hit)
    before = page.evaluate("() => __T.speech.readSeq()")
    spoken_before = len(page.evaluate("() => window.__spoken"))
    page.click("#readSpeakNext")
    page.wait_for_timeout(400)
    after = page.evaluate("() => __T.speech.readSeq()")
    spoken_after = len(page.evaluate("() => window.__spoken"))
    ck(before and after and after["i"] > before["i"],
       "[%s] B2 点「跳过」游标确实前进" % label, "%s -> %s" % (before, after))
    ck(spoken_after > spoken_before,
       "[%s] B3 跳过后立即开始读下一条（有新发声）" % label, "%d -> %d" % (spoken_before, spoken_after))
    bar = page.evaluate("() => __T.speech.readBar()")
    ck(bar and ("第 " + str(after["i"] + 1)) in (bar.get("txt") or ""),
       "[%s] B4 浮条文案跟随更新" % label, bar)

    # ---------------- C 停止
    page.click("#readSpeakStop")
    page.wait_for_timeout(300)
    ck(page.evaluate("() => __T.speech.readSeq()") is None, "[%s] C1 停止后序列清空" % label)
    ck(page.evaluate("() => document.getElementById('readSpeakBar').style.display") == "none",
       "[%s] C2 停止后浮条隐藏" % label)

    # ---------------- D iOS 模型：第一条之后全部静默丢弃
    page.evaluate("() => { window.__mode='ios'; window.__dropAfter=1; window.__spoken=[]; window.__count=0; }")
    page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
    r1 = pump_ios(page, 26000)
    ck(r1["i"] >= 1, "[%s] D1 第 1 条读完不卡死，能推进到下一条" % label, r1)
    st1 = r1["st"]
    ck((st1["d"]["wd"] + st1["d"]["heal"] + st1["d"]["giveUp"]) > 0,
       "[%s] D2 哑火自愈被触发" % label, st1["d"])
    if r1["end"]:
        ck(True, "[%s] D3 静默机型也能自动收场" % label)
    else:
        ck(st1["needTap"] is True, "[%s] D3 卡住时给出「继续朗读」入口" % label, st1)
        vis = page.evaluate("""() => {
            const r = document.getElementById('readSpeakResume');
            const n = document.getElementById('readSpeakNext');
            if (!r || !n) return null;
            return { resume: getComputedStyle(r).display, next: getComputedStyle(n).display, txt: (document.getElementById('readSpeakTxt')||{}).textContent };
        }""")
        ck(vis and vis["resume"] != "none" and vis["next"] == "none",
           "[%s] D4 需要手势时显示「继续朗读」并隐藏「跳过」" % label, vis)
        # 点「继续朗读」必须有反应
        cnt0 = page.evaluate("() => window.__count")
        i0 = page.evaluate("() => __T.speech.readSeq()")
        page.click("#readSpeakResume")
        page.wait_for_timeout(600)
        cnt1 = page.evaluate("() => window.__count")
        st2 = page.evaluate(state_js())
        ck(cnt1 > cnt0, "[%s] D5 点「继续朗读」确有新发声尝试" % label, "%d -> %d" % (cnt0, cnt1))
        ck(st2["needTap"] is False, "[%s] D6 点后恢复正常态" % label, st2)
        ck(i0 is not None and (st2["seq"] is None or st2["seq"]["i"] >= i0["i"]),
           "[%s] D7 点后序列继续推进" % label, "%s -> %s" % (i0, st2["seq"]))
    page.evaluate("() => __T.speech.readStop()")
    page.wait_for_timeout(200)

    # ---------------- E 完全静音：不许无限空转
    page.evaluate("() => { window.__mode='mute'; window.__spoken=[]; }")
    page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
    r2 = pump_ios(page, 30000)
    st3 = r2["st"]
    ck(r2["end"] or st3["needTap"] or st3["dead"] >= 1,
       "[%s] E1 静音设备不无限空转（收场或提示）" % label, st3)
    if not r2["end"]:
        # 再给两次手势，最终必须明确收场
        for _ in range(2):
            if page.evaluate("() => __T.speech.readSeq()") is None:
                break
            page.evaluate("() => __T.speech.resume()")
            page.wait_for_timeout(1200)
            r3 = pump_ios(page, 16000)
            if r3["end"]:
                break
    final = page.evaluate(state_js())
    ck(final["seq"] is None or final["needTap"] or page.evaluate("() => __T.speech.readSeq()") is None,
       "[%s] E2 最终不残留半死序列" % label, final)
    page.evaluate("() => __T.speech.readStop()")

    # ---------------- F 零报错
    ck(not errs, "[%s] F1 无 JS 报错" % label, errs[:3])

    # 截图：需要手势时的浮条
    if not r1["end"]:
        try:
            page.evaluate("() => { window.__mode='ios'; window.__dropAfter=1; }")
            page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
            pump_ios(page, 26000)
            page.screenshot(path=os.path.join(SHOTS, "p17_%s_needtap.png" % label))
            page.evaluate("() => __T.speech.readStop()")
        except Exception:
            pass
    ctx.close()
    b.close()

def main():
    if not os.path.isdir(SHOTS):
        os.makedirs(SHOTS)
    with sync_playwright() as pw:
        for label, vw in [("desktop", {"width": 1440, "height": 900}),
                          ("mobile", {"width": 390, "height": 844})]:
            print("=== %s ===" % label)
            run(pw, vw, label)
    bad = [r for r in RESULTS if not r[0]]
    print("\nTOTAL %d / PASS %d / FAIL %d" % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    for _, l in bad:
        print("  FAILED:", l)
    return 1 if bad else 0

sys.exit(main())
