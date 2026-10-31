# -*- coding: utf-8 -*-
"""第 136 条：朗读引擎改为「轮询驱动 + 三层自愈」，并加朗读诊断面板"""
import io, sys

import os as _os
P = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "index.html")
src = io.open(P, encoding="utf-8").read()
subs = []

def sub(old, new, cnt, label):
    subs.append((old, new, cnt, label))

# ---------------------------------------------------------------- 1. 引擎主体
START = "/* ---------- 第 134 条：断链自愈（移动端）----------"
END = "function speakItem(item, keepSeq) {"

ENGINE = r"""/* ---------- 第 134 / 136 条：句级朗读引擎（轮询驱动 + 三层自愈）----------
   现象：手机端整页朗读读完第一条就停住。移动端 speechSynthesis 的老毛病是「不给回调」：
   读完不触发 onend，或者第二次 speak 直接静音且毫无回调。所以本引擎不把推进押在回调上——
   每 250ms 轮询 speechSynthesis.speaking 的真实播报状态决定本句是否读完，回调只用来提速。
   三层保护：① 轮询判定读完；② 开播检测 + 整句时长兜底；③ 上层 readSpeak 序列心跳。
   任何一层单独失守，整页朗读都不会卡死在半路。 */
const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '', pollDone: 0, tick: 0, synth: false, lastToast: 0 };
const SPEECH_TICK = 250;                 /* 轮询间隔 */
const SPEECH_QUIET = 800;                /* speaking 由 true→false 后，安静这么久判定本句读完 */
const SPEECH_START_TO = 1800;            /* 开播检测：这么久还没出声 = 哑火 */
let SPEECH_WD_SLACK = 4000;              /* 结束回调迟迟不来时的宽容量（测试可调） */
let SPEECH_WD_GAP = 3500;                /* 有发声进度时，距上一次发声事件的最大静默 */
const SPEECH_WD_START = 1600;
let speechUtterance = null;              /* 留住当前 utterance 的引用：iOS 会提前回收导致读到一半静音 */
let speechTickTimer = 0;
function speechEstimateMs(text) {
  const n = String(text || '').length;
  const cps = 5.2 * (Number(speechSettings.rate) || 1);      /* 中文大致 5 字/秒 */
  return Math.max(1200, (n / cps) * 1000);
}
function speechClearWd(q) {
  if (q && q.wd) { clearTimeout(q.wd); q.wd = null; }
}
function speechTickStart() {
  if (speechTickTimer) clearInterval(speechTickTimer);
  speechTickTimer = setInterval(speechTick, SPEECH_TICK);
}
function speechTickStop() {
  if (speechTickTimer) { clearInterval(speechTickTimer); speechTickTimer = 0; }
}
/* 轮询判定：系统有没有真的在说话，比任何回调都可靠 */
function speechTick() {
  const q = speechQueue;
  if (!q || state.speakingId !== q.id) { speechTickStop(); return; }
  if (q.awaitingStart) return;                       /* 正在等待「唤醒重读」，别重复判定 */
  speechDiag.tick++;
  const now = Date.now();
  let speaking = false;
  try { speaking = !!window.speechSynthesis.speaking; } catch (e) { speaking = false; }
  speechDiag.synth = speaking;
  const est = speechEstimateMs(q.parts[q.i] || '');
  /* 兜底：整句时长远超估算（部分机型 speaking 标志会卡死为 true）→ 判定读完 */
  if (speaking && now - q.startedAt > est + (q.deadStreak ? 2000 : SPEECH_WD_SLACK)) {
    speechDiag.wd++;
    try { window.speechSynthesis.cancel(); } catch (e) {}
    speechSentenceDone();
    return;
  }
  if (speaking) {
    q.wasSpeaking = true; q.lastSpeakAt = now; q.wdTries = 0; q.deadStreak = 0;
    return;
  }
  /* 出过声 → 安静够了就当作读完（不依赖 onend） */
  if (q.wasSpeaking) {
    if (now - q.lastSpeakAt >= SPEECH_QUIET) { speechDiag.pollDone++; speechSentenceDone(); }
    return;
  }
  /* 一直没出声：开播检测（估算时长六成 + 下限）到点就进自愈流程 */
  if (now - q.startedAt < Math.max(SPEECH_START_TO, est * 0.6)) return;
  speechStalled(q, q.i, q.gen);
}
/* 一句读完（或判定读完）→ 排下一句；同代次只推进一次，避免回调与轮询双算 */
function speechSentenceDone() {
  const q = speechQueue;
  if (!q) return;
  speechTickStop();
  const key = q.i + ':' + q.gen;
  if (q.doneToken === key) return;
  q.doneToken = key;
  try { window.speechSynthesis.cancel(); } catch (e) {}
  q.i++;
  if (q.i >= q.parts.length) { speechFinish(q.id); return; }
  q.timer = setTimeout(() => {
    q.timer = null;
    if (speechQueue === q) speechSpeakCurrent(q);
  }, Math.max(0, Number(speechSettings.gap) || 0));
}
/* 一句迟迟没有任何声音：先唤醒重读一次，还不行就丢掉这句往后走 */
function speechStalled(q, idx, gen) {
  if (speechQueue !== q || q.i !== idx || (gen != null && q.gen !== gen)) return;
  speechTickStop();
  q.awaitingStart = true;
  speechDiag.wd++;
  const tries = (q.wdTries || 0) + 1;
  q.wdTries = tries;
  const again = () => {
    if (speechQueue !== q || q.i !== idx) return;
    q.awaitingStart = false;
    speechSpeakCurrent(q);
  };
  if (tries === 1) {
    /* 多半是 iOS 把合成器挂起了：resume + cancel 之后再读一次 */
    try { window.speechSynthesis.resume(); } catch (e) {}
    try { window.speechSynthesis.cancel(); } catch (e) {}
    speechDiag.heal++;
    setTimeout(again, 320);
    return;
  }
  try { window.speechSynthesis.cancel(); } catch (e) {}
  speechDiag.giveUp++;
  q.deadStreak = (q.deadStreak || 0) + 1;    /* 连续哑火 → 后面几句的超时收紧 */
  q.wdTries = 0;
  const k2 = idx + ':' + q.gen;
  if (q.doneToken === k2) return;
  q.doneToken = k2;
  q.i++;
  setTimeout(() => { q.awaitingStart = false; if (speechQueue === q) speechSpeakCurrent(q); }, 60);
}
function speechSpeakCurrent(q) {
  if (!q || speechQueue !== q || state.speakingId !== q.id) return;
  if (q.i >= q.parts.length) { speechFinish(q.id); return; }
  const idx = q.i;
  const gen = (q.gen || 0) + 1;
  q.gen = gen;
  const text = q.parts[idx] || '';
  const u = new SpeechSynthesisUtterance(text);
  u.rate = speechSettings.rate;
  u.pitch = SPEECH_CONFIG.pitch;
  u.volume = SPEECH_CONFIG.volume;
  u.lang = SPEECH_CONFIG.lang;
  const v = q.voice || getChineseVoice();
  /* 少数浏览器对「非 getVoices() 来源的音色」赋值会抛错，不能让整句朗读崩掉 */
  if (v) { try { u.voice = v; q.voice = v; } catch (e) { q.voice = null; } }
  q.startedAt = Date.now();
  q.wasSpeaking = false;
  q.lastSpeakAt = q.startedAt;
  q.awaitingStart = false;
  q.boundaries = 0;
  q.doneToken = '';
  speechUtterance = u;                        /* 保住引用，别被移动端提前回收 */
  const alive = () => speechQueue === q && q.i === idx && q.gen === gen;
  u.onstart = () => { if (!alive()) return; q.wasSpeaking = true; q.lastSpeakAt = Date.now(); };
  u.onboundary = () => { if (!alive()) return; q.wasSpeaking = true; q.lastSpeakAt = Date.now(); q.boundaries++; };
  u.onend = () => { if (!alive()) return; speechSentenceDone(); };
  u.onerror = (ev) => {
    if (!alive()) return;
    const err = ev && ev.error;
    speechDiag.lastErr = err || '';
    if (err === 'canceled' || err === 'interrupted') return;   /* 主动停止不算失败 */
    /* 在线音色失败（多为断网）→ 换系统离线音色重读当前句 */
    if (!q.fallback && q.voice && !q.voice.localService) {
      const off = speechZhVoices().filter(x => x.localService);
      if (off.length) {
        q.fallback = true; q.voice = off[0]; q.awaitingStart = true;
        setTimeout(() => { if (speechQueue === q && q.i === idx) { q.awaitingStart = false; speechSpeakCurrent(q); } }, 150);
        return;
      }
    }
    speechSentenceDone();
  };
  /* iOS 上若合成器还留着上一条状态，第二次 speak 会静音：先干净地清一次再发 */
  try { if (window.speechSynthesis.speaking) window.speechSynthesis.cancel(); } catch (e) {}
  try { if (window.speechSynthesis.paused) window.speechSynthesis.resume(); } catch (e) {}
  try {
    window.speechSynthesis.speak(u);
    speechTickStart();
  } catch (e) {
    speechDiag.giveUp++;
    speechSentenceDone();
  }
}
function speechNext() { if (speechQueue) speechSpeakCurrent(speechQueue); }
/* ---------- 第 136 条：朗读诊断（手机上卡住时用它取证）---------- */
function speechDiagSnapshot() {
  let speaking = false, voices = 0;
  try { speaking = !!window.speechSynthesis.speaking; } catch (e) { speaking = false; }
  try { voices = speechZhVoices().length; } catch (e) { voices = -1; }
  let cur = null;
  try { const x = getChineseVoice(); cur = x ? { name: x.name, local: !!x.localService, lang: x.lang } : null; } catch (e) { cur = null; }
  return {
    ver: window.__KV__,
    ua: navigator.userAgent,
    supported: !!speechSupported,
    voices: voices,
    voice: cur,
    rate: speechSettings.rate,
    gap: speechSettings.gap,
    cloud: { on: !!(speechSettings.cloud && speechSettings.cloud.on), lastErr: (speechSettings.cloud && speechSettings.cloud.lastErr) || '' },
    mode: state.mode,
    speakingId: state.speakingId,
    synthSpeaking: speaking,
    seq: (typeof readSpeakSeq !== 'undefined' && readSpeakSeq) ? { i: readSpeakSeq.i, n: readSpeakSeq.ids.length } : null,
    queue: speechQueue ? { id: speechQueue.id, i: speechQueue.i, n: speechQueue.parts.length, startedAgo: Date.now() - (speechQueue.startedAt || 0), wasSpeaking: !!speechQueue.wasSpeaking } : null,
    tick: !!speechTickTimer,
    counters: { wd: speechDiag.wd, heal: speechDiag.heal, giveUp: speechDiag.giveUp, pollDone: speechDiag.pollDone, recover: speechDiag.recover, tickRuns: speechDiag.tick, lastErr: speechDiag.lastErr }
  };
}
function speechDiagText() {
  try { return JSON.stringify(speechDiagSnapshot(), null, 1); } catch (e) { return 'diag error: ' + e; }
}
function speechDiagCopy() {
  const txt = speechDiagText();
  let ok = false;
  try {
    const ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.cssText = 'position:fixed;left:0;top:0;width:2px;height:2px;opacity:0;';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    ok = document.execCommand('copy');
    ta.remove();
  } catch (e) { ok = false; }
  if (!ok && navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(
      () => showToast('诊断信息已复制'),
      () => showToast('复制失败，请长按下方文本手动复制', true));
  } else {
    showToast(ok ? '诊断信息已复制，可直接粘贴给我' : '复制失败，请长按下方文本手动复制', !ok);
  }
  return txt;
}
"""

