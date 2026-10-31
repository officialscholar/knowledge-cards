# -*- coding: utf-8 -*-
"""第 140 条：音色切换无效 + 试听起播慢

两个根因：
1) readPlayVoice()（整页朗读 / 单条朗读共用的音色解析）一律挑「打分最高的本地音色」，
   把 speechSettings.voice 整个丢掉 —— 用户怎么切都没用。
2) speechPreview() 先 stopSpeaking()（内部可能 cancel）再立刻 speak()，
   Chrome 会把紧跟 cancel 的 speak 吞掉 / 延迟数秒，表现就是「点试听后反应很久」；
   而且开了云端朗读时，本地音色下拉被完全绕过，切了当然没变化。

本补丁：一个下拉统管系统音色与云端音色；朗读与试听都按选择走；试听 cancel 后空一拍再发，
带看门狗与一次重试，并即时反馈「正在启动合成器…」。
"""
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(BASE, "index.html")

SRC = io.open(PAGE, encoding="utf-8").read()
ORIG = SRC
REPL = []
MOVED = []


def rep(label, old, new):
    global SRC
    n = SRC.count(old)
    if n != 1:
        print("[FAIL] %s: 锚点命中 %d 次" % (label, n))
        sys.exit(1)
    SRC = SRC.replace(old, new)
    REPL.append(label)


# ---------------------------------------------------------------- 1 统一音色入口
rep(
    "helper",
    """  return zs.slice().sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a))[0];
}

/* ---------- 第 129 条 P1：朗读文本预处理 ----------""",
    """  return zs.slice().sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a))[0];
}

/* ---------- 第 140 条：音色选择统一入口 ----------
   旧实现有两套音色（面板里的系统音色下拉 + 云端朗读区的云端音色下拉），
   而 readPlayVoice() 又一律挑「打分最高的本地音色」——等于把用户的选择整个丢掉，
   于是「切换音色没有任何改变」。现在统一成 speechSettings.voice 一个字段：
     ''                          自动优选
     'Microsoft Huihui - ...'    指定系统音色（离线 / 在线都可以）
     'cloud:zh-CN-YunxiNeural'   指定云端音色（会自动打开云端朗读开关） */
const CLOUD_VOICE_PREFIX = 'cloud:';
function speechVoiceCloudId() {
  const v = String(speechSettings.voice || '');
  return v.indexOf(CLOUD_VOICE_PREFIX) === 0 ? v.slice(CLOUD_VOICE_PREFIX.length) : '';
}
/* 这一次朗读走云端还是系统：选了云端音色必然云端，选了系统音色必然系统，
   两个都没选（自动）时才沿用「云端朗读」开关 */
function speechUseCloud() {
  try {
    if (speechVoiceCloudId()) return cloudTtsReady();
    if (String(speechSettings.voice || '')) return false;
    return cloudTtsReady();
  } catch (e) { return false; }
}
/* 按名字找系统音色：系统重名 / 大小写差异时做一次容错匹配 */
function speechVoiceByName(name) {
  if (!name) return null;
  const zs = speechZhVoices();
  const hit = zs.find(v => v.name === name);
  if (hit) return hit;
  const norm = n => String(n || '').toLowerCase().replace(/\\s+/g, ' ').trim();
  const loose = zs.find(v => norm(v.name) === norm(name));
  return loose || null;
}

/* ---------- 第 129 条 P1：朗读文本预处理 ----------""",
)

# ---------------------------------------------------------------- 2 朗读音色尊重选择
rep(
    "readPlayVoice",
    """/* 整页朗读的音色：优先本地音色。在线音色每句都要取流，是「长时间没声音」的主因 */
function readPlayVoice() {
  try {
    const local = speechZhVoices().filter(v => v.localService);
    if (local.length) {
      local.sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a));
      return local[0];
    }
  } catch (e) {}
  try { return getChineseVoice(); } catch (e) { return null; }
}""",
    """/* 整页朗读 / 单条朗读共用的音色解析：用户选了就照办，只有「自动优选」才替他挑
   （旧版一律挑打分最高的本地音色，这正是「切了音色没反应」的根因） */
function readPlayVoice() {
  const want = String(speechSettings.voice || '');
  if (want && !speechVoiceCloudId()) {
    const hit = speechVoiceByName(want);
    if (hit) return hit;
  }
  try {
    const local = speechZhVoices().filter(v => v.localService);
    if (local.length) {
      local.sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a));
      return local[0];
    }
  } catch (e) {}
  try { return getChineseVoice(); } catch (e) { return null; }
}""",
)

