# -*- coding: utf-8 -*-
"""第 134 条（第二轮）：把看门狗从「一句一个长超时」改成两段式
   1) 开播检测：speak() 后 1.6s 内没有 onstart → 基本等于没出声 → 唤醒重读一次，再不行就跳句
   2) 发声进度滑窗：一旦有 onboundary 持续上报，就把超时紧贴到「上一次发声 + 3.5s」，
      句子再长也不会被误杀，读完不给回调的 iOS 也能马上接管
   同时给「连续哑火」状态降级：后续句子的超时收紧，避免整机静音时每句都苦等十几秒。
"""
import io
import os
import re

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
SRC = os.path.join(BASE, "index.html")
with io.open(SRC, "r", encoding="utf-8") as f:
    html = f.read()

REGIONS = []
SUBS = []


def sub(old, new, cnt=1, label=""):
    SUBS.append([old, new, cnt, label])


# ---------------------------------------------------------------- 常量与对策补充
OLD_CONST = """const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '' };
let SPEECH_WD_SLACK = 7000;                 /* 句预计时长之外再给的宽容量（测试可调） */"""
NEW_CONST = """const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '' };
let SPEECH_WD_SLACK = 4000;                 /* 结束回调迟迟不来时的宽容量（测试可调） */
let SPEECH_WD_GAP = 3500;                   /* 有发声进度时，距上一次发声事件的最大静默 */
const SPEECH_WD_START = 1600;               /* 开播检测：说完这个时间还没出声就是没出声 */"""
sub(OLD_CONST, NEW_CONST, 1, "看门狗常量改成两段式")

# 让放弃也对「连续哑火」计数息稍，后继句子不再苦等
sub("""  /* 出过声却没给结束回调（或唤醒后依旧没声）：丢掉这一句往后走，别停在半路 */
  try { window.speechSynthesis.cancel(); } catch (e) {}
  speechDiag.giveUp++;
  q.wdTries = 0;""",
    """  /* 出过声却没给结束回调（或唤醒后依旧没声）：丢掉这一句往后走，别停在半路 */
  try { window.speechSynthesis.cancel(); } catch (e) {}
  speechDiag.giveUp++;
  q.deadStreak = (q.deadStreak || 0) + 1;    /* 连续哑火 → 后面几句的超时收紧 */
  q.wdTries = 0;""", 1, "连续哑火计数")

# ---------------------------------------------------------------- speechNext 改成两段式
REGIONS.append([
    "function speechNext() {",
    "function speakItem(item, keepSeq) {",
    None,  # placeholder，下面用 SUBS 精替换
    "占位",
])
REGIONS.clear()

OLD_NEXT_HEAD = """function speechNext() {
  const q = speechQueue;
  if (!q || state.speakingId !== q.id) return;
  if (q.i >= q.parts.length) { speechFinish(q.id); return; }
  speechClearWd(q);
  const idx = q.i;
  const gen = (q.gen || 0) + 1;
  q.gen = gen;
  q.spoke = false;
  const u = new SpeechSynthesisUtterance(q.parts[q.i]);
  u.rate = speechSettings.rate;
  u.pitch = SPEECH_CONFIG.pitch;
  u.volume = SPEECH_CONFIG.volume;
  u.lang = SPEECH_CONFIG.lang;
  const v = getChineseVoice();
  /* 少数浏览器对「非 getVoices() 来源的音色」赋值会抛错，不能让整句朗读崩掉 */
  if (v) { try { u.voice = v; q.voice = v; } catch (e) { q.voice = null; } }
  const alive = () => speechQueue === q && q.i === idx && q.gen === gen;
  const settle = (fn) => (ev) => { if (!alive()) return; speechClearWd(q); q.wdTries = 0; fn(ev); };
  /* 出声标记：看门狗据此判断是「没发声」还是「发过声但没回调」 */
  u.onstart = () => { if (alive()) q.spoke = true; };
  u.onboundary = () => { if (alive()) q.spoke = true; };"""

