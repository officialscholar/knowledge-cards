# -*- coding: utf-8 -*-
"""第 139 条：整页朗读引擎重构（以整条知识点为播放原子）"""
import io

import os as _os
P = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "index.html")
s = io.open(P, encoding="utf-8").read()
n = 0


def region_replace(a, b, new, label):
    global s, n
    i = s.find(a)
    assert i >= 0, "anchor A not found: " + label
    j = s.find(b, i + len(a))
    assert j > i, "anchor B not found: " + label
    s = s[:i] + new + s[j:]
    n += 1
    print("ok  " + label)


def one(old, new, label, cnt=1):
    global s, n
    c = s.count(old)
    assert c == cnt, "FAIL %s expect %d got %d" % (label, cnt, c)
    s = s.replace(old, new, cnt)
    n += 1
    print("ok  " + label)


# ============================================================ 1. 播放层 + 序列头（Begin..Play）
NEW_HEAD = r'''/* ============================================================
   第 139 条：整页朗读播放层（以「整条知识点」为播放原子）
   ------------------------------------------------------------
   旧实现把一条知识点切成十几句（110 字/句），每句一次 speak 或一次云端请求，
   任何一次失败就断；推进又依赖 speaking 标志 + 550ms 安静窗口，句首停顿会被
   误判成「读完」，于是出现「跳过部分内容」。
   本层把原子放大到「整条」：
   · 云端：整条一次合成 → 一个 mp3 → 一个 <audio>，条内天然无缝，还能预取下一条；
   · 系统音色：整条一次 utter（移动端按 220 字切 1~2 段），起飞次数从十几次降到 1 次；
   · 推进只用可靠信号：onend / audio.ended / 「确实出过声之后 speaking 变 false」；
   · 队列内绝不 cancel（iOS 上 cancel 后合成器会永久哑掉），只有停止与跳过才 cancel。
   ============================================================ */
var readPlay = { id: null, token: 0, mode: '', startedAt: 0, limitMs: 0, timer: 0, poll: 0, heard: false, miss: 0 };
let READ_IDLE_TO = 8000;     /* 从未出声：多久放弃这一条，别让整页干等（测试可调） */
let READ_TAIL_MUL = 1.8;     /* 出过声后：兜底 = 估算时长 × 倍率 + 余量 */
let READ_TAIL_ADD = 5000;
const READ_POLL = 400;       /* 出声结束后多久确认「真的读完了」 */

/* 停止当前条的播放：只有这里和用户停止才 cancel */
function readPlayStop() {
  readPlay.token++;
  if (readPlay.timer) { clearTimeout(readPlay.timer); readPlay.timer = 0; }
  if (readPlay.poll) { clearInterval(readPlay.poll); readPlay.poll = 0; }
  readPlay.id = null;
  readPlay.limitMs = 0;
  readPlay.heard = false;
  try { if (typeof cloudStopQueue === 'function') cloudStopQueue(); } catch (e) {}
  if (speechSupported) { try { window.speechSynthesis.cancel(); } catch (e) {} }
  if (speechQueue) { if (speechQueue.timer) clearTimeout(speechQueue.timer); speechQueue = null; }
  if (typeof speechTickStop === 'function') speechTickStop();
  speechUtterance = null;
}

/* 整页朗读的音色：优先本地音色。在线音色每句都要取流，是「长时间没声音」的主因 */
function readPlayVoice() {
  try {
    const local = speechZhVoices().filter(v => v.localService);
    if (local.length) {
      local.sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a));
      return local[0];
    }
  } catch (e) {}
  try { return getChineseVoice(); } catch (e) { return null; }
}

/* 切段：桌面整条一次读；移动端单条 utter 过长会被系统截断，按 220 字聚合成 1~2 段 */
function readPlaySegments(text) {
  const t = String(text || '');
  if (!t) return [];
  const mobile = /iPhone|iPad|iPod|Android|Mobile/i.test(navigator.userAgent || '');
  const lim = mobile ? 220 : 900;
  if (t.length <= lim) return [t];
  const out = [];
  let buf = '';
  speechSplitKeep(t, '\u3002\uff01\uff1f!?\uff1b;\n').forEach(seg => {
    if (buf && (buf + seg).length > lim) { out.push(buf); buf = seg; }
    else buf += seg;
  });
  if (buf) out.push(buf);
  return out;
}

function readPlayDone(id, token) {
  if (token !== readPlay.token) return;
  if (readPlay.timer) { clearTimeout(readPlay.timer); readPlay.timer = 0; }
  if (readPlay.poll) { clearInterval(readPlay.poll); readPlay.poll = 0; }
  const heard = readPlay.heard;
  readPlay.id = null;
  readPlay.limitMs = 0;
  if (!heard) {
    /* 这一条从头到尾没有任何发声迹象：记一次「被系统吞掉」 */
    readPlay.miss++;
    speechDiag.deadItems = readPlay.miss;
    speechLog('dead', 'item');
    if (readPlay.miss >= 2) {
      readPlay.miss = 0;
      if (typeof readSpeakAskTap === 'function' && readSpeakAskTap()) return;
    }
  } else {
    readPlay.miss = 0;
    speechDiag.deadItems = 0;
  }
  readSpeakAdvance(id);
}

/* ---- 系统音色：整条一次 utter（移动端 1~2 段） ---- */
function readPlaySystem(item, token) {
  readPlay.mode = 'system';
  const segs = readPlaySegments(typeof readSpeakText === 'function' ? readSpeakText(item) : '');
  if (!segs.length) { readPlayDone(item.id, token); return; }
  const voice = readPlayVoice();
  const q = { wasSpeaking: false, quiet: 0 };
  let si = 0;
  const clearAll = () => {
    if (readPlay.timer) { clearTimeout(readPlay.timer); readPlay.timer = 0; }
    if (readPlay.poll) { clearInterval(readPlay.poll); readPlay.poll = 0; }
  };
  const step = () => {
    if (token !== readPlay.token) return;
    if (si >= segs.length) { readPlayDone(item.id, token); return; }
    const seg = segs[si];
    const est = speechEstimateMs(seg);
    q.wasSpeaking = false;
    q.quiet = 0;
    readPlay.startedAt = Date.now();
    const u = new SpeechSynthesisUtterance(seg);
    u.rate = speechSettings.rate;
    u.pitch = SPEECH_CONFIG.pitch;
    u.volume = SPEECH_CONFIG.volume;
    u.lang = SPEECH_CONFIG.lang;
    if (voice) { try { u.voice = voice; } catch (e) {} }
    speechUtterance = u;
    let ended = false;
    const finishSeg = () => {
      if (ended) return;
      ended = true;
      clearAll();
      if (token !== readPlay.token) return;
      si++;
      step();
    };
    /* 出过声后按估算时长放宽兜底；从未出声则用较短的放弃时间（等下去毫无意义） */
    const arm = (ms) => {
      if (readPlay.timer) clearTimeout(readPlay.timer);
      readPlay.limitMs = ms;
      readPlay.timer = setTimeout(() => {
        readPlay.timer = 0;
        if (token !== readPlay.token) return;
        speechDiag.wd++;
        speechLog('timeout', q.wasSpeaking ? 'tail' : 'idle');
        try { window.speechSynthesis.cancel(); } catch (e) {}
        finishSeg();
      }, ms);
    };
    arm(READ_IDLE_TO);
    u.onstart = () => {
      if (token !== readPlay.token) return;
      readPlay.heard = true;
      q.wasSpeaking = true;
      arm(Math.round(est * READ_TAIL_MUL) + READ_TAIL_ADD);
    };
    u.onboundary = () => {
      if (token !== readPlay.token) return;
      readPlay.heard = true;
      q.wasSpeaking = true;
    };
    u.onend = () => {
      if (token !== readPlay.token) return;
      readPlay.heard = true;
      speechLog('end', 'item');
      finishSeg();
    };
    u.onerror = (ev) => {
      if (token !== readPlay.token) return;
      const err = ev && ev.error;
      speechDiag.lastErr = err || '';
      if (err === 'canceled' || err === 'interrupted') return;
      speechLog('err', err || '');
      finishSeg();
    };
    try { window.speechSynthesis.speak(u); }
    catch (e) { finishSeg(); return; }
    /* 轮询确认：真出过声、且 speaking 已经变 false 并持续 READ_POLL×2 → 本条读完。
       （iOS 常常不给 onend，但 speaking 是准的；这里不会误杀句首停顿，因为只在
        确实发过声之后才开始判定「结束」。） */
    if (readPlay.poll) clearInterval(readPlay.poll);
    readPlay.poll = setInterval(() => {
      if (token !== readPlay.token) { clearInterval(readPlay.poll); readPlay.poll = 0; return; }
      let spk = false;
      try { spk = !!window.speechSynthesis.speaking; } catch (e) { spk = false; }
      if (spk) { q.wasSpeaking = true; q.quiet = 0; return; }
      if (!q.wasSpeaking) return;
      q.quiet++;
      if (q.quiet >= 2) { speechDiag.pollDone++; finishSeg(); }
    }, READ_POLL);
  };
  step();
}

/* ---- 云端：整条一次合成 + 单个 audio 播放（条内零接缝） ---- */
function readPlayAudio(buf, token) {
  return new Promise((resolve, reject) => {
    const a = getTtsAudio();
    let url = null, wd = 0, done = false, lastT = -1, stall = 0;
    try { url = URL.createObjectURL(new Blob([buf], { type: 'audio/mpeg' })); }
    catch (e) { reject(e); return; }
    const cleanup = (err) => {
      if (done) return;
      done = true;
      if (wd) { clearInterval(wd); wd = 0; }
      a.onended = null; a.onerror = null; a.ontimeupdate = null;
      try { URL.revokeObjectURL(url); } catch (e) {}
      if (err) reject(err); else resolve();
    };
    a.onended = () => cleanup(null);
    a.onerror = () => cleanup(new Error('audio error'));
    a.ontimeupdate = () => {
      if (a.currentTime > lastT + 0.02) { lastT = a.currentTime; stall = 0; readPlay.heard = true; }
    };
    a.src = url;
    try {
      const p = a.play();
      if (p && p.catch) p.catch((err) => cleanup(err));
    } catch (e) { cleanup(e); return; }
    wd = setInterval(() => {
      if (done) return;
      if (token !== readPlay.token) { cleanup(new Error('stopped')); return; }
      if (a.paused && !a.ended) {
        stall++;
        if (stall >= 4) cleanup(new Error('audio stalled'));
      } else { stall = 0; }
    }, 700);
  });
}

async function readPlayCloud(item, token) {
  readPlay.mode = 'cloud';
  readPlay.startedAt = Date.now();
  readPlay.limitMs = 30000;                     /* 合成 + 播放的整体上限，心跳据此接管 */
  const text = typeof readSpeakText === 'function' ? readSpeakText(item) : '';
  let buf = null;
  try { buf = await cloudTtsBuffer(text); }
  catch (err) {
    if (token !== readPlay.token) return;
    speechDiag.lastErr = 'cloud:' + ((err && err.status) || '');
    try { if (typeof cloudTtsErrText === 'function') showToast(cloudTtsErrText(err), true); } catch (e) {}
    readPlaySystem(item, token);                 /* 同一条改用系统音色，token 不变 */
    return;
  }
  if (token !== readPlay.token) return;
  readPlay.startedAt = Date.now();
  try { await readPlayAudio(buf, token); }
  catch (err) {
    if (token !== readPlay.token) return;
    speechDiag.lastErr = 'audio:' + (err && err.message);
    readPlaySystem(item, token);
    return;
  }
  if (token !== readPlay.token) return;
  readPlay.heard = true;
  readPlayDone(item.id, token);
}

function readPlayItem(item) {
  if (!item) return;
  readPlay.token++;
  const token = readPlay.token;
  readPlay.id = item.id;
  readPlay.heard = false;
  readPlay.miss = 0;
  let cloud = false;
  try { cloud = !!cloudTtsReady(); } catch (e) { cloud = false; }
  if (cloud) {
    try { cloudUnlockAudio(); } catch (e) {}
    readPlayCloud(item, token);
  } else {
    readPlaySystem(item, token);
  }
  /* 预取下一条：云端合成有 1~2 秒延迟，提前做好就能做到条间零空档 */
  const q = readSpeakSeq;
  if (cloud && q && typeof cloudPrefetch === 'function') {
    const nx = state.items.find(x => x.id === q.ids[q.i + 1]);
    if (nx) { try { cloudPrefetch(readSpeakText(nx)); } catch (e) {} }
  }
}

function readSpeakBegin(id) {
  const ids = readSpeakIds();
  if (!ids.length) { showToast('\u8fd9\u4e00\u9875\u8fd8\u6ca1\u6709\u53ef\u6717\u8bfb\u7684\u5185\u5bb9', true); return; }
  let i = 0;
  if (id) { const k = ids.indexOf(id); i = k >= 0 ? k : 0; }
  else i = readSpeakStartIndex(ids);
  readSpeakNeedTap = false;
  speechDiag.deadItems = 0;
  speechDiag.taps = 0;
  readPlay.miss = 0;
  readSpeakSeq = { ids: ids, i: Math.min(i, ids.length - 1) };
  readSpeakHeartStart();
  readSpeakPlay();
}
/* 从 from 起往后找第一条有内容的，找到就把游标挪过去 */
function readSpeakSeek(from) {
  const q = readSpeakSeq;
  if (!q) return false;
  for (let k = Math.max(0, from); k < q.ids.length; k++) {
    const it = state.items.find(x => x.id === q.ids[k]);
    if (it && readSpeakText(it)) { q.i = k; return true; }
  }
  return false;
}
/* 起点：默认用视口里第一条知识点，让人接着眼前的位置听 */
function readSpeakStartIndex(ids) {
  const sc = el.contentArea.querySelector('.read-scroll');
  if (!sc) return 0;
  const top = sc.getBoundingClientRect().top;
  for (let k = 0; k < ids.length; k++) {
    const node = el.contentArea.querySelector('.read-item[data-read-item="' + ids[k] + '"]');
    if (!node) continue;
    if (node.getBoundingClientRect().bottom - top > 48) return k;
  }
  return 0;
}
/* 心跳：播放层自己就有兜底，这里只处理「异步链整体失联」的极端情况 */
var readSpeakHeart = 0;
var readSpeakQuietSince = 0;
function readSpeakHeartStart() {
  if (readSpeakHeart) return;
  readSpeakQuietSince = Date.now();
  readSpeakHeart = setInterval(readSpeakHeartBeat, 1500);
}
function readSpeakHeartStop() {
  if (readSpeakHeart) { clearInterval(readSpeakHeart); readSpeakHeart = 0; }
}
function readSpeakHeartBeat() {
  const q = readSpeakSeq;
  if (!q || state.mode !== 'read') { readSpeakHeartStop(); return; }
  if (!readPlay.id) return;                       /* 条间停顿中，正常 */
  const limit = (readPlay.limitMs || 15000) + 12000;
  if (Date.now() - readPlay.startedAt < limit) return;
  speechDiag.recover++;
  speechLog('heart', 'stuck');
  readPlayStop();
  state.speakingId = null;
  q.i++;
  readSpeakPlay();
}
'''

