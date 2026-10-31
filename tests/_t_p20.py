# -*- coding: utf-8 -*-
"""第 140 条：音色切换无效 / 试听起播慢 回归

覆盖：
  A 选中的系统音色必须真的被用上（整页朗读 + 单条朗读 + 试听），且 u.lang 跟着音色走
  B 试听：正在播时点击 → 先 cancel 再空一拍 speak（Chrome 吞 speak 的解法）
  C 试听：合成器被卡死（speak 不出声也不回调）→ 看门狗 2.2s 后重发一次
  D 云端音色并进同一个下拉；选云端走云端，选系统音色不再被云端吞掉
  E 诊断快照带 voiceSel
"""
import os
import time
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")

HUIHUI = "Microsoft Huihui - Chinese (Simplified, PRC)"
KANGKANG = "Microsoft Kangkang - Chinese (Simplified, PRC)"
GOOGLE = "Google 普通话（中国大陆）"

MOCK = r"""(function(){
  var s = window.speechSynthesis;
  if (!s) return;
  var VS = [
    { name: 'Microsoft Huihui - Chinese (Simplified, PRC)', lang: 'zh-CN', localService: true },
    { name: 'Microsoft Kangkang - Chinese (Simplified, PRC)', lang: 'zh-CN', localService: true },
    { name: 'Google 普通话（中国大陆）', lang: 'zh-CN', localService: false }
  ];
  window.__utts = [];
  window.__log = [];
  window.__spk = false;
  window.__pending = null;
  window.__stuck = false;          /* true: speak 完全没反应（模拟合成器卡死） */
  Object.defineProperty(s, 'speaking', { configurable: true, get: function () { return window.__spk; } });
  Object.defineProperty(s, 'pending', { configurable: true, get: function () { return false; } });
  /* 真实 utterance 的 voice 只吃 SpeechSynthesisVoice，mock 的普通对象会抛错；
     这里把 setter 换成普通字段，才能验证「到底把哪个音色塞给了引擎」 */
  try {
    Object.defineProperty(SpeechSynthesisUtterance.prototype, 'voice', {
      configurable: true,
      get: function () { return this.__v || null; },
      set: function (v) { this.__v = v; }
    });
  } catch (e) {}
  s.getVoices = function () { return VS; };
  s.pause = function () {};
  s.resume = function () { window.__log.push({ ev: 'resume', t: Date.now() }); };
  s.cancel = function () {
    window.__log.push({ ev: 'cancel', t: Date.now() });
    window.__pending = null; window.__spk = false;
  };
  s.speak = function (u) {
    window.__log.push({ ev: 'speak', t: Date.now() });
    window.__utts.push({
      text: String(u.text || ''),
      voice: (u.voice && u.voice.name) || '',
      lang: u.lang || '',
      rate: u.rate
    });
    if (window.__stuck) return;
    window.__pending = u;
    window.__spk = true;
    try { if (u.onstart) u.onstart({}); } catch (e) {}
  };
  window.__finish = function () {
    var u = window.__pending;
    window.__pending = null; window.__spk = false;
    try { if (u && u.onend) u.onend({}); } catch (e) {}
  };
})();"""

RES = {"pass": 0, "fail": 0}


def check(ok, label, extra=None):
    if ok:
        RES["pass"] += 1
        print("  ok   ", label)
    else:
        RES["fail"] += 1
        print("  FAIL ", label, "" if extra is None else str(extra)[:260])


