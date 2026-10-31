# -*- coding: utf-8 -*-
"""第 137 条：整页朗读在手机端「读完第一条就停 / 跳过点了没反应」修复"""
import io

import os as _os
P = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "index.html")
src = io.open(P, encoding="utf-8").read()
n_ok = 0

def sub(old, new, cnt, label):
    global src, n_ok
    c = src.count(old)
    if c != cnt:
        raise SystemExit("FAIL [%s] expect %d got %d" % (label, cnt, c))
    src = src.replace(old, new, cnt)
    n_ok += 1
    print("ok  %s" % label)

# ---------------------------------------------------------------- 1. 诊断计数新增 deadItems
sub("const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '', pollDone: 0, tick: 0, synth: false, lastToast: 0 };",
    "const speechDiag = { wd: 0, heal: 0, giveUp: 0, recover: 0, lastErr: '', pollDone: 0, tick: 0, synth: false, lastToast: 0, deadItems: 0 };",
    1, "speechDiag 增加 deadItems")

# ---------------------------------------------------------------- 2. 开播检测：不再按句长慢慢等
sub("""  /* 一直没出声：开播检测到点就进自愈流程；连续哑火时把等待压到最短，别让整页朗读干等 */
  const startDeadline = (q.deadStreak && q.deadStreak >= 2)
    ? Math.min(SPEECH_START_TO, 700)
    : Math.max(SPEECH_START_TO, est * 0.6);
  if (now - q.startedAt < startDeadline) return;""",
    """  /* 第 137 条：一直没出声就别按句子长度慢慢等了 —— 真在念的话早就出声了。
     首次 1.5s 判定哑火，之后收紧到 0.6s，长句也不会让整页朗读干等十几秒。 */
  const startDeadline = q.deadStreak ? 600 : Math.min(SPEECH_START_TO, 1500);
  if (now - q.startedAt < startDeadline) return;""",
    1, "开播检测缩短")

# ---------------------------------------------------------------- 3. speechSentenceDone：别无谓 cancel
sub("""  q.doneToken = key;
  try { window.speechSynthesis.cancel(); } catch (e) {}
  q.i++;""",
    """  q.doneToken = key;
  /* 第 137 条：iOS Safari 调过 cancel() 之后合成器会彻底哑掉 —— 只在它真的还在念时才掐断 */
  let still = false;
  try { still = !!window.speechSynthesis.speaking; } catch (e) { still = false; }
  if (still) { try { window.speechSynthesis.cancel(); } catch (e) {} }
  if (q.wasSpeaking) { speechDiag.deadItems = 0; q.deadStreak = 0; }
  q.i++;""",
    1, "句末只在仍在发声时才 cancel")

# ---------------------------------------------------------------- 4. speechStalled：唤醒 + 整条放弃
sub("""  if (tries === 1) {
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
  q.wdTries = 0;""",
    """  if (tries === 1) {
    /* 多半是 iOS 把合成器挂起了：resume + 空语句唤醒之后再读一次 */
    try { window.speechSynthesis.resume(); } catch (e) {}
    speechRevive();
    speechDiag.heal++;
    setTimeout(again, 260);
    return;
  }
  speechDiag.giveUp++;
  q.deadStreak = (q.deadStreak || 0) + 1;    /* 连续哑火 → 后面几句的超时收紧 */
  q.wdTries = 0;
  try { window.speechSynthesis.cancel(); } catch (e) {}
  if (q.deadStreak >= 2) {
    /* 这台机器连续两句都不出声：整条放弃，直接进下一条，别把剩下的句子挨个磨一遍 */
    speechDiag.deadItems = (speechDiag.deadItems || 0) + 1;
    q.doneToken = 'dead';
    speechFinish(q.id);
    return;
  }""",
    1, "哑火自愈：空语句唤醒 + 整条放弃")

# ---------------------------------------------------------------- 5. 发声前不再无条件 cancel
sub("""  /* iOS 上若合成器还留着上一条状态，第二次 speak 会静音：先干净地清一次再发 */
  try { if (window.speechSynthesis.speaking) window.speechSynthesis.cancel(); } catch (e) {}
  try { if (window.speechSynthesis.paused) window.speechSynthesis.resume(); } catch (e) {}""",
    """  /* 第 137 条：iOS 上调 cancel() 会让后续 speak 永久静音 —— 这里只解除暂停，不再抢着清状态 */
  try { if (window.speechSynthesis.paused) window.speechSynthesis.resume(); } catch (e) {}""",
    1, "发声前不再无条件 cancel")