region_replace("function readSpeakBegin(id) {", "function readSpeakPlay() {", NEW_HEAD,
               "readSpeakBegin..readSpeakPlay 整体替换（含播放层与心跳）")

# ============================================================ 2. readSpeakPlay
NEW_PLAY = r'''function readSpeakPlay() {
  const q = readSpeakSeq;
  if (!q) return;
  if (state.mode !== 'read') { readSpeakStop(); return; }
  if (!readSpeakSeek(q.i)) { readSpeakStop(); showToast('\u672c\u9875\u5df2\u8bfb\u5b8c'); return; }
  const id = q.ids[q.i];
  const item = state.items.find(x => x.id === id);
  if (!item) { q.i++; readSpeakPlay(); return; }
  state.speakingId = id;
  readSpeakScrollTo(id);
  readSpeakUi();                    /* 先出界面：点下去立刻看到反馈，再发声 */
  readPlayItem(item);
}
'''
region_replace("function readSpeakPlay() {", "function readSpeakSkip() {", NEW_PLAY, "readSpeakPlay 替换")

# ============================================================ 3. readSpeakSkip
NEW_SKIP = r'''function readSpeakSkip() {
  const q = readSpeakSeq;
  if (!q) return;
  readSpeakNeedTap = false;
  if (readSpeakTimer) { clearTimeout(readSpeakTimer); readSpeakTimer = 0; }
  readPlayStop();                   /* 立刻掐断当前条 */
  if (readSpeakSeq !== q) return;
  state.speakingId = null;
  q.i++;
  if (q.i >= q.ids.length) { readSpeakStop(); showToast('\u672c\u9875\u5df2\u8bfb\u5b8c'); return; }
  readSpeakUi();                    /* 浮条立刻显示下一条 —— 点击必有反应 */
  /* 让出 150ms 再发下一条：Chrome / iOS 在 cancel 之后立刻 speak 会吞掉新语句 */
  readSpeakTimer = setTimeout(() => {
    readSpeakTimer = 0;
    if (readSpeakSeq !== q) return;
    readSpeakPlay();
  }, 150);
}
'''
region_replace("function readSpeakSkip() {", "function readSpeakStop() {", NEW_SKIP, "readSpeakSkip 替换")

