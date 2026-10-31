# -*- coding: utf-8 -*-
"""第 143 条：去掉节点头部抓手（⠿）+ 导出弹窗重排（可折叠、不遮挡）回归

覆盖：
  A 节点标题前不再渲染 ⠿ 抓手；标题区仍可拖动
  B 抓手改为标题区承载：节点状态提示仍挂在标题区
  C 导出弹窗默认高度不超出视口、不再有说明性文字
  D 三个折叠区（页面规格 / 导出页面 / 图片占用）默认收起且可展开
  E 折叠区摘要在收起时显示当前档位与已选页面数
  F 底部三个导出按钮始终可见可点（不被裁切）
  G 手机端 390×844：弹窗在视口内、正文可滚动、按钮可点
  H 全程无 JS 报错
"""
import os
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")
SHOTS = os.path.join(BASE, "tests", "_shots")

RES = {"pass": 0, "fail": 0}


def check(ok, label, extra=None):
    if ok:
        RES["pass"] += 1
        print("  ok   ", label)
    else:
        RES["fail"] += 1
        print("  FAIL ", label, "" if extra is None else str(extra)[:300])


def enter_node(page):
    page.click("#nodeModeBtn")
    page.wait_for_selector(".node-viewport", timeout=20000)
    page.wait_for_timeout(500)


def add_node(page, x, y, typ, title):
    return page.evaluate(
        "([x,y,t,ti]) => __T.node().addNode(x,y,t,ti)", [x, y, typ, title])


def clear(page):
    page.evaluate("() => __T.node().clearAll()")
    page.wait_for_timeout(200)


def open_export(page):
    page.click("#nodeExportBtn")
    page.wait_for_timeout(400)


def box(page, sel):
    el = page.query_selector(sel)
    return el.bounding_box() if el else None


def pos(page, nid):
    return page.evaluate(
        "(id) => { const p = __T.node().positions().find(x => x.id === id); return p ? [p.x, p.y] : null; }", nid)