# ---------------------------------------------------------------- 3 播放时按音色的 lang
rep(
    "readPlaySystem.lang",
    """    u.volume = SPEECH_CONFIG.volume;
    u.lang = SPEECH_CONFIG.lang;
    if (voice) { try { u.voice = voice; } catch (e) {} }
    speechUtterance = u;""",
    """    u.volume = SPEECH_CONFIG.volume;
    /* 第 140 条：lang 必须跟着音色走。lang 写成 zh-CN 而音色是别的口音时，
       Chrome 会静默替换成默认音色 —— 看起来就像「切换无效」 */
    u.lang = (voice && voice.lang) ? voice.lang : SPEECH_CONFIG.lang;
    if (voice) { try { u.voice = voice; } catch (e) {} }
    speechDiag.lastVoice = voice ? voice.name : '(\u9ed8\u8ba4)';
    speechUtterance = u;""",
)

# ---------------------------------------------------------------- 4 走云端还是系统
rep(
    "readPlayItem.cloud",
    """  let cloud = false;
  try { cloud = !!cloudTtsReady(); } catch (e) { cloud = false; }""",
    """  let cloud = false;
  try { cloud = speechUseCloud(); } catch (e) { cloud = false; }""",
)

# ---------------------------------------------------------------- 5 试听重写
rep(
    "speechPreview",
    """/* 第 130 条：试听 —— 不打断按钮态，直接用当前选中的音色读一句样例 */
function speechPreview() {
  if (!speechSupported) return;
  stopSpeaking();
  /* 第 131 条：开了云端就用云端音色试听 */
  if (cloudTtsReady()) { cloudUnlockAudio(); cloudTestVoice(); return; }
  const sel = document.getElementById('speakVoiceSel');
  const v = (sel && sel.value) ? speechZhVoices().find(x => x.name === sel.value) : getChineseVoice();
  const u = new SpeechSynthesisUtterance('你好，这是当前音色的试听效果，挑一个最顺耳的吧。');
  u.rate = speechSettings.rate;
  u.pitch = SPEECH_CONFIG.pitch;
  u.volume = SPEECH_CONFIG.volume;
  u.lang = SPEECH_CONFIG.lang;
  if (v) { try { u.voice = v; } catch (e) {} }
  try { window.speechSynthesis.speak(u); } catch (e) {}
}""",
    """/* ---------- 第 140 条：试听 ----------
   旧实现两个硬伤：
   ① 先 stopSpeaking()（内部会 cancel）再立刻 speak() —— Chrome 会把紧跟 cancel 的 speak
      吞掉或延迟数秒，「点试听很久才有声音」就是这么来的；
   ② 只要开了云端朗读就无条件走云端，系统音色下拉被完全绕过，切了自然没变化。
   现在：按当前选择决定走哪条路；真掐断过就空一拍再发；带看门狗 + 一次重试；按钮即时反馈。 */
const SPEECH_PREVIEW_TEXT = '你好，我是当前音色，听一听喜不喜欢。';
var speechPreviewTok = 0;
function speechPreviewState(t) {
  const b = document.getElementById('speakPreviewBtn');
  if (b) b.textContent = t ? ('\u2026 ' + t) : '\u25b6 \u8bd5\u542c\u5f53\u524d\u97f3\u8272';
  const h = document.getElementById('speakPrevHint');
  if (h) {
    if (t) { h.textContent = t; h.style.display = 'block'; }
    else { h.textContent = ''; h.style.display = 'none'; }
  }
}
function speechPreview() {
  if (!speechSupported) return;
  const tok = ++speechPreviewTok;
  let wasBusy = false;
  try { const sy = window.speechSynthesis; wasBusy = !!(sy.speaking || sy.pending || sy.paused); } catch (e) {}
  stopSpeaking();
  /* 云端：合成要走网络，先把状态说出来，别让人以为按钮失灵 */
  if (speechUseCloud()) {
    speechPreviewState('\u6b63\u5728\u5411\u4e91\u7aef\u53d6\u6d41\u2026');
    try { cloudUnlockAudio(); } catch (e) {}
    cloudTestVoice().then(() => { if (tok === speechPreviewTok) speechPreviewState(''); });
    return;
  }
  const v = speechVoiceByName(speechSettings.voice) || getChineseVoice();
  const u = new SpeechSynthesisUtterance(SPEECH_PREVIEW_TEXT);
  u.rate = speechSettings.rate;
  u.pitch = SPEECH_CONFIG.pitch;
  u.volume = SPEECH_CONFIG.volume;
  u.lang = (v && v.lang) ? v.lang : SPEECH_CONFIG.lang;
  if (v) { try { u.voice = v; } catch (e) {} }
  speechDiag.lastVoice = v ? v.name : '(\u9ed8\u8ba4)';
  speechPreviewState('\u6b63\u5728\u542f\u52a8\u5408\u6210\u5668\u2026');
  let heard = false;
  const spokenName = v ? v.name : '\u9ed8\u8ba4\u97f3\u8272';
  u.onstart = () => { heard = true; if (tok === speechPreviewTok) speechPreviewState('\u6b63\u5728\u7528\uff1a' + spokenName); };
  u.onboundary = () => { heard = true; };
  u.onend = () => { heard = true; if (tok === speechPreviewTok) speechPreviewState(''); };
  u.onerror = (ev) => {
    const err = ev && ev.error;
    if (err === 'canceled' || err === 'interrupted') return;
    if (tok === speechPreviewTok) speechPreviewState('\u8bd5\u542c\u5931\u8d25\uff1a' + (err || '\u672a\u77e5\u9519\u8bef'));
  };
  let tries = 0;
  const watchdog = () => {
    setTimeout(() => {
      if (tok !== speechPreviewTok || heard) return;
      let spk = false;
      try { spk = !!window.speechSynthesis.speaking; } catch (e) {}
      if (spk) { heard = true; return; }
      if (tries >= 1) {
        if (tok === speechPreviewTok) speechPreviewState('\u6ca1\u6709\u58f0\u97f3\uff1a\u8bf7\u786e\u8ba4\u7cfb\u7edf\u88c5\u4e86\u4e2d\u6587\u8bed\u97f3\u5305');
        return;
      }
      /* Chrome 的合成器被上一次 cancel 卡死时，只有「再掐一次 + 重发」能唤醒 */
      tries++;
      try { window.speechSynthesis.cancel(); } catch (e) {}
      setTimeout(() => {
        if (tok !== speechPreviewTok) return;
        try { window.speechSynthesis.resume(); } catch (e) {}
        try { window.speechSynthesis.speak(u); } catch (e) {}
        watchdog();
      }, 180);
    }, 2200);
  };
  const fire = () => {
    if (tok !== speechPreviewTok) return;
    try { window.speechSynthesis.resume(); } catch (e) {}
    try { window.speechSynthesis.speak(u); } catch (e) {}
    watchdog();
  };
  /* 确实掐断过（正在播 / 排队 / 暂停）才需要空一拍，否则立刻发声 */
  if (wasBusy) setTimeout(fire, 160); else fire();
}""",
)

