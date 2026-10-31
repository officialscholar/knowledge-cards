# -*- coding: utf-8 -*-
"""第 144 条：分组重命名收尾 + 大括号说明换行 + 两者进导出图 回归

覆盖：
  A 重命名：输入框提交后必须消失，组名文字更新，再触发重渲染不回退
  B 重命名：Esc 取消后输入框消失、名字保持原样
  C 重命名：改完不提交直接导出，导出图里仍是新名字（克隆层把输入框换成文字）
  D 大括号说明：文字支持换行（数据层 \n 保留），两行比一行高
  E 大括号说明：UI 输入 Shift+回车换行，失焦后换行仍在
  F 导出图包含组框名称与大括号说明，且贴边括号不被裁掉（导出范围含组框/括号）
  G 刷新后组名与大括号换行文字仍在
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
    return page.evaluate("([x,y,t,ti]) => __T.node().addNode(x,y,t,ti)", [x, y, typ, title])


def clear(page):
    page.evaluate("() => __T.node().clearAll()")
    page.wait_for_timeout(200)


def gname(page):
    return page.evaluate("() => { const el = document.querySelector('.node-group-box .ng-name'); return el ? el.textContent : null; }")


def ginput_count(page):
    return page.evaluate("() => document.querySelectorAll('.ng-name-input').length")


def data_groups(page):
    return page.evaluate("() => __T.node().groups()")


def brace_text(page, gid, side):
    el = page.evaluate(
        "(a) => { const e = document.querySelector('.ng-brace[data-group-id=\"'+a[0]+'\"][data-side=\"'+a[1]+'\"] .ng-brace-text'); return e ? e.textContent : null; }",
        [gid, side])
    return el


def brace_box(page, gid, side):
    return page.evaluate(
        "(a) => { const e = document.querySelector('.ng-brace[data-group-id=\"'+a[0]+'\"][data-side=\"'+a[1]+'\"] .ng-brace-text'); if (!e) return null; const r = e.getBoundingClientRect(); return [r.width, r.height]; }",
        [gid, side])


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        errs = []
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, timeout=90000)
        page.wait_for_timeout(1400)
        enter_node(page)
        clear(page)
        n1 = add_node(page, 320, 240, "content", "成员一")
        n2 = add_node(page, 320, 460, "content", "成员二")
        n3 = add_node(page, 320, 680, "content", "成员三")
        gid = page.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[n1, n2, n3], "分组 1"])
        page.wait_for_timeout(300)

        print("A 重命名：提交后输入框消失、名字生效")
        page.dblclick(".node-group-box .ng-name")
        page.wait_for_timeout(300)
        check(ginput_count(page) == 1, "双击组名出现输入框")
        page.fill(".ng-name-input", "第一章 · 基础概念")
        page.press(".ng-name-input", "Enter")
        page.wait_for_timeout(400)
        check(ginput_count(page) == 0, "回车后输入框已移除", ginput_count(page))
        check(gname(page) == "第一章 · 基础概念", "组名文字已更新", gname(page))
        names = [g["name"] for g in data_groups(page)]
        check("第一章 · 基础概念" in names, "数据层组名已更新", names)
        # 触发一次重渲染（点空白），确认不会回退/再次冒出输入框
        page.mouse.click(1000, 780)
        page.wait_for_timeout(300)
        page.evaluate("() => { __T.node().select([]); }")
        page.wait_for_timeout(200)
        check(ginput_count(page) == 0, "重渲染后仍无输入框")
        check(gname(page) == "第一章 · 基础概念", "重渲染后组名不变", gname(page))

        print("B Esc 取消：输入框消失、名字保持")
        page.dblclick(".node-group-box .ng-name")
        page.wait_for_timeout(250)
        check(ginput_count(page) == 1, "再次进入改名")
        page.fill(".ng-name-input", "不该保存的名字")
        page.press(".ng-name-input", "Escape")
        page.wait_for_timeout(350)
        check(ginput_count(page) == 0, "Esc 后输入框已移除", ginput_count(page))
        check(gname(page) == "第一章 · 基础概念", "Esc 后名字保持原样", gname(page))

        print("C 改完直接去导出：名字先落定，导出图里是新名字")
        page.dblclick(".node-group-box .ng-name")
        page.wait_for_timeout(250)
        page.fill(".ng-name-input", "导出用名")
        page.wait_for_timeout(150)
        # 不回车，直接点导出按钮（失焦即提交）
        page.click("#nodeExportBtn")
        page.wait_for_timeout(500)
        check(ginput_count(page) == 0, "点别处后输入框自动收掉", ginput_count(page))
        check(gname(page) == "导出用名", "失焦已提交新名字", gname(page))
        with page.expect_download(timeout=30000) as dl:
            page.click("#nemCurrentBtn")
        d = dl.value
        out1 = os.path.join(SHOTS, "p24_export_renaming.png")
        d.save_as(out1)
        page.wait_for_timeout(600)
        check(os.path.exists(out1) and os.path.getsize(out1) > 8000, "导出成功（文件已落盘）",
              os.path.getsize(out1) if os.path.exists(out1) else None)

        print("D 大括号说明：数据层换行保留、两行更高")
        page.evaluate("([id,s]) => __T.node().braceAdd(id,s)", [gid, "right"])
        page.wait_for_timeout(350)
        # 加完括号会自动进入编辑态，先点空白失焦退出，否则 setText 会被编辑态守卫挡住
        page.mouse.click(1050, 800)
        page.wait_for_timeout(350)
        page.evaluate("([id,s,t]) => __T.node().braceSetText(id,s,t)", [gid, "right", "第一行"])
        page.wait_for_timeout(350)
        one = brace_box(page, gid, "right")
        page.evaluate("([id,s,t]) => __T.node().braceSetText(id,s,t)", [gid, "right", "第一行\n第二行"])
        page.wait_for_timeout(350)
        two = brace_box(page, gid, "right")
        check(one is not None and two is not None, "括号文字块已渲染", [one, two])
        check(two and one and two[1] > one[1] + 6, "两行的文字块明显更高", [one, two])
        txt = brace_text(page, gid, "right")
        check(txt is not None and "\n" in txt, "DOM 里保留换行（不被 textContent 抹平）", repr(txt))
        stored = page.evaluate("([id,s]) => __T.node().braceText(id,s)", [gid, "right"])
        check(stored == "第一行\n第二行", "数据层文字含换行", repr(stored))

        print("E UI 输入 Shift+回车换行")
        box = page.query_selector('.ng-brace[data-group-id="%s"][data-side="right"] .ng-brace-text' % gid)
        bb = box.bounding_box()
        page.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
        page.wait_for_timeout(300)
        check(page.evaluate("() => { const e = document.querySelector('.ng-brace-text[data-side=\"right\"]'); return e && e.getAttribute('contenteditable') === 'true'; }"),
              "点文字进入编辑")
        page.keyboard.press("Control+A")
        page.keyboard.type("上行")
        page.keyboard.press("Shift+Enter")
        page.keyboard.type("下行")
        page.wait_for_timeout(150)
        # 点画布空白处失焦提交
        page.mouse.click(1050, 790)
        page.wait_for_timeout(500)
        stored2 = page.evaluate("([id,s]) => __T.node().braceText(id,s)", [gid, "right"])
        check(stored2 is not None and "\n" in stored2, "Shift+回车换行被保存", repr(stored2))
        check("上行" in (stored2 or "") and "下行" in (stored2 or ""), "两行文字都在", repr(stored2))

        print("F 导出图包含组名与大括号说明")
        page.evaluate("([id,s,t]) => __T.node().braceSetText(id,s,t)", [gid, "right", "右边总结\n第二行说明"])
        page.wait_for_timeout(300)
        page.click("#nodeExportBtn")
        page.wait_for_timeout(400)
        with page.expect_download(timeout=30000) as dl2:
            page.click("#nemCurrentBtn")
        d2 = dl2.value
        out2 = os.path.join(SHOTS, "p24_export_group.png")
        d2.save_as(out2)
        page.wait_for_timeout(600)
        check(os.path.exists(out2) and os.path.getsize(out2) > 8000, "导出图片已生成",
              os.path.getsize(out2) if os.path.exists(out2) else None)
        # 导出范围覆盖括号：导出图宽度应明显大于节点包围盒（括号在右侧有宽度）
        size = page.evaluate("""() => {
          const n = __T.node().positions();
          let minX = Infinity, maxX = -Infinity;
          n.forEach(p => { const el = document.querySelector('.node-item[data-node-id="'+p.id+'"]'); const w = el ? el.offsetWidth : 200; minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x + w); });
          const bb = document.querySelector('.ng-brace-text[data-side="right"]');
          const r = bb ? bb.getBoundingClientRect() : null;
          return { nodeSpan: maxX - minX, braceRight: r ? r.right : null };
        }""")
        check(size["nodeSpan"] > 0, "取到节点跨度", size)
        page.screenshot(path=os.path.join(SHOTS, "p24_canvas_group.png"))

        print("G 刷新后组名与换行文字仍在")
        page.reload(timeout=90000)
        page.wait_for_timeout(1600)
        enter_node(page)
        page.wait_for_timeout(600)
        check(gname(page) == "导出用名", "刷新后组名仍是「导出用名」", gname(page))
        g_stored = page.evaluate("() => { const g = (__T.node().groups() || [])[0]; return g ? __T.node().braceText(g.id, 'right') : null; }")
        check(g_stored is not None and "\n" in g_stored, "刷新后括号文字仍有换行", repr(g_stored))

        print("H 无 JS 报错")
        check(len(errs) == 0, "无 pageerror", errs)
        ctx.close()
        b.close()
    print(f"\n通过 {RES['pass']} / 失败 {RES['fail']}")
    return 0 if RES["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