# ---------------------------------------------------------------- 6. 新增 speechRevive
sub("""function speechNext() { if (speechQueue) speechSpeakCurrent(speechQueue); }""",
    """function speechNext() { if (speechQueue) speechSpeakCurrent(speechQueue); }
/* 第 137 条：iOS Safari 的顽疾 —— 调过 cancel() 之后合成器往往彻底哑掉。
   社区通行解法是用一条「空语句」把合成器重新激活再收尾，这里封装成一次唤醒。 */
function speechRevive() {
  if (!speechSupported) return;
  try { window.speechSynthesis.cancel(); } catch (e) {}
  try {
    const w = new SpeechSynthesisUtterance('\\u3002');
    w.volume = 0;
    window.speechSynthesis.speak(w);
  } catch (e) {}
  setTimeout(() => { try { window.speechSynthesis.cancel(); } catch (e) {} }, 80);
}""",
    1, "新增 speechRevive")

# ---------------------------------------------------------------- 7. 心跳：speakingId 不再算「忙」
sub("""  const busy = !!state.speakingId || !!speechQueue || !!readSpeakTimer || !!cloudQueue;
  if (busy) { readSpeakQuietSince = Date.now(); return; }
  if (Date.now() - readSpeakQuietSince < 6000) return;
  readSpeakQuietSince = Date.now();
  speechDiag.recover++;
  const now = Date.now();
  if (now - (speechDiag.lastToast || 0) > 20000) {
    speechDiag.lastToast = now;
    showToast('\\u6717\\u8bfb\\u88ab\\u7cfb\\u7edf\\u6253\\u65ad\\uff0c\\u6b63\\u5728\\u7ee7\\u7eed');
  }
  readSpeakSkip();""",
    """  /* 第 137 条：speakingId 绝不能算「忙」—— 系统吞掉发声时它会一直挂着，
     于是心跳永远认为还在读，序列级自愈一次都不会触发（这正是上一版卡死的直接原因）。
     改看真实状态：合成器在不在出声、有没有待播队列/定时器。 */
  let synth = false;
  try { synth = !!window.speechSynthesis.speaking; } catch (e) { synth = false; }
  const busy = synth || !!speechQueue || !!readSpeakTimer || !!cloudQueue;
  if (busy) { readSpeakQuietSince = Date.now(); return; }
  if (Date.now() - readSpeakQuietSince < 4500) return;
  readSpeakQuietSince = Date.now();
  speechDiag.recover++;
  const now = Date.now();
  /* 连续两条都被系统拒绝：交给用户点一下 —— 真实点击手势是 iOS 上唯一可靠的唤醒方式 */
  if ((speechDiag.deadItems || 0) >= 2) {
    readSpeakNeedTap = true;
    readSpeakUi();
    return;
  }
  if (now - (speechDiag.lastToast || 0) > 20000) {
    speechDiag.lastToast = now;
    showToast('\\u6717\\u8bfb\\u88ab\\u7cfb\\u7edf\\u6253\\u65ad\\uff0c\\u6b63\\u5728\\u7ee7\\u7eed');
  }
  readSpeakSkip();""",
    1, "心跳判定改为真实发声状态")

# ---------------------------------------------------------------- 8. needTap 状态位
sub("""var readSpeakSeq = null;
var readSpeakTimer = 0;""",
    """var readSpeakSeq = null;
var readSpeakTimer = 0;
var readSpeakNeedTap = false;   /* 第 137 条：系统拒绝自动续读，等用户点「继续朗读」 */""",
    1, "新增 readSpeakNeedTap 状态位")

sub("""  readSpeakSeq = { ids: ids, i: Math.min(i, ids.length - 1) };
  readSpeakHeartStart();
  readSpeakPlay();""",
    """  readSpeakNeedTap = false;
  speechDiag.deadItems = 0;
  readSpeakSeq = { ids: ids, i: Math.min(i, ids.length - 1) };
  readSpeakHeartStart();
  readSpeakPlay();""",
    1, "readSpeakBegin 复位")

sub("""function readSpeakSkip() {
  const q = readSpeakSeq;
  if (!q) return;
  stopSpeaking(true);""",
    """function readSpeakSkip() {
  const q = readSpeakSeq;
  if (!q) return;
  readSpeakNeedTap = false;
  stopSpeaking(true);""",
    1, "readSpeakSkip 复位 needTap")

sub("""function readSpeakStop() {
  readSpeakSeq = null;""",
    """function readSpeakStop() {
  readSpeakSeq = null;
  readSpeakNeedTap = false;""",
    1, "readSpeakStop 复位 needTap")

# ---------------------------------------------------------------- 9. 继续朗读（真手势）
sub("""/* 悬浮条 + 顶栏按钮 + 当前条高亮 */
function readSpeakUi() {""",
    """/* 第 137 条：用户点「继续朗读」—— 真实点击手势能重新唤醒被系统挂起的合成器 */
function readSpeakResume() {
  const q = readSpeakSeq;
  if (!q) return;
  readSpeakNeedTap = false;
  speechDiag.deadItems = 0;
  readSpeakQuietSince = Date.now();
  try { window.speechSynthesis.resume(); } catch (e) {}
  readSpeakPlay();
}
/* 悬浮条 + 顶栏按钮 + 当前条高亮 */
function readSpeakUi() {""",
    1, "新增 readSpeakResume")