# ---------------------------------------------------------------- 6 下拉合并云端音色
rep(
    "populateVoiceSelect",
    """function populateVoiceSelect() {
  const sel = document.getElementById('speakVoiceSel');
  if (!sel) return;
  const zs = speechZhVoices().slice().sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a));
  const cur = sel.value;
  sel.innerHTML = '<option value="">自动优选（推荐）</option>' + zs.map(v =>
    `<option value="${escapeHtml(v.name)}">${escapeHtml(v.name)}${v.localService ? '（离线）' : '（在线）'}</option>`).join('');
  sel.value = zs.some(v => v.name === cur) ? cur : (speechSettings.voice || '');
}""",
    """function populateVoiceSelect() {
  const sel = document.getElementById('speakVoiceSel');
  if (!sel) return;
  const zs = speechZhVoices().slice().sort((a, b) => speechVoiceScore(b) - speechVoiceScore(a));
  const keep = sel.value || speechSettings.voice || '';
  let html = '<option value="">自动优选（推荐）</option>' + zs.map(v =>
    `<option value="${escapeHtml(v.name)}">${escapeHtml(v.name)}${v.localService ? '（离线）' : '（在线）'}</option>`).join('');
  /* 第 140 条：云端音色并进同一个下拉 ——「我用哪个声音」只该有一个答案，
     分成两处开关正是「切了没反应」的来源 */
  const cid = speechVoiceCloudId();
  if (cloudTtsReady() || cid) {
    html += '<optgroup label="云端音色（Azure · 需联网）">' + CLOUD_TTS.voices.map(v =>
      `<option value="${CLOUD_VOICE_PREFIX}${v[0]}">${v[1]}</option>`).join('') + '</optgroup>';
  }
  sel.innerHTML = html;
  const has = Array.prototype.some.call(sel.options, o => o.value === keep);
  sel.value = has ? keep : '';
}""",
)