i0 = src.find(START)
i1 = src.find(END)
if i0 < 0 or i1 < 0 or i1 <= i0:
    print("!! 未找到替换区", i0, i1); sys.exit(1)
old_block = src[i0:i1]
sub(old_block, ENGINE, 1, "第 136 条：轮询驱动朗读引擎")

# ---------------------------------------------------------------- 2. 停止时收口：停轮询 + 清定时器
sub("""  /* 第 129 条：分句朗读是排队推进的，停止时要把待播定时器一并清掉 */
  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  if (speechQueue && speechQueue.wd) { clearTimeout(speechQueue.wd); speechQueue.wd = null; }
  speechQueue = null;""",
"""  /* 第 129 条：分句朗读是排队推进的，停止时要把待播定时器一并清掉 */
  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  if (speechQueue && speechQueue.wd) { clearTimeout(speechQueue.wd); speechQueue.wd = null; }
  /* 第 136 条：轮询驱动器与 utterance 引用一并收口，避免停止后仍有后台推进 */
  if (typeof speechTickStop === 'function') speechTickStop();
  speechUtterance = null;
  speechQueue = null;""",
1, "stopSpeaking 收口轮询")

# ---------------------------------------------------------------- 3. speechFinish 清轮询
sub("""function speechFinish(id) {
  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  if (speechQueue && speechQueue.wd) { clearTimeout(speechQueue.wd); speechQueue.wd = null; }""",
"""function speechFinish(id) {
  if (speechQueue && speechQueue.timer) { clearTimeout(speechQueue.timer); speechQueue.timer = null; }
  if (speechQueue && speechQueue.wd) { clearTimeout(speechQueue.wd); speechQueue.wd = null; }
  if (typeof speechTickStop === 'function') speechTickStop();""",
1, "speechFinish 清轮询")

