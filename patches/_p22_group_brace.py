# -*- coding: utf-8 -*-
"""第 142 条补丁：总结节点落点决定连线方式 + 分组左/右/下大括号说明

用法： python patches/_p22_group_brace.py
"""
import io
import os

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")


def sub(s, old, new, tag):
    n = s.count(old)
    assert n == 1, "锚点不唯一/缺失 [%s] count=%d" % (tag, n)
    return s.replace(old, new)


# 源文件是 CRLF：读进来先统一成 \n 便于锚点匹配，写回时还原 CRLF
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
orig_len = len(s)

# ---------------------------------------------------------------- 0 版本号
assert s.count("2026-10-31h") == 2, s.count("2026-10-31h")
s = s.replace("2026-10-31h", "2026-10-31i")

# ---------------------------------------------------------------- 1 state 字段
s = sub(s,
        "  nodeGroups: [],\n  nodeGroupSelectedId: null,",
        "  nodeGroups: [],\n  nodeGroupSelectedId: null,\n  ngBraceEdit: null,",
        "state.ngBraceEdit")

# ---------------------------------------------------------------- 2 CSS
CSS_OLD = """.ng-drag-line {
  fill: none; stroke: var(--primary-bright); stroke-width: 2;
  stroke-dasharray: 6 5; stroke-linecap: round;
}"""
CSS_NEW = CSS_OLD + """
/* ===== 分组大括号说明（第 142 条）：左 / 右 / 下三边，括号后面可写一句总结 ===== */
.ng-brace-layer {
  position: absolute; left: 0; top: 0; width: 0; height: 0;
  pointer-events: none; z-index: 3;
}
.ng-brace { position: absolute; pointer-events: none; }
.ng-brace-svg {
  position: absolute; left: 0; top: 0; width: 100%; height: 100%;
  overflow: visible; pointer-events: none;
}
.ng-brace-path {
  fill: none; stroke: var(--primary-bright); stroke-width: 1.6;
  stroke-linecap: round; stroke-linejoin: round; opacity: 0.85;
}
.ng-brace-text {
  position: absolute; pointer-events: auto; cursor: text;
  max-width: 220px; min-width: 30px; box-sizing: border-box;
  padding: 3px 6px; border-radius: 7px;
  border: 1px solid transparent; background: var(--bg-surface);
  font-size: 0.72rem; line-height: 1.45; color: var(--text-secondary);
  white-space: pre-wrap; word-break: break-word;
  -webkit-tap-highlight-color: transparent;
}
.ng-brace-text:hover { border-color: var(--border); }
.ng-brace-text.empty { color: var(--text-faint); }
.ng-brace-text.empty::before { content: '点这里写说明'; opacity: 0.75; }
.ng-brace-text.editing { border-color: var(--primary-bright); outline: none; }
.ng-brace-text.editing::before { content: ''; }
.ng-brace-text[data-side="left"] { transform: translate(-100%, -50%); text-align: right; }
.ng-brace-text[data-side="right"] { transform: translate(0, -50%); text-align: left; }
.ng-brace-text[data-side="bottom"] { transform: translate(-50%, 0); text-align: center; }
@media (max-width: 640px) { .ng-brace-text { max-width: 150px; font-size: 0.7rem; } }"""
s = sub(s, CSS_OLD, CSS_NEW, "css-brace")

# ---------------------------------------------------------------- 3 组头按钮
BTN_OLD = """      '<span class="ng-tools">' +
        '<button type="button" class="ng-btn" data-ng="summary" title="按住拖到画布空白处，生成总结节点">⇢</button>' +"""
BTN_NEW = """      '<span class="ng-tools">' +
        '<button type="button" class="ng-btn" data-ng="brace" title="加总结说明（左 / 右 / 下大括号）">｝</button>' +
        '<button type="button" class="ng-btn" data-ng="summary" title="按住拖到画布空白处，生成总结节点">⇢</button>' +"""
s = sub(s, BTN_OLD, BTN_NEW, "ng-tools-btn")