# ---------------------------------------------------------------- 7 当前音色说明
rep(
    "hint",
    """  const v = getChineseVoice();
  const hint = document.getElementById('speakVoiceHint');
  /* 第 138 条：在线音色每句开头都要取流，天然有 1~2 秒延迟 —— 说清楚，免得被当成故障 */
  if (hint) hint.textContent = v
    ? (`当前：${v.name}${v.localService ? '（离线，连贯）' : '（在线，更自然，但每句开头可能有 1~2 秒取流延迟）'}`)
    : '未检测到中文音色';""",
    """  /* 第 140 条：这里要显示「真正会用的那个声音」，而不是另一个函数猜的 */
  const cid = speechVoiceCloudId();
  const hint = document.getElementById('speakVoiceHint');
  let label;
  if (cid && cloudTtsReady()) {
    const n = CLOUD_TTS.voices.find(x => x[0] === cid);
    label = '当前：云端 ' + (n ? n[1] : cid) + '（需联网；起播最快、声音最自然）';
  } else if (cid) {
    label = '当前：选了云端音色，但云端朗读还没开启或没填密钥 —— 会先回退系统音色';
  } else if (!String(speechSettings.voice || '') && cloudTtsReady()) {
    const n = CLOUD_TTS.voices.find(x => x[0] === speechSettings.cloud.voice);
    label = '当前：自动（云端 ' + (n ? n[1] : speechSettings.cloud.voice) + '）';
  } else {
    const v = readPlayVoice();
    label = v
      ? ('当前：' + v.name + (v.localService ? '（离线，起播快、连贯）' : '（在线，更自然，起播可能慢 1~2 秒）'))
      : '未检测到中文音色';
  }
  if (hint) hint.textContent = label;""",
)

# ---------------------------------------------------------------- 8 面板文案 + 预览状态位
rep(
    "panel.hint",
    """      <div class="rs-hint">整页朗读（▶ 朗读本页）为保证连贯会自动选用本地音色；想要更自然的声音，可开启下方云端朗读。</div>
      <button type="button" class="rs-btn" id="speakPreviewBtn">▶ 试听当前音色</button>""",
    """      <div class="rs-hint">这里选的音色对「朗读本页」和单条朗读都生效；只有选「自动优选」时才按离线优先自动挑。云端音色需联网并填好下方密钥。</div>
      <button type="button" class="rs-btn" id="speakPreviewBtn">▶ 试听当前音色</button>
      <div class="rs-hint" id="speakPrevHint" style="display:none"></div>""",
)

# ---------------------------------------------------------------- 9 选择即生效
rep(
    "sel.change",
    """  if (sel) sel.addEventListener('change', () => {
    speechSettings.voice = sel.value;
    saveSpeechSettings();
    syncSpeechSettingsUi();
  });""",
    """  if (sel) sel.addEventListener('change', () => {
    speechSettings.voice = sel.value;
    const cid = speechVoiceCloudId();
    if (cid) {
      speechSettings.cloud.voice = cid;
      if (!speechSettings.cloud.on) speechSettings.cloud.on = true;
      if (!speechSettings.cloud.key) showToast('云端音色需要先填 Azure 密钥（在下方云端朗读里），暂时仍用系统音色', true);
    }
    saveSpeechSettings();
    syncSpeechSettingsUi();
    speechPreview();            /* 选完立刻用新音色试听 —— 切换有没有生效，一听就知道 */
  });""",
)