# ============================================================ 4. readSpeakStop
NEW_STOP = r'''function readSpeakStop() {
  readSpeakSeq = null;
  readSpeakNeedTap = false;
  state.speakingId = null;
  if (readSpeakTimer) { clearTimeout(readSpeakTimer); readSpeakTimer = 0; }
  readSpeakHeartStop();
  readPlayStop();
  readSpeakUi();
}
'''
region_replace("function readSpeakStop() {", "function readSpeakScrollTo(id) {", NEW_STOP, "readSpeakStop 替换")

# ============================================================ 5. readSpeakAdvance（条间停很短）
NEW_ADV = r'''function readSpeakAdvance(id) {
  const q = readSpeakSeq;
  if (!q || !id || q.ids[q.i] !== id) return;
  if (readSpeakTimer) clearTimeout(readSpeakTimer);
  /* 整条已经是一次连续播放，条与条之间只需要很短的换气 */
  const wait = Math.round(Math.max(140, (Number(speechSettings.gap) || 0) * 0.4));
  readSpeakTimer = setTimeout(() => {
    readSpeakTimer = 0;
    if (readSpeakSeq !== q) return;
    q.i++;
    readSpeakPlay();
  }, wait);
}
'''
region_replace("function readSpeakAdvance(id) {",
               "/* 第 137 条：系统连续拒绝发声时向用户要一次真实点击手势",
               NEW_ADV, "readSpeakAdvance 替换")