# ---------------------------------------------------------------- 4 parseGroupsArray 保留 braces
PG_OLD = """function parseGroupsArray(arr, nodes) {"""
PG_NEW = """/* 分组大括号说明：{ left: {text}, right: {text}, bottom: {text} }，键存在即显示 */
const NG_BRACE_SIDES = ['left', 'right', 'bottom'];
const NG_BRACE_META = {
  left: { label: '左边', icon: '｛' },
  right: { label: '右边', icon: '｝' },
  bottom: { label: '下边', icon: '⏟' }
};
const NG_BRACE_GAP = 12;
const NG_BRACE_DEPTH = 16;
function parseGroupBraces(src) {
  const out = {};
  if (!src || typeof src !== 'object' || Array.isArray(src)) return out;
  NG_BRACE_SIDES.forEach(side => {
    const v = src[side];
    if (v == null) return;
    const text = (typeof v === 'string') ? v : (v && typeof v.text === 'string' ? v.text : '');
    out[side] = { text: String(text).slice(0, 300) };
  });
  return out;
}
function parseGroupsArray(arr, nodes) {"""
s = sub(s, PG_OLD, PG_NEW, "parseGroupBraces")

PUSH_OLD = """    out.push({
      id,
      name: (typeof g.name === 'string' && g.name.trim()) ? g.name.trim().slice(0, 40) : '未命名分组',
      nodeIds: members
    });"""
PUSH_NEW = """    out.push({
      id,
      name: (typeof g.name === 'string' && g.name.trim()) ? g.name.trim().slice(0, 40) : '未命名分组',
      nodeIds: members,
      braces: parseGroupBraces(g.braces)
    });"""
s = sub(s, PUSH_OLD, PUSH_NEW, "parseGroupsArray-braces")

# ---------------------------------------------------------------- 5 renderNodeGroups / syncGroupBoxes 挂上大括号
RG_OLD = """    let box = layer.querySelector('.node-group-box[data-group-id="' + nodeGroupEsc(g.id) + '"]');
    if (!box) { box = createGroupBoxEl(g); layer.appendChild(box); }
    updateGroupBoxEl(box, g, b);
  });
}"""
RG_NEW = """    let box = layer.querySelector('.node-group-box[data-group-id="' + nodeGroupEsc(g.id) + '"]');
    if (!box) { box = createGroupBoxEl(g); layer.appendChild(box); }
    updateGroupBoxEl(box, g, b);
  });
  try { renderNodeBraces(); } catch (e) {}
}"""
s = sub(s, RG_OLD, RG_NEW, "renderNodeGroups")

SG_OLD = """    box.style.width = b.w + 'px';
    box.style.height = b.h + 'px';
  });
}"""
SG_NEW = """    box.style.width = b.w + 'px';
    box.style.height = b.h + 'px';
  });
  try { syncGroupBraces(); } catch (e) {}
}"""
s = sub(s, SG_OLD, SG_NEW, "syncGroupBoxes")