# ---------------------------------------------------------------- 4. speakItem 初始化新字段
sub("""  speechQueue = { id: item.id, parts: parts, i: 0, timer: null, voice: null, fallback: false };
  speechNext();""",
"""  speechQueue = {
    id: item.id, parts: parts, i: 0, gen: 0, timer: null, voice: null, fallback: false,
    startedAt: Date.now(), wasSpeaking: false, lastSpeakAt: Date.now(), doneToken: ''
  };
  speechSpeakCurrent(speechQueue);""",
1, "speakItem 建队字段")

# ---------------------------------------------------------------- 5. 设置面板加诊断行
sub("""    <div class="rs-hint">阅读模式是整页朗读：顶栏「朗读本页」从当前位置一路读到本页最后一条，边读边自动滚动；浮条上可跳过当前条或停止。</div>""",
"""    <div class="rs-row">
      <div class="rs-label">朗读诊断</div>
      <div class="rs-opts"><button type="button" class="rs-opt" id="speakDiagBtn">查看并复制诊断信息</button></div>
      <div class="rs-hint" id="speakDiagHint">手机上整页朗读卡住时点这里，把结果发给我就能定位</div>
    </div>
    <div class="rs-hint">阅读模式是整页朗读：顶栏「朗读本页」从当前位置一路读到本页最后一条，边读边自动滚动；浮条上可跳过当前条或停止。</div>""",
1, "朗读设置面板加诊断行")

fail = 0
for old, new, cnt, label in subs:
    n = src.count(old)
    if n != cnt:
        print("!! %s: 期望 %d 处，实际 %d 处" % (label, cnt, n)); fail += 1; continue
    src = src.replace(old, new, cnt)
    print("ok  " + label)

if fail:
    sys.exit(1)

# ---------------------------------------------------------------- 6. 绑定诊断按钮
if "function bindSpeechSettings() {" in src:
    insert_at = src.find("{", src.find("function bindSpeechSettings()")) + 1
    bind = """
  const diagBtn = document.getElementById('speakDiagBtn');
  if (diagBtn) diagBtn.addEventListener('click', () => {
    const txt = speechDiagCopy();
    const hint = document.getElementById('speakDiagHint');
    if (hint) {
      hint.textContent = txt;
      hint.style.maxHeight = '200px';
      hint.style.overflow = 'auto';
      hint.style.whiteSpace = 'pre-wrap';
      hint.style.fontSize = '11px';
    }
  });"""
    src = src[:insert_at] + bind + src[insert_at:]
    print("ok  绑定诊断按钮")
else:
    print("!! 未定位 bindSpeechSettings"); sys.exit(1)

io.open(P, "w", encoding="utf-8").write(src)
print("written")