# ============================================================ 6. stopSpeaking 收口播放层
one("""  /* 第 131 条：云端队列与音频元素也要停 */
  if (typeof cloudStopQueue === 'function') cloudStopQueue();""",
    """  /* 第 131 条：云端队列与音频元素也要停 */
  if (typeof cloudStopQueue === 'function') cloudStopQueue();
  /* 第 139 条：整页朗读的播放层（audio / 整条 utter / 兜底定时器）一并收口 */
  if (typeof readPlayStop === 'function') readPlayStop();""",
    "stopSpeaking 调用 readPlayStop")

# ============================================================ 7. readSpeakUi：准备中提示
one("""    if (readSpeakNeedTap) {
      txt.textContent = '\u7cfb\u7edf\u6682\u505c\u4e86\u81ea\u52a8\u7eed\u8bfb';
    } else {""",
    """    if (readSpeakNeedTap) {
      txt.textContent = '\u7cfb\u7edf\u5df2\u6682\u505c\uff0c\u70b9\u300c\u7ee7\u7eed\u6717\u8bfb\u300d\u63a5\u7740\u8bfb';
    } else if (readPlay.id && readPlay.mode === 'cloud' && !readPlay.heard) {
      txt.textContent = '\u6b63\u5728\u51c6\u5907\u8bed\u97f3\u2026';
    } else {""",
    "readSpeakUi 准备中提示")