# ---------------------------------------------------------------- 10 云端下拉与统一字段对齐
rep(
    "cvoice.change",
    """  if (cvoice) cvoice.addEventListener('change', () => {
    speechSettings.cloud.voice = cvoice.value;
    speechSettings.cloud.lastErr = '';
    saveSpeechSettings();
    refreshCloudHint();
  });""",
    """  if (cvoice) cvoice.addEventListener('change', () => {
    speechSettings.cloud.voice = cvoice.value;
    speechSettings.cloud.lastErr = '';
    /* 第 140 条：与统一音色下拉保持一致，避免两处各说各话 */
    speechSettings.voice = CLOUD_VOICE_PREFIX + cvoice.value;
    saveSpeechSettings();
    syncSpeechSettingsUi();
  });""",
)

# ---------------------------------------------------------------- 11 诊断字段
rep(
    "diag.obj",
    """const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '', pollDone: 0, tick: 0, synth: false, lastToast: 0, deadItems: 0, taps: 0, log: [] };""",
    """const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '', pollDone: 0, tick: 0, synth: false, lastToast: 0, deadItems: 0, taps: 0, lastVoice: '', log: [] };""",
)

rep(
    "diag.snapshot",
    """    voices: voices,
    voice: cur,""",
    """    voices: voices,
    voice: cur,
    voiceSel: { sel: String(speechSettings.voice || ''), cloudId: (function () { try { return speechVoiceCloudId(); } catch (e) { return ''; } })(), useCloud: (function () { try { return speechUseCloud(); } catch (e) { return null; } })(), last: speechDiag.lastVoice || '' },""",
)

# ---------------------------------------------------------------- 12 测试钩子
rep(
    "hooks",
    """    segs: function (t) { try { return readPlaySegments(t); } catch (e) { return []; } },""",
    """    segs: function (t) { try { return readPlaySegments(t); } catch (e) { return []; } },
    /* 第 140 条：音色选择 / 试听 */
    voicePick: function () {
      try { var v = readPlayVoice(); return v ? { name: v.name, local: !!v.localService, lang: v.lang } : null; }
      catch (e) { return null; }
    },
    useCloud: function () { try { return speechUseCloud(); } catch (e) { return null; } },
    setVoice: function (n) {
      speechSettings.voice = String(n == null ? '' : n);
      saveSpeechSettings();
      try { syncSpeechSettingsUi(); } catch (e) {}
      return speechSettings.voice;
    },
    preview: function () { try { speechPreview(); return true; } catch (e) { return String(e); } },
    previewText: function () { return SPEECH_PREVIEW_TEXT; },
    previewState: function () {
      var b = document.getElementById('speakPreviewBtn'), h = document.getElementById('speakPrevHint');
      return {
        btn: b ? b.textContent : '',
        hint: (h && getComputedStyle(h).display !== 'none') ? h.textContent : '',
        selVal: (function () { var s = document.getElementById('speakVoiceSel'); return s ? s.value : null; })(),
        opts: (function () {
          var s = document.getElementById('speakVoiceSel');
          return s ? Array.prototype.map.call(s.options, function (o) { return o.value; }) : [];
        })()
      };
    },""",
)

# ---------------------------------------------------------------- 13 版本号
rep("ver", "window.__KV__='2026-10-31f'", "window.__KV__='2026-10-31g'")
rep("ver2", "window.__KV__ = '2026-10-31f';", "window.__KV__ = '2026-10-31g';")

io.open(PAGE, "w", encoding="utf-8", newline="").write(SRC)
print("OK 已应用 %d 处：" % len(REPL))
for r in REPL:
    print("  -", r)
print("字节：%d -> %d (%+d)" % (len(ORIG.encode("utf-8")), len(SRC.encode("utf-8")), len(SRC.encode("utf-8")) - len(ORIG.encode("utf-8"))))