NEW_NEXT_HEAD = """function speechNext() {
  const q = speechQueue;
  if (!q || state.speakingId !== q.id) return;
  if (q.i >= q.parts.length) { speechFinish(q.id); return; }
  speechClearWd(q);
  const idx = q.i;
  const gen = (q.gen || 0) + 1;
  q.gen = gen;
  q.spoke = false;
  q.boundaries = 0;
  const text = q.parts[idx];
  const u = new SpeechSynthesisUtterance(text);
  u.rate = speechSettings.rate;
  u.pitch = SPEECH_CONFIG.pitch;
  u.volume = SPEECH_CONFIG.volume;
  u.lang = SPEECH_CONFIG.lang;
  const v = getChineseVoice();
  /* 少数浏览器对「非 getVoices() 来源的音色」赋值会抛错，不能让整句朗读崩掉 */
  if (v) { try { u.voice = v; q.voice = v; } catch (e) { q.voice = null; } }
  const alive = () => speechQueue === q && q.i === idx && q.gen === gen;
  const arm = (ms) => {
    if (q.wd) clearTimeout(q.wd);
    q.wd = setTimeout(() => speechStalled(q, idx, gen), ms);
  };
  const settle = (fn) => (ev) => {
    if (!alive()) return;
    speechClearWd(q); q.wdTries = 0; q.deadStreak = 0; fn(ev);
  };
  /* 出过声：给整句估算时长（连续哑火时收紧）；万一漏了 onstart，边界事件也能补标记 */
  u.onstart = () => {
    if (!alive()) return;
    q.spoke = true;
    arm(Math.max(2500, speechEstimateMs(text) + (q.deadStreak ? 2500 : SPEECH_WD_SLACK)));
  };
  /* 持续有朗读进度 → 超时紧贴「上一次发声 + SPEECH_WD_GAP」，长句不会被误杀 */
  u.onboundary = () => {
    if (!alive()) return;
    q.spoke = true;
    q.boundaries++;
    if (q.boundaries >= 2) arm(SPEECH_WD_GAP);
  };"""
sub(OLD_NEXT_HEAD, NEW_NEXT_HEAD, 1, "speechNext 头部改成两段式")

OLD_NEXT_TAIL = """  try { if (window.speechSynthesis.paused) window.speechSynthesis.resume(); } catch (e) {}
  /* 看门狗：按本句预计时长 + 宽容量兜底，既不会误伤长句，也不会死等 */
  q.wd = setTimeout(() => speechStalled(q, idx, gen),
    Math.max(2500, speechEstimateMs(q.parts[idx]) + SPEECH_WD_SLACK));
  try { window.speechSynthesis.speak(u); }
  catch (e) { q.i++; q.timer = setTimeout(speechNext, speechSettings.gap); }
}"""
NEW_NEXT_TAIL = """  try { if (window.speechSynthesis.paused) window.speechSynthesis.resume(); } catch (e) {}
  try {
    window.speechSynthesis.speak(u);
    arm(SPEECH_WD_START);        /* 开播检测：这个时间内没出声 → 判定为哑火 */
  } catch (e) {
    q.i++;
    q.timer = setTimeout(speechNext, speechSettings.gap);
  }
}"""
sub(OLD_NEXT_TAIL, NEW_NEXT_TAIL, 1, "speechNext 尾部改成开播检测")

# ---------------------------------------------------------------- 测试钩子
sub("""    setWd: function (ms) { SPEECH_WD_SLACK = Math.max(200, Number(ms) || 0); return SPEECH_WD_SLACK; },""",
    """    setWd: function (ms, gap) {
      SPEECH_WD_SLACK = Math.max(200, Number(ms) || 0);
      if (gap != null) SPEECH_WD_GAP = Math.max(600, Number(gap) || 0);
      return { slack: SPEECH_WD_SLACK, gap: SPEECH_WD_GAP, start: SPEECH_WD_START };
    },""", 1, "setWd 支持滑窗参数")

fail = 0
for old, new, cnt, label in SUBS:
    n = html.count(old)
    if n != cnt:
        print("!! %s -> 期望 %d 处，实际 %d 处" % (label, cnt, n))
        fail += 1
        continue
    html = html.replace(old, new, cnt if cnt else -1)
    print("ok %s (%d)" % (label, n))

if fail:
    print("\n未写盘")
    raise SystemExit(1)

with io.open(SRC, "w", encoding="utf-8") as f:
    f.write(html)
print("\n已写入 index.html，长度 %d" % len(html))