# ============================================================ 8. 浮条 CSS 加固
one(""".read-speak-bar {
  position: fixed; left: 18px; bottom: 18px; z-index: 96;
  display: flex; align-items: center; gap: 10px;""",
    """.read-speak-bar {
  position: fixed; left: 18px; bottom: 18px; z-index: 300;
  display: flex; align-items: center; gap: 10px;
  pointer-events: auto; touch-action: manipulation;""",
    "浮条 z-index / pointer-events")

one(""".read-speak-bar .rsb-btn {
  flex: 0 0 auto; border: 1px solid var(--border); background: var(--bg-accent);""",
    """.read-speak-bar .rsb-btn {
  flex: 0 0 auto; border: 1px solid var(--border); background: var(--bg-accent);
  touch-action: manipulation; -webkit-tap-highlight-color: transparent;""",
    "浮条按钮触摸优化")

# ============================================================ 9. 浮条按钮改用 pointerdown（移动端更可靠）
one("""  const rsbNext = document.getElementById('readSpeakNext');
  if (rsbNext) rsbNext.addEventListener('click', (e) => { e.stopPropagation(); readSpeakSkip(); });
  const rsbResume = document.getElementById('readSpeakResume');
  if (rsbResume) rsbResume.addEventListener('click', (e) => { e.stopPropagation(); readSpeakResume(); });
  const rsbStop = document.getElementById('readSpeakStop');
  if (rsbStop) rsbStop.addEventListener('click', (e) => { e.stopPropagation(); stopSpeaking(); });""",
    """  /* 第 139 条：移动端用 pointerdown 直接响应（滚动容器里 click 偶尔会被吃掉） */
  const rsbTap = (node, fn) => {
    if (!node) return;
    const fire = (e) => {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      try { fn(); } catch (err) { showToast('\u64cd\u4f5c\u5931\u8d25\uff1a' + err.message, true); }
    };
    if ('onpointerdown' in window) {
      node.addEventListener('pointerdown', fire);
      node.addEventListener('click', (e) => e.stopPropagation());
    } else {
      node.addEventListener('click', fire);
    }
  };
  rsbTap(document.getElementById('readSpeakNext'), () => readSpeakSkip());
  rsbTap(document.getElementById('readSpeakResume'), () => readSpeakResume());
  rsbTap(document.getElementById('readSpeakStop'), () => stopSpeaking());""",
    "浮条按钮 pointerdown 绑定")