# ---------------------------------------------------------------- 6 大括号主体代码
BRACE_CODE = r"""
/* ============================================================
   第 142 条：分组大括号说明
   数据：group.braces = { left:{text}, right:{text}, bottom:{text} }
   几何与大括号本身一样「现算」——只存文字，坐标永远跟着组框走
   ============================================================ */
function groupBraces(g) {
  if (!g) return {};
  if (!g.braces || typeof g.braces !== 'object' || Array.isArray(g.braces)) g.braces = {};
  return g.braces;
}
function groupHasBrace(g, side) { return !!groupBraces(g)[side]; }
function groupBraceText(g, side) {
  const b = groupBraces(g)[side];
  return (b && typeof b.text === 'string') ? b.text : '';
}
function ensureGroupBraceLayer() {
  if (state.mode !== 'node') return null;
  const world = document.getElementById('nodeWorld');
  if (!world) return null;
  let layer = document.getElementById('nodeGroupBraceLayer');
  if (!layer) {
    layer = document.createElement('div');
    layer.className = 'ng-brace-layer';
    layer.id = 'nodeGroupBraceLayer';
    const nl = document.getElementById('nodeLayer');
    if (nl && nl.parentNode === world) world.insertBefore(layer, nl);
    else world.appendChild(layer);
  }
  return layer;
}
/* 大括号几何：括号贴住组框外侧，尖角朝外，文字在尖角外侧居中对齐 */
function groupBraceLayout(g, side, b) {
  b = b || groupBounds(g);
  if (!b) return null;
  const GAP = NG_BRACE_GAP, D = NG_BRACE_DEPTH;
  const along = Math.max(40, (side === 'bottom' ? b.w : b.h) - 16);
  const startX = (side === 'bottom') ? b.x + 8 : 0;
  const startY = (side === 'bottom') ? 0 : b.y + 8;
  const baseX = (side === 'left') ? (b.x - GAP) : (side === 'right' ? (b.x + b.w + GAP) : 0);
  const baseY = (side === 'bottom') ? (b.y + b.h + GAP) : 0;
  let minX, minY, w, h;
  if (side === 'left') { minX = baseX - D - 2; minY = startY - 2; w = D + 4; h = along + 4; }
  else if (side === 'right') { minX = baseX - 2; minY = startY - 2; w = D + 4; h = along + 4; }
  else { minX = startX - 2; minY = baseY - 2; w = along + 4; h = D + 4; }
  return { side: side, b: b, along: along, depth: D, baseX: baseX, baseY: baseY,
           startX: startX, startY: startY, minX: minX, minY: minY, w: w, h: h };
}
/* 大括号骨架：在「沿线 a / 朝外 o」局部坐标里画，再按边映射成世界坐标 */
function braceSegments(along, depth) {
  const L = Math.max(24, along);
  const d = Math.max(6, depth);
  const r = Math.max(4, Math.min(d * 0.9, L / 6, 15));
  const h = L / 2;
  return [
    { t: 'M', p: [0, 0] },
    { t: 'C', p: [-d * 0.55, 0, -d * 0.5, r * 0.45, -d * 0.5, r] },
    { t: 'L', p: [-d * 0.5, h - r] },
    { t: 'C', p: [-d * 0.5, h - r * 0.45, -d, h - r * 0.5, -d, h] },
    { t: 'C', p: [-d, h + r * 0.5, -d * 0.5, h + r * 0.45, -d * 0.5, h + r] },
    { t: 'L', p: [-d * 0.5, L - r] },
    { t: 'C', p: [-d * 0.5, L - r * 0.45, -d * 0.55, L, 0, L] }
  ];
}
function bracePathD(geo) {
  const round = v => Math.round(v * 100) / 100;
  const pt = (a, o) => {
    let wx, wy;
    if (geo.side === 'left') { wx = geo.baseX + o; wy = geo.startY + a; }
    else if (geo.side === 'right') { wx = geo.baseX - o; wy = geo.startY + a; }
    else { wx = geo.startX + a; wy = geo.baseY - o; }
    return round(wx - geo.minX) + ' ' + round(wy - geo.minY);
  };
  let d = '';
  braceSegments(geo.along, geo.depth).forEach(seg => {
    if (seg.t === 'M') d += 'M ' + pt(seg.p[0], seg.p[1]) + ' ';
    else if (seg.t === 'L') d += 'L ' + pt(seg.p[0], seg.p[1]) + ' ';
    else d += 'C ' + pt(seg.p[0], seg.p[1]) + ', ' + pt(seg.p[2], seg.p[3]) + ', ' + pt(seg.p[4], seg.p[5]) + ' ';
  });
  return d.trim();
}
function createBraceEl(g, side) {
  const el = document.createElement('div');
  el.className = 'ng-brace';
  el.dataset.groupId = g.id;
  el.dataset.side = side;
  el.innerHTML = '<svg class="ng-brace-svg"><path class="ng-brace-path"></path></svg>' +
    '<div class="ng-brace-text" data-side="' + side + '" title="点一下写总结说明（回车保存，Shift+回车换行）"></div>';
  const txt = el.querySelector('.ng-brace-text');
  txt.dataset.groupId = g.id;
  txt.dataset.side = side;
  txt.addEventListener('pointerdown', (e) => { e.stopPropagation(); });
  txt.addEventListener('click', (e) => {
    e.stopPropagation();
    selectNodeGroup(g.id);
    startGroupBraceEdit(g.id, side);
  });
  txt.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); txt.blur(); }
    else if (e.key === 'Escape') { e.preventDefault(); txt.dataset.cancel = '1'; txt.blur(); }
  });
  txt.addEventListener('blur', () => { commitGroupBraceText(g.id, side, txt); });
  return el;
}
function layoutBraceEl(el, g, side, b) {
  const geo = groupBraceLayout(g, side, b);
  if (!geo) return;
  el.style.left = geo.minX + 'px';
  el.style.top = geo.minY + 'px';
  el.style.width = geo.w + 'px';
  el.style.height = geo.h + 'px';
  const path = el.querySelector('.ng-brace-path');
  if (path) path.setAttribute('d', bracePathD(geo));
  const txt = el.querySelector('.ng-brace-text');
  if (!txt) return;
  const midAlong = geo.startX ? (geo.along / 2) : (geo.along / 2);
  if (side === 'left') {
    txt.style.left = (geo.baseX - geo.depth - 8 - geo.minX) + 'px';
    txt.style.top = (geo.startY + midAlong - geo.minY) + 'px';
  } else if (side === 'right') {
    txt.style.left = (geo.baseX + geo.depth + 8 - geo.minX) + 'px';
    txt.style.top = (geo.startY + midAlong - geo.minY) + 'px';
  } else {
    txt.style.left = (geo.startX + midAlong - geo.minX) + 'px';
    txt.style.top = (geo.baseY + geo.depth + 8 - geo.minY) + 'px';
  }
}
function renderNodeBraces() {
  if (state.mode !== 'node' || !nodeDomReady) return;
  const layer = ensureGroupBraceLayer();
  if (!layer) return;
  const alive = new Set();
  (state.nodeGroups || []).forEach(g => {
    const braces = groupBraces(g);
    const b = groupBounds(g);
    if (!b) return;
    NG_BRACE_SIDES.forEach(side => {
      if (!braces[side]) return;
      const key = g.id + '::' + side;
      alive.add(key);
      let el = layer.querySelector('.ng-brace[data-group-id="' + nodeGroupEsc(g.id) + '"][data-side="' + side + '"]');
      if (!el) { el = createBraceEl(g, side); layer.appendChild(el); }
      layoutBraceEl(el, g, side, b);
      const txt = el.querySelector('.ng-brace-text');
      if (!txt) return;
      const editing = state.ngBraceEdit && state.ngBraceEdit.groupId === g.id && state.ngBraceEdit.side === side;
      if (editing || txt.getAttribute('contenteditable') === 'true') return;
      const want = groupBraceText(g, side);
      if (txt.textContent !== want) txt.textContent = want;
      txt.classList.toggle('empty', !String(want || '').trim());
    });
  });
  Array.from(layer.children).forEach(el => {
    if (!alive.has(el.dataset.groupId + '::' + el.dataset.side)) el.remove();
  });
}
/* 拖动过程中只改几何，不重建 DOM（否则正在输入的文字会被销毁） */
function syncGroupBraces() {
  if (state.mode !== 'node' || !nodeDomReady) return;
  const layer = document.getElementById('nodeGroupBraceLayer');
  if (!layer) return;
  (state.nodeGroups || []).forEach(g => {
    NG_BRACE_SIDES.forEach(side => {
      if (!groupHasBrace(g, side)) return;
      const el = layer.querySelector('.ng-brace[data-group-id="' + nodeGroupEsc(g.id) + '"][data-side="' + side + '"]');
      if (!el) return;
      const b = groupBounds(g);
      if (b) layoutBraceEl(el, g, side, b);
    });
  });
}
function toggleGroupBrace(groupId, side) {
  const g = getNodeGroupById(groupId);
  if (!g || NG_BRACE_SIDES.indexOf(side) < 0) return false;
  const braces = groupBraces(g);
  if (braces[side]) {
    histCapture('删除分组说明');
    delete braces[side];
    saveNodes();
    renderNodeGroups();
    histCommit();
    showToast('已移除分组' + NG_BRACE_META[side].label + '的说明');
    return true;
  }
  histCapture('添加分组说明');
  braces[side] = { text: '' };
  saveNodes();
  renderNodeGroups();
  histCommit();
  setTimeout(() => startGroupBraceEdit(groupId, side), 60);
  showToast('分组' + NG_BRACE_META[side].label + '已加大括号，直接输入说明文字');
  return true;
}
function startGroupBraceEdit(groupId, side) {
  const g = getNodeGroupById(groupId);
  const el = document.querySelector('.ng-brace[data-group-id="' + nodeGroupEsc(groupId) + '"][data-side="' + side + '"] .ng-brace-text');
  if (!g || !el) return false;
  if (el.getAttribute('contenteditable') === 'true') { try { el.focus(); } catch (e) {} return true; }
  state.ngBraceEdit = { groupId: groupId, side: side };
  el.setAttribute('contenteditable', 'true');
  el.classList.add('editing');
  el.classList.remove('empty');
  el.focus();
  try {
    const r = document.createRange();
    r.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(r);
  } catch (e) {}
  return true;
}
function commitGroupBraceText(groupId, side, el) {
  const g = getNodeGroupById(groupId);
  if (!g || !el) return;
  const cancel = el.dataset.cancel === '1';
  delete el.dataset.cancel;
  el.removeAttribute('contenteditable');
  el.classList.remove('editing');
  if (state.ngBraceEdit && state.ngBraceEdit.groupId === groupId && state.ngBraceEdit.side === side) state.ngBraceEdit = null;
  const braces = groupBraces(g);
  const prev = groupBraceText(g, side);
  if (!braces[side]) { el.textContent = ''; return; }
  const next = cancel ? prev : String(el.textContent || '').replace(/\u00a0/g, ' ').replace(/\s+$/,'').slice(0, 300);
  if (cancel || next === prev) {
    el.textContent = prev;
    el.classList.toggle('empty', !prev.trim());
    return;
  }
  histCapture(next ? '编辑分组说明' : '清空分组说明');
  braces[side].text = next;
  saveNodes();
  histCommit();
  renderNodeGroups();
}
function setGroupBraceText(groupId, side, text) {
  const g = getNodeGroupById(groupId);
  if (!g || NG_BRACE_SIDES.indexOf(side) < 0) return false;
  const braces = groupBraces(g);
  if (!braces[side]) braces[side] = { text: '' };
  braces[side].text = String(text == null ? '' : text).slice(0, 300);
  saveNodes();
  renderNodeGroups();
  return true;
}
function openGroupBraceMenu(groupId, clientX, clientY) {
  const g = getNodeGroupById(groupId);
  const menu = document.getElementById('nodeMenu');
  const viewport = document.getElementById('nodeViewport');
  if (!g || !menu || !viewport) return;
  const braces = groupBraces(g);
  let html = '<div class="menu-head">' +
    '<button type="button" class="menu-back" data-menu="close-batch" title="关闭">✕</button>' +
    '<span class="menu-title">分组说明 · 大括号</span></div>' +
    '<div class="menu-hint">大括号贴在分组的左 / 右 / 下三条边上，括号外侧可以写一句总结。点已有的那条可以移除。</div>';
  NG_BRACE_SIDES.forEach(side => {
    const on = !!braces[side];
    html += '<button type="button" class="menu-row" data-menu="brace-toggle" data-side="' + side + '">' +
      '<span class="mi">' + (on ? '✓' : '＋') + '</span>' +
      '<span class="mt">' + NG_BRACE_META[side].icon + ' ' + NG_BRACE_META[side].label + '</span>' +
      '<span class="mv' + (on ? ' current' : '') + '">' + (on ? '已有 · 点此移除' : '未添加') + '</span></button>';
  });
  menu.innerHTML = html;
  menu.dataset.view = 'group-brace';
  menu.dataset.groupId = groupId;
  menu.style.display = '';
  placeNodeMenu(menu, viewport, clientX || 200, clientY || 200);
}
/* 编辑中点到别处也要收尾（contenteditable 不会因为点到普通 div 而失焦） */
document.addEventListener('pointerdown', (e) => {
  const cur = state.ngBraceEdit;
  if (!cur) return;
  const el = document.querySelector('.ng-brace[data-group-id="' + nodeGroupEsc(cur.groupId) + '"][data-side="' + cur.side + '"] .ng-brace-text');
  if (!el) { state.ngBraceEdit = null; return; }
  if (e.target === el || (el.contains && el.contains(e.target))) return;
  if (el.getAttribute('contenteditable') === 'true') el.blur();
}, true);
function selectNodeGroup(id) {"""