# ---------------------------------------------------------------- 10. 浮条 UI：跳过 / 继续 互斥
sub("""  const it = state.items.find(x => x.id === active);
  if (bar) bar.style.display = 'flex';
  if (txt) {
    const head = q ? '第 ' + (q.i + 1) + '/' + q.ids.length + ' 条' : '正在朗读';
    txt.textContent = head + ' · ' + (it ? (it.title || '无标题') : '');
  }""",
    """  const it = state.items.find(x => x.id === active);
  if (bar) bar.style.display = 'flex';
  if (txt) {
    if (readSpeakNeedTap) {
      txt.textContent = '系统暂停了自动续读';
    } else {
      const head = q ? '第 ' + (q.i + 1) + '/' + q.ids.length + ' 条' : '正在朗读';
      txt.textContent = head + ' · ' + (it ? (it.title || '无标题') : '');
    }
  }
  /* 第 137 条：需要手势时把「跳过」换成「继续朗读」 */
  const rsBtn = document.getElementById('readSpeakResume');
  const nxBtn = document.getElementById('readSpeakNext');
  if (rsBtn) rsBtn.style.display = readSpeakNeedTap ? 'inline-block' : 'none';
  if (nxBtn) nxBtn.style.display = readSpeakNeedTap ? 'none' : 'inline-block';""",
    1, "浮条 UI 支持继续态")

# ---------------------------------------------------------------- 11. 浮条 HTML 增加「继续朗读」
sub("""      <button type="button" class="rsb-btn rsb-next" id="readSpeakNext" title="跳过这一条，直接读下一条">跳过</button>""",
    """      <button type="button" class="rsb-btn rsb-resume" id="readSpeakResume" style="display:none" title="点一下接着往下读">继续朗读</button>
      <button type="button" class="rsb-btn rsb-next" id="readSpeakNext" title="跳过这一条，直接读下一条">跳过</button>""",
    1, "浮条增加继续朗读按钮")

# ---------------------------------------------------------------- 12. CSS
sub("""@media (max-width: 640px) { .read-speak-bar { left: 12px; right: 12px; bottom: 12px; } }""",
    """/* 第 137 条：「继续朗读」是主操作，手机端按钮加大好点 */
.read-speak-bar .rsb-resume { background: var(--primary); border-color: var(--primary); color: var(--text-on-primary); }
@media (max-width: 640px) {
  .read-speak-bar { left: 12px; right: 12px; bottom: calc(12px + env(safe-area-inset-bottom, 0px)); }
  .read-speak-bar .rsb-btn { padding: 6px 14px; font-size: 13px; }
}""",
    1, "浮条按钮加大 + 安全区")

# ---------------------------------------------------------------- 13. 绑定「继续朗读」
sub("""  const rsbStop = document.getElementById('readSpeakStop');""",
    """  const rsbResume = document.getElementById('readSpeakResume');
  if (rsbResume) rsbResume.addEventListener('click', (e) => { e.stopPropagation(); readSpeakResume(); });
  const rsbStop = document.getElementById('readSpeakStop');""",
    1, "绑定继续朗读")

# ---------------------------------------------------------------- 14. 诊断快照补 deadItems
sub("""    counters: { wd: speechDiag.wd, heal: speechDiag.heal, giveUp: speechDiag.giveUp, pollDone: speechDiag.pollDone, recover: speechDiag.recover, tickRuns: speechDiag.tick, lastErr: speechDiag.lastErr }""",
    """    needTap: (typeof readSpeakNeedTap !== 'undefined') ? !!readSpeakNeedTap : false,
    counters: { wd: speechDiag.wd, heal: speechDiag.heal, giveUp: speechDiag.giveUp, pollDone: speechDiag.pollDone, recover: speechDiag.recover, tickRuns: speechDiag.tick, deadItems: speechDiag.deadItems || 0, lastErr: speechDiag.lastErr }""",
    1, "诊断快照补 needTap/deadItems")

# ---------------------------------------------------------------- 15. 测试钩子
sub("""    snapshot: function () { try { return speechDiagSnapshot(); } catch (e) { return { err: String(e) }; } },""",
    """    snapshot: function () { try { return speechDiagSnapshot(); } catch (e) { return { err: String(e) }; } },
    resume: function () { try { readSpeakResume(); return true; } catch (e) { return String(e); } },
    needTap: function () { return !!readSpeakNeedTap; },
    deadItems: function () { return speechDiag.deadItems || 0; },""",
    1, "新增测试钩子")

# ---------------------------------------------------------------- 16. 版本号
sub("2026-10-31c", "2026-10-31d", 2, "版本号递增")

io.open(P, "w", encoding="utf-8").write(src)
print("all applied:", n_ok)
