# -*- coding: utf-8 -*-
"""第 134 条：整页朗读在移动端的断链修复
移动端（尤其 iOS Safari）常见三类卡死：
  1) 句子读完后不回调 onend → 队列不再推进；
  2) 第二次 speak 静音（合成器被系统挂起）→ 听不到声音也不回调；
  3) 上面两种情况叠加 → 整页朗读死在第一条。
本补丁给每一句加「看门狗 + 一次自愈」，再给整页序列加心跳保活，并在自愈时给出可见提示。
"""
import io
import os
import re

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
SRC = os.path.join(BASE, "index.html")

with io.open(SRC, "r", encoding="utf-8") as f:
    html = f.read()

SUBS = []
REGIONS = []


def sub(old, new, cnt=1, label=""):
    SUBS.append([old, new, cnt, label])


# ---------------------------------------------------------------- 1. 版本号
sub("window.__KV__='2026-10-30c';", "window.__KV__='2026-10-31a';", 1, "版本号 head")
sub("window.__KV__ = '2026-10-30c';", "window.__KV__ = '2026-10-31a';", 1, "版本号 script")

# ---------------------------------------------------------------- 2. speechFinish 收掉看门狗
sub("""function speechFinish(id) {
  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  speechQueue = null;""",
    """function speechFinish(id) {
  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  if (speechQueue && speechQueue.wd) { clearTimeout(speechQueue.wd); speechQueue.wd = null; }
  speechQueue = null;""", 1, "speechFinish 清看门狗")

# stopSpeaking 同样要收掉，否则卡住的定时器会在停止后把句子再推一遍
sub("""  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  speechQueue = null;
  /* 第 131 条：云端队列与音频元素也要停 */""",
    """  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  if (speechQueue && speechQueue.wd) { clearTimeout(speechQueue.wd); speechQueue.wd = null; }
  speechQueue = null;
  /* 第 131 条：云端队列与音频元素也要停 */""", 1, "stopSpeaking 清看门狗")

# ---------------------------------------------------------------- 3. 重写 speechNext
OLD_NEXT = """function speechNext() {
  const q = speechQueue;
  if (!q || state.speakingId !== q.id) return;
  if (q.i >= q.parts.length) { speechFinish(q.id); return; }
  const u = new SpeechSynthesisUtterance(q.parts[q.i]);
  u.rate = speechSettings.rate;
  u.pitch = SPEECH_CONFIG.pitch;
  u.volume = SPEECH_CONFIG.volume;
  u.lang = SPEECH_CONFIG.lang;
  const v = getChineseVoice();
  /* 少数浏览器对「非 getVoices() 来源的音色」赋值会抛错，不能让整句朗读崩掉 */
  if (v) { try { u.voice = v; q.voice = v; } catch (e) { q.voice = null; } }
  u.onend = () => {
    if (speechQueue !== q) return;
    q.i++;
    q.timer = setTimeout(speechNext, speechSettings.gap);   /* 句间停顿 */
  };
  u.onerror = (ev) => {
    const err = ev && ev.error;
    if (err === 'canceled' || err === 'interrupted') return;  /* 主动停止不算失败 */
    if (speechQueue !== q) return;
    /* 在线音色失败（多为断网）→ 换系统离线音色重读当前句 */
    if (!q.fallback && q.voice && !q.voice.localService) {
      const off = speechZhVoices().filter(x => x.localService);
      if (off.length) { q.fallback = true; q.voice = off[0]; q.timer = setTimeout(speechNext, 150); return; }
    }
    q.i++;
    q.timer = setTimeout(speechNext, speechSettings.gap);
  };
  try { window.speechSynthesis.speak(u); }
  catch (e) { q.i++; q.timer = setTimeout(speechNext, speechSettings.gap); }
}"""