s = sub(s, "function selectNodeGroup(id) {", BRACE_CODE, "brace-code")

# ---------------------------------------------------------------- 7 组头按钮事件
s = sub(s,
        "      if (btn.dataset.ng === 'summary') { startGroupSummaryDrag(e, groupId); return; }",
        """      if (btn.dataset.ng === 'summary') { startGroupSummaryDrag(e, groupId); return; }
      if (btn.dataset.ng === 'brace') {
        e.stopPropagation();
        if (e.preventDefault) e.preventDefault();
        selectNodeGroup(groupId);
        openGroupBraceMenu(groupId, e.clientX, e.clientY);
        return;
      }""",
        "ng-brace-btn")

# ---------------------------------------------------------------- 8 菜单点击
s = sub(s,
        "    if (act === 'close-batch') { closeNodeMenu(); return; }",
        """    if (act === 'close-batch') { closeNodeMenu(); return; }
    if (act === 'brace-toggle') {
      const gid = menu.dataset.groupId || '';
      const side = btn.dataset.side;
      closeNodeMenu();
      toggleGroupBrace(gid, side);
      return;
    }""",
        "menu-brace-toggle")

# ---------------------------------------------------------------- 9 总结节点：落点决定连线方式
SUMMARY_HELPERS = r"""
/* ---------- 第 142 条：总结节点的连线方式由「松手位置」决定 ---------- */
/* 落点相对组框在哪个方向（落在框内时取最近的一条边） */
function groupDropSide(b, world) {
  if (!b) return 'right';
  if (!world || !isFinite(world.x) || !isFinite(world.y)) return 'right';
  if (world.x < b.x) return 'left';
  if (world.x > b.x + b.w) return 'right';
  if (world.y < b.y) return 'top';
  if (world.y > b.y + b.h) return 'bottom';
  const dl = world.x - b.x, dr = b.x + b.w - world.x;
  const dt = world.y - b.y, db = b.y + b.h - world.y;
  const m = Math.min(dl, dr, dt, db);
  if (m === dl) return 'left';
  if (m === dr) return 'right';
  if (m === dt) return 'top';
  return 'bottom';
}
/* 节点所有连接点在世界坐标里的位置（与 getAnchorPoint 的兜底算法同一套） */
function nodePortWorldPoints(node) {
  if (!node) return [];
  const m = nodeMeasure(node);
  return getNodePorts(node).map(p => {
    const pos = Math.min(0.92, Math.max(0.08, typeof p.pos === 'number' ? p.pos : 0.5));
    let x = node.x, y = node.y;
    if (p.side === 'top') { x = node.x + m.w * pos; y = node.y; }
    else if (p.side === 'bottom') { x = node.x + m.w * pos; y = node.y + m.h; }
    else if (p.side === 'left') { x = node.x; y = node.y + m.h * pos; }
    else { x = node.x + m.w; y = node.y + m.h * pos; }
    return { side: p.side, portId: p.id, x: x, y: y };
  });
}
/* 最短连线原则：在两边所有连接点里取距离最近的一对 */
function nearestPortPair(a, b) {
  const pa = nodePortWorldPoints(a), pb = nodePortWorldPoints(b);
  let best = null, bd = Infinity;
  pa.forEach(x => pb.forEach(y => {
    const d = Math.hypot(x.x - y.x, x.y - y.y);
    if (d < bd) { bd = d; best = { a: x, b: y, dist: d }; }
  }));
  return best;
}
/* parent → child 的父子线，两端都吸附到最近的一对连接点 */
function connectSummaryByNearestPort(parent, child) {
  if (!parent || !child || parent.id === child.id) return false;
  if (!canBeParent(parent.id, child.id)) return false;
  const pair = nearestPortPair(parent, child);
  if (!pair) return false;
  const old = getParentNodeId(child.id);
  if (old && old !== parent.id) {
    const oe = state.edges.find(e => isParentEdge(e) && e.to === child.id);
    if (oe) oe.kind = 'relation';
  }
  let edge = state.edges.find(e => (e.from === parent.id && e.to === child.id) || (e.from === child.id && e.to === parent.id));
  if (!edge) {
    edge = {
      id: generateId(), from: parent.id, to: child.id,
      fromSide: pair.a.side, fromPort: pair.a.portId,
      toSide: pair.b.side, toPort: pair.b.portId,
      kind: 'parent', label: ''
    };
    state.edges.push(edge);
  } else {
    edge.from = parent.id; edge.to = child.id;
    edge.fromSide = pair.a.side; edge.fromPort = pair.a.portId;
    edge.toSide = pair.b.side; edge.toPort = pair.b.portId;
    edge.kind = 'parent';
  }
  return true;
}
function createGroupSummaryNode(groupId, world) {"""