def open_read(page):
    page.click("#readModeBtn")
    page.wait_for_selector(".read-scroll", timeout=20000)
    page.wait_for_timeout(500)
    page.click('[data-action="speak-set"]')
    page.wait_for_timeout(200)


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(MOCK)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, timeout=90000)
        page.wait_for_timeout(1500)
        open_read(page)

        print("A 选中的音色必须真的用上")
        pick = page.evaluate("() => __T.speech.pick()")
        check(pick and pick["name"] == GOOGLE, "自动优选挑在线神经音色（基线）", pick)
        page.evaluate("(n) => __T.speech.setVoice(n)", KANGKANG)
        p2 = page.evaluate("() => __T.speech.voicePick()")
        check(p2 and p2["name"] == KANGKANG, "readPlayVoice 尊重手动选择", p2)
        ids = page.evaluate("() => __T.speech.readIds()")
        page.evaluate("(id) => __T.speech.readStart(id)", ids[0])
        page.wait_for_timeout(700)
        u = page.evaluate("() => window.__utts[window.__utts.length - 1]")
        check(u and u["voice"] == KANGKANG, "整页朗读用选中的音色", u)
        check(u and u["lang"] == "zh-CN", "utterance.lang 跟着音色走", u)
        page.evaluate("() => __T.speech.readStop()")
        page.wait_for_timeout(300)

        print("B 试听：正在播时点 → cancel 后空一拍")
        page.evaluate("() => { window.__log = []; window.__utts = []; }")
        page.evaluate("() => __T.speech.readStart(null)")   # 先让它读起来
        page.wait_for_timeout(600)
        page.evaluate("() => { window.__log = []; window.__utts = []; }")
        page.evaluate("() => __T.speech.preview()")
        page.wait_for_timeout(900)
        log = page.evaluate("() => window.__log")
        u2 = page.evaluate("() => window.__utts[0] || null")
        check(u2 and u2["voice"] == KANGKANG, "试听用当前选中的音色", u2)
        check(u2 and u2["text"] == page.evaluate("() => __T.speech.previewText()"), "试听读的是样例句", u2)
        spk = [x for x in log if x["ev"] == "speak"]
        can = [x for x in log if x["ev"] == "cancel"]
        gap = (spk[0]["t"] - can[-1]["t"]) if (spk and can) else -1
        check(bool(spk) and bool(can) and gap >= 100, "cancel → speak 之间留了空档", {"gap": gap, "log": log})
        page.wait_for_timeout(300)
        page.evaluate("() => window.__finish()")
        page.wait_for_timeout(200)
        st = page.evaluate("() => __T.speech.previewState()")
        check(st["btn"].strip().startswith("▶"), "试听结束按钮复位", st)

        print("B2 空闲时点试听 → 立刻发声，不多余 cancel")
        page.evaluate("() => __T.speech.readStop()")
        page.wait_for_timeout(500)
        page.evaluate("() => { window.__log = []; window.__utts = []; window.__t0 = Date.now(); }")
        page.evaluate("() => __T.speech.preview()")
        page.wait_for_timeout(320)
        log = page.evaluate("() => window.__log")
        spk = [x for x in log if x["ev"] == "speak"]
        can = [x for x in log if x["ev"] == "cancel"]
        t0 = page.evaluate("() => window.__t0")
        gap = (spk[0]["t"] - t0) if spk else -1
        check(bool(spk) and gap < 120, "空闲时起播 <120ms", {"gap": gap, "log": log})
        check(not can, "空闲时没有多余 cancel", can)
        page.evaluate("() => window.__finish()")
        page.wait_for_timeout(200)

        print("C 合成器卡死 → 看门狗重发")
        page.evaluate("() => { window.__stuck = true; window.__spk = false; window.__log = []; window.__utts = []; }")
        page.evaluate("() => __T.speech.preview()")
        page.wait_for_timeout(900)
        n1 = page.evaluate("() => window.__utts.length")
        page.wait_for_timeout(2600)
        n2 = page.evaluate("() => window.__utts.length")
        check(n1 == 1, "首次只发一次（不抢跑）", n1)
        check(n2 >= 2, "2.2s 后看门狗重发", n2)
        st = page.evaluate("() => __T.speech.previewState()")
        check("重试" in st["hint"] or "正在用" in st["hint"], "重试时给了明确状态提示", st)
        page.wait_for_timeout(2400)
        st = page.evaluate("() => __T.speech.previewState()")
        check("没有声音" in st["hint"], "彻底没声时给出结论提示", st)
        page.evaluate("() => { window.__stuck = false; }")

        print("D 云端音色与系统音色互不劫持")
        page.evaluate("() => __T.speech.ttsSetCloud({ on: true, key: 'k', region: 'eastasia' })")
        page.evaluate("() => __T.speech.setVoice('')")
        check(page.evaluate("() => __T.speech.useCloud()") is True, "自动 + 云端开 → 走云端", None)
        page.evaluate("(n) => __T.speech.setVoice(n)", KANGKANG)
        check(page.evaluate("() => __T.speech.useCloud()") is False, "选了系统音色 → 不被云端劫持", None)
        page.evaluate("() => __T.speech.setVoice('cloud:zh-CN-YunxiNeural')")
        check(page.evaluate("() => __T.speech.useCloud()") is True, "选了云端音色 → 走云端", None)
        c = page.evaluate("() => __T.speech.settings().cloud")
        check(c["on"] is True and c["voice"] == "zh-CN-YunxiNeural", "云端音色同步进 cloud.voice", c)
        st = page.evaluate("() => __T.speech.previewState()")
        check(any(o.startswith("cloud:zh-CN-XiaoxiaoNeural") for o in st["opts"]), "下拉里有云端音色组", st["opts"])
        check(st["selVal"] == "cloud:zh-CN-YunxiNeural", "下拉选中项跟着走", st["selVal"])
        hint = page.evaluate("() => document.getElementById('speakVoiceHint').textContent")
        check("云端" in hint, "当前音色说明写的是云端", hint)

        print("E 诊断")
        page.evaluate("(n) => __T.speech.setVoice(n)", HUIHUI)
        snap = page.evaluate("() => __T.speech.snapshot()")
        vs = snap.get("voiceSel") or {}
        check(vs.get("sel") == HUIHUI, "诊断里有选择项", vs)
        check(vs.get("cloudId") == "", "诊断里 cloudId 为空", vs)
        check("last" in vs, "诊断里有上次实际发声的音色", vs)

        print("F 落盘")
        page.reload()
        page.wait_for_timeout(1500)
        page.evaluate("() => __T.speech.setVoice('%s')" % KANGKANG)
        page.reload()
        page.wait_for_timeout(1500)
        v = page.evaluate("() => __T.speech.settings().voice")
        check(v == KANGKANG, "选择已存 localStorage", v)

        check(not errs, "无 JS 报错", errs)
        b.close()

    print("\n== %d pass / %d fail ==" % (RES["pass"], RES["fail"]))
    return 1 if RES["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