def run(ctx_label, page, vw, vh, shot_name, mobile=False):
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL, timeout=90000)
    page.wait_for_timeout(1400)
    enter_node(page)
    clear(page)
    tid = add_node(page, 220, 200, "title", "根标题")
    add_node(page, 220, 400, "content", "成员甲")
    page.wait_for_timeout(250)

    print(f"[{ctx_label}] A 抓手已移除")
    check(page.query_selector_all(".node-item .node-grip").__len__() == 0,
          "节点内无 .node-grip 元素")
    check(page.evaluate("() => document.querySelectorAll('.node-head').length >= 2"),
          "标题区（.node-head）存在")
    txt = page.evaluate("() => { const h = document.querySelector('.node-item .node-head'); return h ? h.textContent : ''; }")
    check("⠿" not in (txt or ""), "标题区文本不含 ⠿ 字符", txt)

    print(f"[{ctx_label}] B 标题区仍可拖动 + 状态提示")
    before = pos(page, tid)
    hb = box(page, f'.node-item[data-node-id="{tid}"] .node-title-text')
    page.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2)
    page.mouse.down()
    page.mouse.move(hb["x"] + hb["width"] / 2 + 70, hb["y"] + hb["height"] / 2 + 45, steps=20)
    page.mouse.up()
    page.wait_for_timeout(300)
    after = pos(page, tid)
    check(after is not None and before is not None and (after[0] != before[0] or after[1] != before[1]),
          "拖标题文字可移动节点（超过阈值）", [before, after])
    check(page.evaluate(f"() => !!document.querySelector('.node-item[data-node-id=\"{tid}\"] .node-head').title"),
          "状态提示挂在标题区 title 上")
    # 单击标题仍应进入光标编辑（不位移）
    b2 = pos(page, tid)
    hb2 = box(page, f'.node-item[data-node-id="{tid}"] .node-title-text')
    if mobile:
        page.tap(f'.node-item[data-node-id="{tid}"] .node-title-text')
    else:
        page.mouse.click(hb2["x"] + hb2["width"] / 2, hb2["y"] + hb2["height"] / 2)
    page.wait_for_timeout(250)
    a2 = pos(page, tid)
    check(b2 == a2, "单击标题不移动节点", [b2, a2])
    foc = page.evaluate("() => { const el = document.activeElement; return el && el.className ? String(el.className) : ''; }")
    check("node-title-text" in (foc or ""), "单击标题后获得焦点（可编辑）", foc)

    print(f"[{ctx_label}] C 弹窗不超高、无说明文字")
    open_export(page)
    pb = box(page, "#nodeExportModal")
    check(pb is not None, "弹窗已打开")
    check(pb["y"] >= 0 and pb["y"] + pb["height"] <= vh + 1,
          "弹窗完整落在视口内", [round(pb["y"], 1), round(pb["height"], 1), vh])
    check(pb["height"] <= vh - 60, "弹窗高度受视口约束", round(pb["height"], 1))
    check(page.evaluate("() => document.querySelectorAll('#nodeExportModal .nem-note').length") == 0,
          "说明性文字（.nem-note）已全部移除")
    body_txt = page.evaluate("() => document.querySelector('#nodeExportModal').textContent")
    check("可导出" not in body_txt and "勾选" not in body_txt and "落款文字，如" not in body_txt,
          "面板内无解释性长句", body_txt[:120])

    print(f"[{ctx_label}] D 折叠区默认收起且可展开")
    nsec = page.evaluate("() => document.querySelectorAll('#nodeExportModal details.nem-sec').length")
    check(nsec == 3, "三个折叠区", nsec)
    check(page.evaluate("() => document.querySelectorAll('#nodeExportModal details.nem-sec[open]').length") == 0,
          "默认全部收起")
    # 展开页面规格
    page.click("#nodeExportModal details.nem-sec:nth-of-type(1) > summary")
    page.wait_for_timeout(250)
    check(page.evaluate("() => document.querySelectorAll('#nodeExportModal details.nem-sec')[0].open"),
          "点击标题可展开页面规格")
    check(page.is_visible("#nemPageSpec"), "展开后规格下拉可见")
    # 收起
    page.click("#nodeExportModal details.nem-sec:nth-of-type(1) > summary")
    page.wait_for_timeout(200)
    check(not page.evaluate("() => document.querySelectorAll('#nodeExportModal details.nem-sec')[0].open"),
          "再次点击可收起")

    print(f"[{ctx_label}] E 摘要文案")
    brief = page.evaluate("() => document.getElementById('nemPageSpecBrief').textContent")
    check(bool(brief) and len(brief) > 0, "页面规格摘要非空", brief)
    pbrief = page.evaluate("() => document.getElementById('nemPagesBrief').textContent")
    check("全部" in pbrief or "/" in pbrief, "页面数摘要显示全部/已选数", pbrief)
    page.evaluate("() => { const b = document.querySelector('#nemPages input[type=checkbox]'); if (b) { b.checked = false; b.dispatchEvent(new Event('change', {bubbles:true})); } }")
    page.wait_for_timeout(200)
    pbrief2 = page.evaluate("() => document.getElementById('nemPagesBrief').textContent")
    check("/" in pbrief2, "取消勾选后摘要变为 n / m", pbrief2)

    print(f"[{ctx_label}] F 底部按钮始终可见")
    for bid in ("#nemCurrentBtn", "#nemSelectedBtn", "#nemAllBtn"):
        bb = box(page, bid)
        ok = bb is not None and bb["y"] >= 0 and bb["y"] + bb["height"] <= vh + 1
        check(ok, f"{bid} 在视口内", None if bb is None else [round(bb["y"], 1), round(bb["height"], 1)])
        check(page.is_visible(bid), f"{bid} 可见")
    check(page.is_visible("#nemCancelBtn"), "关闭按钮可见")

    print(f"[{ctx_label}] F2 三个折叠区全展开也不遮挡")
    page.evaluate("() => document.querySelectorAll('#nodeExportModal details.nem-sec').forEach(d => { d.open = true; })")
    page.wait_for_timeout(300)
    pb2 = box(page, "#nodeExportModal")
    check(pb2["y"] + pb2["height"] <= vh + 1, "全展开后弹窗底部不超出视口",
          [round(pb2["y"], 1), round(pb2["height"], 1), vh])
    sc = page.evaluate("() => { const b = document.querySelector('#nodeExportModal .nem-body'); return [b.scrollHeight, b.clientHeight]; }")
    check(sc[0] >= sc[1], "正文区高度受限（内容超长时内部滚动）", sc)
    for bid in ("#nemCurrentBtn", "#nemSelectedBtn", "#nemAllBtn"):
        bb = box(page, bid)
        check(bb is not None and bb["y"] + bb["height"] <= vh + 1, f"全展开后 {bid} 仍在视口内",
              None if bb is None else round(bb["y"] + bb["height"], 1))
    page.evaluate("() => document.querySelectorAll('#nodeExportModal details.nem-sec').forEach(d => { d.open = false; })")
    page.wait_for_timeout(200)

    page.evaluate("() => { const p = document.getElementById('nodeExportModal'); p.scrollTop = 0; }")
    page.screenshot(path=os.path.join(SHOTS, shot_name))

    print(f"[{ctx_label}] G 关闭弹窗")
    page.click("#nemCancelBtn")
    page.wait_for_timeout(250)
    check(page.evaluate("() => getComputedStyle(document.getElementById('nodeExportModal')).display") == "none",
          "点 ✕ 可关闭")

    print(f"[{ctx_label}] H 导出动作可用")
    open_export(page)
    page.evaluate("() => { const b = document.querySelector('#nemPages input[type=checkbox]'); if (b) b.checked = true; }")
    page.click("#nemCurrentBtn")
    page.wait_for_timeout(2600)
    check(page.evaluate("() => getComputedStyle(document.getElementById('nodeExportModal')).display") == "none",
          "点「当前页」后自动收起弹窗")
    toast = page.evaluate("() => { const t = document.querySelector('.toast, #toast'); return t ? t.textContent : ''; }")
    check("导出" in (toast or ""), "出现导出结果提示", toast)

    print(f"[{ctx_label}] I 无 JS 报错")
    check(len(errs) == 0, "无 pageerror", errs)


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        run("桌面", page, 1440, 900, "p23_export_desktop.png")
        ctx.close()

        ctx2 = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page2 = ctx2.new_page()
        run("手机", page2, 390, 844, "p23_export_mobile.png", mobile=True)
        ctx2.close()
        b.close()
    print(f"\n通过 {RES['pass']} / 失败 {RES['fail']}")
    return 0 if RES["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