s = sub(s, "function createGroupSummaryNode(groupId, world) {", SUMMARY_HELPERS, "summary-helpers")

SUM_OLD = """  histCapture('创建分组总结');
  const node = makeNode(x, y, 'content');
  node.title = (g.name || '分组') + ' 总结';
  node.content = '';
  state.nodes.push(node);
  appendNodeEl(node);
  const idset = new Set(ids);
  let roots = ids.filter(id => { const p = getParentNodeId(id); return !p || !idset.has(p); });
  if (!roots.length) roots = ids.slice();
  let linked = 0;
  roots.forEach(id => { const r = setNodeParent(id, node.id); if (r && r.ok) linked++; });"""
SUM_NEW = """  /* 第 142 条：落点在组的左边 → 保持原有逻辑（把成员挂成它的下级）；
     落在右边 / 上边 / 下边 → 走最短连线原则，两端各取最近的那个连接点 */
  const dropSide = groupDropSide(b, world);
  const useNearest = dropSide !== 'left';
  histCapture('创建分组总结');
  const node = makeNode(x, y, 'content');
  node.title = (g.name || '分组') + ' 总结';
  node.content = '';
  state.nodes.push(node);
  appendNodeEl(node);
  const idset = new Set(ids);
  let roots = ids.filter(id => { const p = getParentNodeId(id); return !p || !idset.has(p); });
  if (!roots.length) roots = ids.slice();
  let linked = 0;
  if (useNearest) {
    roots.forEach(id => {
      const c = state.nodes.find(n => n.id === id);
      if (c && connectSummaryByNearestPort(node, c)) linked++;
    });
  } else {
    roots.forEach(id => { const r = setNodeParent(id, node.id); if (r && r.ok) linked++; });
  }"""