NEW_NEXT = """/* ---------- 第 134 条：断链自愈（移动端）----------
   现象：整页朗读在手机读到第一条就停住。根因不是游标逻辑，而是系统的 speechSynthesis 在移动端
   经常不给回调（读完不触发 onend）或者第二次 speak 静音。这里给每一句加超时看门狗：
   超时 → 先 resume + 重读本句一次；再超时 → 放弃本句往后走，绝不让整页朗读死在半路。 */
const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '' };
let SPEECH_WD_SLACK = 7000;                 /* 句预计时长之外再给的宽容量（测试可调） */
function speechEstimateMs(text) {
  const n = String(text || '').length;
  const cps = 5.2 * (Number(speechSettings.rate) || 1);      /* 中文大致 5 字/秒 */
  return Math.max(1200, (n / cps) * 1000);
}
function speechClearWd(q) {
  if (q && q.wd) { clearTimeout(q.wd); q.wd = null; }
}
/* 一句迟迟没有结果：先试着唤醒合成器重读，仍无反应就跳过这一句 */
function speechStalled(q, idx, gen) {
  if (speechQueue !== q || q.i !== idx || (gen != null && q.gen !== gen)) return;
  q.wd = null;
  speechDiag.wd++;
  const tries = (q.wdTries || 0) + 1;
  q.wdTries = tries;
  if (!q.spoke && tries === 1) {
    /* 压根没出声：多半是 iOS 把合成器挂起了，唤醒后重读这一句 */
    try { window.speechSynthesis.resume(); } catch (e) {}
    try { window.speechSynthesis.cancel(); } catch (e) {}
    speechDiag.heal++;
    q.timer = setTimeout(() => { if (speechQueue === q && q.i === idx) speechNext(); }, 320);
    return;
  }
  /* 出过声却没给结束回调（或唤醒后依旧没声）：丢掉这一句往后走，别停在半路 */
  try { window.speechSynthesis.cancel(); } catch (e) {}
  speechDiag.giveUp++;
  q.wdTries = 0;
  q.i++;
  q.timer = setTimeout(() => { if (speechQueue === q) speechNext(); }, 60);
}
function speechNext() {
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
  u.onboundary = () => { if (alive()) q.spoke = true; };
  u.onend = settle(() => {
    q.i++;
    q.timer = setTimeout(speechNext, speechSettings.gap);   /* 句间停顿 */
  });
  u.onerror = settle((ev) => {
    const err = ev && ev.error;
    if (err === 'canceled' || err === 'interrupted') return;  /* 主动停止不算失败 */
    /* 在线音色失败（多为断网）→ 换系统离线音色重读当前句 */
    if (!q.fallback && q.voice && !q.voice.localService) {
      const off = speechZhVoices().filter(x => x.localService);
      if (off.length) { q.fallback = true; q.voice = off[0]; q.timer = setTimeout(speechNext, 150); return; }
    }
    q.i++;
    q.timer = setTimeout(speechNext, speechSettings.gap);
  });
  try { if (window.speechSynthesis.paused) window.speechSynthesis.resume(); } catch (e) {}
  /* 看门狗：按本句预计时长 + 宽容量兜底，既不会误伤长句，也不会死等 */
  q.wd = setTimeout(() => speechStalled(q, idx, gen),
    Math.max(2500, speechEstimateMs(q.parts[idx]) + SPEECH_WD_SLACK));
  try { window.speechSynthesis.speak(u); }
  catch (e) { q.i++; q.timer = setTimeout(speechNext, speechSettings.gap); }
}"""

REGIONS.append([
    "function speechNext() {",
    "function speakItem(item, keepSeq) {",
    NEW_NEXT + "\n",
    "speechNext 重写（看门狗）",
])