# ============================================================ 10. 诊断快照补播放层
one("""    needTap: (typeof readSpeakNeedTap !== 'undefined') ? !!readSpeakNeedTap : false,""",
    """    needTap: (typeof readSpeakNeedTap !== 'undefined') ? !!readSpeakNeedTap : false,
    play: (typeof readPlay !== 'undefined') ? { id: readPlay.id, mode: readPlay.mode, token: readPlay.token, heard: readPlay.heard, limitMs: readPlay.limitMs } : null,""",
    "诊断快照补 play")

# ============================================================ 11. 测试钩子
one("""    readStop: function () { stopSpeaking(); return true; },""",
    """    readStop: function () { stopSpeaking(); return true; },
    /* 第 139 条：播放层观测与调参 */
    play: function () { return { id: readPlay.id, mode: readPlay.mode, token: readPlay.token, heard: readPlay.heard, limitMs: readPlay.limitMs, miss: readPlay.miss, polling: !!readPlay.poll }; },
    playTune: function (o) {
      o = o || {};
      if (o.idle != null) READ_IDLE_TO = Math.max(300, Number(o.idle) || 0);
      if (o.mul != null) READ_TAIL_MUL = Math.max(0.2, Number(o.mul) || 0);
      if (o.add != null) READ_TAIL_ADD = Math.max(200, Number(o.add) || 0);
      return { idle: READ_IDLE_TO, mul: READ_TAIL_MUL, add: READ_TAIL_ADD };
    },
    segs: function (t) { try { return readPlaySegments(t); } catch (e) { return []; } },""",
    "新增 play / playTune / segs 钩子")

# ============================================================ 12. 版本号
c = s.count("2026-10-31e")
assert c >= 2, "version count %d" % c
s = s.replace("2026-10-31e", "2026-10-31f")
print("ok  version -> 2026-10-31f (%d)" % c)

io.open(P, "w", encoding="utf-8").write(s)
print("applied", n, "patches")