s = sub(s, SUM_OLD, SUM_NEW, "summary-drop-side")

s = sub(s,
        "  showToast('已生成总结节点，' + linked + ' 个成员挂到它下面');",
        """  showToast(useNearest
    ? '已生成总结节点：' + linked + ' 个成员按最近连接点连到它'
    : '已生成总结节点，' + linked + ' 个成员挂到它下面');""",
        "summary-toast")

# ---------------------------------------------------------------- 10 测试钩子
HOOK_OLD = """        edgeList: function () { return state.edges.map(function (e) { return { from: e.from, to: e.to, kind: e.kind }; }); },"""
HOOK_NEW = """        edgeList: function () {
          return state.edges.map(function (e) {
            return {
              from: e.from, to: e.to, kind: e.kind,
              fromSide: e.fromSide, fromPort: e.fromPort,
              toSide: e.toSide, toPort: e.toPort
            };
          });
        },
        /* 第 142 条：分组大括号 */
        braces: function (id) {
          var g = getNodeGroupById(id); if (!g) return null;
          var out = {};
          NG_BRACE_SIDES.forEach(function (side) { if (groupHasBrace(g, side)) out[side] = groupBraceText(g, side); });
          return out;
        },
        braceAdd: function (id, side) { return toggleGroupBrace(id, side); },
        braceRemove: function (id, side) {
          var g = getNodeGroupById(id);
          if (!g || !groupHasBrace(g, side)) return false;
          var braces = groupBraces(g);
          delete braces[side];
          saveNodes(); renderNodeGroups(); return true;
        },
        braceText: function (id, side) {
          var g = getNodeGroupById(id); if (!g) return null;
          return groupBraceText(g, side);
        },
        braceSetText: function (id, side, text) { return setGroupBraceText(id, side, text); },
        braceRect: function (id, side) {
          var el = document.querySelector('.ng-brace[data-group-id="' + id + '"][data-side="' + side + '"]');
          if (!el) return null;
          var r = el.getBoundingClientRect();
          var t = el.querySelector('.ng-brace-text');
          var tr = t ? t.getBoundingClientRect() : null;
          var p = el.querySelector('.ng-brace-path');
          return {
            l: r.left, t: r.top, w: r.width, h: r.height,
            d: p ? p.getAttribute('d') : null,
            text: t ? t.textContent : null,
            textRect: tr ? { l: tr.left, t: tr.top, w: tr.width, h: tr.height } : null
          };
        },
        dropSide: function (id, x, y) { var g = getNodeGroupById(id); return g ? groupDropSide(groupBounds(g), x == null ? null : { x: x, y: y }) : null; },
        nearestPorts: function (a, b) {
          var na = state.nodes.find(function (n) { return n.id === a; });
          var nb = state.nodes.find(function (n) { return n.id === b; });
          if (!na || !nb) return null;
          var pair = nearestPortPair(na, nb);
          return pair ? { from: pair.a.side, fromPort: pair.a.portId, to: pair.b.side, toPort: pair.b.portId, dist: pair.dist } : null;
        },"""
s = sub(s, HOOK_OLD, HOOK_NEW, "hooks")

io.open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n"))
print("patched: %d -> %d bytes" % (orig_len, len(s)))