# ---------------------------------------------------------------- 4. 整页序列心跳保活
sub("""  readSpeakSeq = { ids: ids, i: Math.min(i, ids.length - 1) };
  readSpeakPlay();
}""",
    """  readSpeakSeq = { ids: ids, i: Math.min(i, ids.length - 1) };
  readSpeakHeartStart();
  readSpeakPlay();
}
/* 心跳：整页朗读期间，如果连续 6 秒既没在说话、也没有待播任务，说明这条被系统吞了，跳到下一条 */
var readSpeakHeart = 0;
var readSpeakQuietSince = 0;
function readSpeakHeartStart() {
  if (readSpeakHeart) return;
  readSpeakQuietSince = Date.now();
  readSpeakHeart = setInterval(readSpeakHeartBeat, 1200);
}
function readSpeakHeartStop() {
  if (readSpeakHeart) { clearInterval(readSpeakHeart); readSpeakHeart = 0; }
}
function readSpeakHeartBeat() {
  const q = readSpeakSeq;
  if (!q || state.mode !== 'read') { readSpeakHeartStop(); return; }
  const busy = !!state.speakingId || !!speechQueue || !!readSpeakTimer || !!cloudQueue;
  if (busy) { readSpeakQuietSince = Date.now(); return; }
  if (Date.now() - readSpeakQuietSince < 6000) return;
  readSpeakQuietSince = Date.now();
  speechDiag.recover++;
  showToast('\\u6717\\u8bfb\\u88ab\\u7cfb\\u7edf\\u6253\\u65ad\\uff0c\\u6b63\\u5728\\u7ee7\\u7eed');
  readSpeakSkip();
}""", 1, "整页朗读心跳保活")

sub("""function readSpeakStop() {
  readSpeakSeq = null;
  if (readSpeakTimer) { clearTimeout(readSpeakTimer); readSpeakTimer = 0; }
  readSpeakUi();
}""",
    """function readSpeakStop() {
  readSpeakSeq = null;
  if (readSpeakTimer) { clearTimeout(readSpeakTimer); readSpeakTimer = 0; }
  readSpeakHeartStop();
  readSpeakUi();
}""", 1, "停止时收心跳")

# ---------------------------------------------------------------- 5. 测试钩子
sub("""    readSkip: function () { try { readSpeakSkip(); return readSpeakSeq ? readSpeakSeq.i : -1; } catch (e) { return -1; } },""",
    """    readSkip: function () { try { readSpeakSkip(); return readSpeakSeq ? readSpeakSeq.i : -1; } catch (e) { return -1; } },
    /* 第 134 条：断链自愈诊断 */
    diag: function () {
      try {
        return {
          wd: speechDiag.wd, heal: speechDiag.heal, giveUp: speechDiag.giveUp,
          recover: speechDiag.recover, lastErr: speechDiag.lastErr,
          queue: speechQueue ? { id: speechQueue.id, n: speechQueue.parts.length, i: speechQueue.i, tries: speechQueue.wdTries || 0 } : null,
          seq: readSpeakSeq ? { i: readSpeakSeq.i, n: readSpeakSeq.ids.length } : null,
          heart: !!readSpeakHeart
        };
      } catch (e) { return { err: String(e) }; }
    },
    setWd: function (ms) { SPEECH_WD_SLACK = Math.max(200, Number(ms) || 0); return SPEECH_WD_SLACK; },""",
    1, "新增 diag / setWd 钩子")

# ---------------------------------------------------------------- 执行
fail = 0
for start, end, newtext, label in REGIONS:
    pat = re.escape(start) + r"[\s\S]*?(?=" + re.escape(end) + ")"
    html, n = re.subn(pat, lambda m: newtext, html, count=1)
    if n != 1:
        print("!! %s -> 区域替换失败" % label)
        fail += 1
    else:
        print("ok %s" % label)

for old, new, cnt, label in SUBS:
    n = html.count(old)
    if n != cnt:
        print("!! %s -> 期望 %d 处，实际 %d 处" % (label, cnt, n))
        fail += 1
        continue
    html = html.replace(old, new, cnt if cnt else -1)
    print("ok %s (%d)" % (label, n))

if fail:
    print("\n共 %d 处未命中，未写盘" % fail)
    raise SystemExit(1)

with io.open(SRC, "w", encoding="utf-8") as f:
    f.write(html)
print("\n已写入 index.html，长度 %d" % len(html))
