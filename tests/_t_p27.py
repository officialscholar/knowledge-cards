# -*- coding: utf-8 -*-
"""第 147 条回归：节点圆角 + 节点编辑浮动面板

覆盖：
  A 圆角：默认 14px；可设 0（直角）/ 中间值；超过短边一半被夹到上限；上限随尺寸变化
  B 面板开关：右键菜单「编辑面板」、Ctrl+E 呼出 / 再按关闭、✕ 关闭、Esc 关闭
  C 面板拖动：拖标题栏移动、位置被夹在画布内、拖动位置被记住
  D 面板控件：宽度滑块 / 数字联动、圆角滑块 / 数字联动、标题对齐与加粗按钮、恢复默认、跟随选中
  E 持久化：刷新后 width / radius 保留，没设过的节点仍回落 14px
  F 撤销：一次连续拖动只留一条记录，撤销回到拖动前
  G 导出图片：设了圆角仍能导出 PNG
  H 手机端 390×844：面板不越界、控件可用
  I 全程无 JS 报错
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


def radius_of(page, nid):
    return page.evaluate("(id) => __T.node().radius(id)", nid)


def computed_radius(page, nid):
    return page.evaluate("(id) => __T.node().borderRadiusPx(id)", nid)


def radius_max(page, nid):
    return page.evaluate("(id) => __T.node().radiusMax(id)", nid)


def panel_open(page):
    return page.evaluate("() => __T.node().panelOpen()")


def panel_values(page):
    return page.evaluate("() => __T.node().panelValues()")


def node_metrics(page, nid):
    return page.evaluate("""(id) => {
      const e = document.querySelector('.node-item[data-node-id="' + id + '"]');
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return { w: e.offsetWidth, h: e.offsetHeight, left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    }""", nid)


def panel_rect(page):
    return page.evaluate("""() => {
      const p = document.getElementById('nodeEditPanel');
      const r = p.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height, display: p.style.display,
               vw: window.innerWidth, vh: window.innerHeight };
    }""")


def drag(page, x1, y1, x2, y2, steps=10):
    page.mouse.move(x1, y1)
    page.mouse.down()
    page.mouse.move(x2, y2, steps=steps)
    page.mouse.up()


def run(browser, mobile=False):
    label = "手机 390×844" if mobile else "桌面 1440×900"
    vp = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900}
    ctx = browser.new_context(viewport=vp)
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL, timeout=90000)
    page.wait_for_timeout(1300)
    enter_node(page)
    page.evaluate("() => __T.node().clearAll()")
    page.wait_for_timeout(200)

    # ---------------- A 圆角 ----------------
    print(f"[{label}] A 圆角（0 ~ 短边一半）")
    base_x = 60 if mobile else 420
    a = add_node(page, base_x, 120, "content", "圆角甲")
    b = add_node(page, base_x, 380, "content", "圆角乙")
    page.wait_for_timeout(350)
    check(radius_of(page, a) is None, "新节点没有存圆角（回落到默认）", radius_of(page, a))
    check(abs(computed_radius(page, a) - 14) < 0.6, "默认渲染为 14px 圆角", computed_radius(page, a))
    m = node_metrics(page, a)
    rmax = radius_max(page, a)
    check(rmax == int(min(m["w"], m["h"]) // 2), "圆角上限 = 短边的一半", [rmax, m["w"], m["h"]])

    page.evaluate("(id) => __T.node().setRadius([id], 0)", a)
    page.wait_for_timeout(250)
    check(radius_of(page, a) == 0, "可以设成 0", radius_of(page, a))
    check(computed_radius(page, a) == 0, "0 渲染成直角", computed_radius(page, a))

    page.evaluate("(id) => __T.node().setRadius([id], 24)", b)
    page.wait_for_timeout(250)
    check(radius_of(page, b) == 24, "可以设成中间值 24", radius_of(page, b))
    check(abs(computed_radius(page, b) - 24) < 0.6, "24 渲染正确", computed_radius(page, b))
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p27_radius_cmp.png"))

    page.evaluate("(id) => __T.node().setRadius([id], 9999)", b)
    page.wait_for_timeout(250)
    rmax2 = radius_max(page, b)
    check(radius_of(page, b) == rmax2, "超限值被夹到短边一半", [radius_of(page, b), rmax2])
    check(radius_of(page, b) <= rmax2, "存的值不会超过上限", radius_of(page, b))
    cmp_r = computed_radius(page, b)
    mm = node_metrics(page, b)
    check(cmp_r <= min(mm["w"], mm["h"]) / 2 + 0.6, "渲染圆角不超过短边一半（不会畸变）",
          [cmp_r, mm["w"], mm["h"]])

    # 宽度变窄后上限随之变小
    before_max = radius_max(page, b)
    page.evaluate("(id) => __T.node().setWidth([id], 120)", b)
    page.wait_for_timeout(350)
    after_max = radius_max(page, b)
    check(after_max <= before_max, "把节点改窄后圆角上限跟着变小", [before_max, after_max])
    page.evaluate("(id) => __T.node().setRadius([id], 9999)", b)
    page.wait_for_timeout(250)
    check(radius_of(page, b) == after_max, "再设超限值时按新的上限夹住", [radius_of(page, b), after_max])
    check(computed_radius(page, b) <= min(node_metrics(page, b)["w"], node_metrics(page, b)["h"]) / 2 + 0.6,
          "窄节点上渲染圆角仍在短边一半以内", computed_radius(page, b))

    # ---------------- B 面板开关 ----------------
    print(f"[{label}] B 面板开关（右键 / Ctrl+E / ✕ / Esc）")
    page.evaluate("(id) => __T.node().setRadius([id], 14)", b)
    page.evaluate("(id) => __T.node().setWidth([id], 232)", b)
    page.wait_for_timeout(250)
    check(not panel_open(page), "一开始面板是收起的")
    m = node_metrics(page, a)
    page.mouse.click(m["left"] + m["w"] / 2, m["top"] + 12, button="right")
    page.wait_for_timeout(300)
    has_row = page.evaluate("() => !!document.querySelector('#nodeMenu [data-menu=\"edit-panel\"]')")
    check(has_row, "右键菜单里有「编辑面板」")
    page.click("#nodeMenu [data-menu=\"edit-panel\"]")
    page.wait_for_timeout(350)
    check(panel_open(page), "点菜单项后面板打开")
    check(not page.evaluate("() => { const m=document.getElementById('nodeMenu'); return m.style.display !== 'none'; }"),
          "打开面板时右键菜单已收起")
    check(page.evaluate("() => __T.node().panelTargets().length") == 1, "面板目标是右键的那个节点",
          page.evaluate("() => __T.node().panelTargets()"))
    check(page.evaluate("() => document.getElementById('nepBody').innerText.indexOf('圆角') >= 0"),
          "面板里能看到「圆角」区块")

    page.click("#nepClose")
    page.wait_for_timeout(250)
    check(not panel_open(page), "✕ 能关掉面板")

    page.evaluate("(id) => __T.node().setSelection(id)", a)
    page.wait_for_timeout(200)
    page.keyboard.press("Control+e")
    page.wait_for_timeout(300)
    check(panel_open(page), "Ctrl+E 呼出面板")
    page.keyboard.press("Control+e")
    page.wait_for_timeout(300)
    check(not panel_open(page), "再按 Ctrl+E 关闭面板")

    page.keyboard.press("Control+e")
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check(not panel_open(page), "Esc 关闭面板")

    # ---------------- C 拖动 ----------------
    print(f"[{label}] C 面板拖动与位置记忆")
    page.keyboard.press("Control+e")
    page.wait_for_timeout(350)
    r0 = panel_rect(page)
    hp = page.evaluate("""() => { const h = document.getElementById('nepHead').getBoundingClientRect();
        return { x: h.x + h.width / 2, y: h.y + h.height / 2 }; }""")
    dx, dy = (60 if mobile else 220), 120
    drag(page, hp["x"], hp["y"], hp["x"] + dx, hp["y"] + dy)
    page.wait_for_timeout(300)
    r1 = panel_rect(page)
    check(abs(r1["x"] - r0["x"]) > 20 or abs(r1["y"] - r0["y"]) > 20, "拖标题栏能移动面板",
          [r0["x"], r0["y"], r1["x"], r1["y"]])
    check(r1["x"] >= 0 and r1["y"] >= 0, "面板没有被拖出画布（左上）", [r1["x"], r1["y"]])
    check(r1["x"] + r1["w"] <= r1["vw"] + 1, "面板右侧没有越界", [r1["x"] + r1["w"], r1["vw"]])
    check(r1["y"] + r1["h"] <= r1["vh"] + 1, "面板底部没有越界", [r1["y"] + r1["h"], r1["vh"]])

    # 拖到右下角之外，应被夹住
    hp = page.evaluate("""() => { const h = document.getElementById('nepHead').getBoundingClientRect();
        return { x: h.x + h.width / 2, y: h.y + h.height / 2 }; }""")
    drag(page, hp["x"], hp["y"], hp["x"] + 900, hp["y"] + 900)
    page.wait_for_timeout(300)
    r2 = panel_rect(page)
    check(r2["x"] + r2["w"] <= r2["vw"] + 1 and r2["y"] + r2["h"] <= r2["vh"] + 1,
          "拖到画布外会被夹在可视范围内", [r2["x"] + r2["w"], r2["y"] + r2["h"], r2["vw"], r2["vh"]])

    saved = page.evaluate("() => JSON.parse(localStorage.getItem('knowledge_node_editpanel_pos_v1') || 'null')")
    check(bool(saved) and "left" in saved, "拖动后的位置写进了本地存储", saved)
    page.click("#nepClose")
    page.wait_for_timeout(250)
    page.keyboard.press("Control+e")
    page.wait_for_timeout(350)
    r3 = panel_rect(page)
    check(abs(r3["x"] - r2["x"]) < 3 and abs(r3["y"] - r2["y"]) < 3, "重新打开时回到上次的位置",
          [r2["x"], r2["y"], r3["x"], r3["y"]])

    # 复位到一个好点的位置，方便后面截图与操作
    page.evaluate("() => localStorage.removeItem('knowledge_node_editpanel_pos_v1')")
    page.click("#nepClose")
    page.wait_for_timeout(150)
    page.keyboard.press("Control+e")
    page.wait_for_timeout(350)

    # ---------------- D 面板控件 ----------------
    print(f"[{label}] D 面板控件（宽度 / 圆角 / 标题样式）")
    page.evaluate("(id) => __T.node().setSelection(id)", a)
    page.wait_for_timeout(300)
    pv = panel_values(page)
    check(pv and pv["width"] and pv["width"] > 0, "面板显示当前宽度", pv)
    check(pv and pv["radius"] is not None, "面板显示当前圆角", pv)

    # 宽度：拖滑块
    wr = page.evaluate("""() => { const r = document.getElementById('nepWidthRange').getBoundingClientRect();
        return { x: r.x, y: r.y + r.height / 2, w: r.width }; }""")
    drag(page, wr["x"] + 4, wr["y"], wr["x"] + wr["w"] * 0.8, wr["y"], steps=8)
    page.wait_for_timeout(450)
    w_after = page.evaluate("(id) => { const e = document.querySelector('.node-item[data-node-id=\"' + id + '\"]'); return e.offsetWidth; }", a)
    check(w_after > 240, "拖宽度滑块把节点变宽了", w_after)
    check(abs(panel_values(page)["width"] - w_after) <= 2, "滑块与数字框（宽度）保持一致",
          [panel_values(page)["width"], w_after])

    # 宽度：直接输入数字
    page.fill("#nepWidthNum", "300")
    page.wait_for_timeout(500)
    check(abs(node_metrics(page, a)["w"] - 300) <= 1, "数字框输入 300 生效", node_metrics(page, a)["w"])

    # 圆角：拖滑块到中间
    rr = page.evaluate("""() => { const r = document.getElementById('nepRadiusRange').getBoundingClientRect();
        return { x: r.x, y: r.y + r.height / 2, w: r.width }; }""")
    drag(page, rr["x"] + 2, rr["y"], rr["x"] + rr["w"] * 0.5, rr["y"], steps=8)
    page.wait_for_timeout(450)
    r_set = radius_of(page, a)
    check(r_set is not None and 0 < r_set <= radius_max(page, a), "拖圆角滑块能改圆角", [r_set, radius_max(page, a)])
    check(abs(computed_radius(page, a) - r_set) < 0.8, "节点实际圆角跟着变", [computed_radius(page, a), r_set])
    check(abs(panel_values(page)["radius"] - r_set) <= 1, "滑块与数字框（圆角）保持一致",
          [panel_values(page)["radius"], r_set])

    # 圆角：数字框超限自动夹
    page.fill("#nepRadiusNum", "999")
    page.wait_for_timeout(450)
    check(radius_of(page, a) == radius_max(page, a), "数字框输入超限值也夹到上限",
          [radius_of(page, a), radius_max(page, a)])

    # 标题样式按钮
    page.click("#nepBody [data-nep-align=\"center\"]")
    page.wait_for_timeout(350)
    check(page.evaluate("(id) => __T.node().list().find(n => n.id === id).titleAlign", a) == "center",
          "面板「中」把标题设为居中")
    check(page.evaluate("() => document.querySelector('#nepBody [data-nep-align=\"center\"]').classList.contains('on')"),
          "居中的按钮高亮")
    page.click("#nepBody [data-nep-bold]")
    page.wait_for_timeout(350)
    check(page.evaluate("(id) => __T.node().list().find(n => n.id === id).titleBold", a) is False,
          "面板 B 取消加粗")
    page.click("#nepBody [data-nep-bold]")
    page.wait_for_timeout(300)
    check(page.evaluate("(id) => __T.node().list().find(n => n.id === id).titleBold", a) is True,
          "再点 B 恢复加粗")
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p27_panel.png"))

    # 恢复默认
    page.click("#nepReset")
    page.wait_for_timeout(400)
    lst = page.evaluate("(id) => __T.node().list().find(n => n.id === id)", a)
    check(lst["radius"] is None and lst["width"] is None, "「恢复默认」清掉宽度与圆角", lst)
    check(abs(computed_radius(page, a) - 14) < 0.6, "恢复默认后圆角回到 14px", computed_radius(page, a))
    inline_w = page.evaluate("(id) => document.querySelector('.node-item[data-node-id=\"' + id + '\"]').style.width", a)
    check(inline_w == "", "恢复默认后节点不再有内联宽度（回落到全局默认）", inline_w)

    # 跟随选中：多选两个节点后点「跟随选中」
    page.evaluate("([a,b]) => __T.node().select([a,b])", [a, b])
    page.wait_for_timeout(300)
    check(panel_open(page), "多选后面板仍开着")
    check(page.evaluate("() => __T.node().panelTargets().length") == 2, "面板自动跟随到 2 个选中节点",
          page.evaluate("() => __T.node().panelTargets()"))
    check(page.evaluate("() => document.getElementById('nepTarget').innerText.indexOf('2') >= 0"),
          "面板标题显示作用的是 2 个节点",
          page.evaluate("() => document.getElementById('nepTarget').innerText"))
    page.evaluate("(ids) => __T.node().setRadius(ids, 18)", [a, b])
    page.wait_for_timeout(300)
    check(radius_of(page, a) == 18 and radius_of(page, b) == 18, "面板对多个节点同时生效",
          [radius_of(page, a), radius_of(page, b)])

    page.evaluate("(id) => __T.node().setSelection(id)", a)
    page.wait_for_timeout(250)
    page.evaluate("() => __T.node().setRadius([], 0)")  # 空数组不应报错
    check(True, "传空目标不报错")

    # ---------------- E 持久化 ----------------
    print(f"[{label}] E 持久化（刷新后保留）")
    page.evaluate("(ids) => __T.node().setRadius(ids, 20)", [a])
    page.evaluate("(ids) => __T.node().setWidth(ids, 268)", [a])
    page.wait_for_timeout(600)
    page.reload()
    page.wait_for_timeout(1500)
    enter_node(page)
    page.wait_for_timeout(500)
    lst = page.evaluate("(id) => __T.node().list().find(n => n.id === id)", a)
    check(lst and lst["radius"] == 20, "刷新后圆角还在", lst)
    check(lst and lst["width"] == 268, "刷新后宽度还在", lst)
    check(abs(computed_radius(page, a) - 20) < 0.8, "刷新后渲染的圆角正确", computed_radius(page, a))
    lst_b = page.evaluate("(id) => __T.node().list().find(n => n.id === id)", b)
    check(lst_b and lst_b["radius"] == 18, "另一个节点（多选时设的 18）也保留", lst_b)
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p27_reload.png"))

    # ---------------- F 撤销 ----------------
    print(f"[{label}] F 撤销（一次拖动 = 一步）")
    page.evaluate("(id) => __T.node().setSelection(id)", a)
    page.wait_for_timeout(200)
    page.keyboard.press("Control+e")
    page.wait_for_timeout(350)
    before_labels = page.evaluate("() => __T.node().histLabels()['node']")
    rr = page.evaluate("""() => { const r = document.getElementById('nepRadiusRange').getBoundingClientRect();
        return { x: r.x, y: r.y + r.height / 2, w: r.width }; }""")
    page.mouse.move(rr["x"] + 2, rr["y"])
    page.mouse.down()
    for i in range(1, 9):
        page.mouse.move(rr["x"] + rr["w"] * i / 8, rr["y"])
        page.wait_for_timeout(35)
    page.mouse.up()
    page.wait_for_timeout(950)
    after_labels = page.evaluate("() => __T.node().histLabels()['node']")
    added = [x for x in after_labels if x not in before_labels]
    check(len(added) == 1, "连续拖滑块只产生一条历史记录", [before_labels, after_labels])
    check(added and "圆角" in added[0], "记录标题是「调整节点圆角」", added)
    page.evaluate("() => __T.node().undo()")
    page.wait_for_timeout(450)
    check(radius_of(page, a) == 20, "撤销后圆角回到拖动前的 20", radius_of(page, a))
    page.evaluate("() => __T.node().redo()")
    page.wait_for_timeout(400)
    check(radius_of(page, a) is not None and radius_of(page, a) > 20, "重做又回到拖动后的值", radius_of(page, a))
    # 复位
    page.evaluate("(ids) => __T.node().setRadius(ids, 20)", [a])
    page.wait_for_timeout(300)

    # ---------------- G 导出 ----------------
    print(f"[{label}] G 导出图片（带圆角不影响导出）")
    page.evaluate("(ids) => __T.node().setRadius(ids, 0)", [b])
    page.wait_for_timeout(300)
    if page.evaluate("() => document.getElementById('nodeToolbar').classList.contains('nt-collapsed')"):
        page.evaluate("() => document.getElementById('nodeToolbarMore').click()")
        page.wait_for_timeout(200)
    page.evaluate("() => document.getElementById('nodeExportBtn').click()")
    page.wait_for_timeout(500)
    ok_dl = True
    try:
        with page.expect_download(timeout=40000) as dl:
            page.click("#nemCurrentBtn")
        fname = dl.value.suggested_filename
    except Exception as ex:
        ok_dl = False
        fname = str(ex)[:160]
    check(ok_dl, "设了直角（0）后导出 PNG 成功", fname)
    page.wait_for_timeout(400)
    page.evaluate("() => { const b = document.getElementById('nemCancelBtn'); if (b && b.offsetParent) b.click(); }")

    # ---------------- H 手机端 ----------------
    if mobile:
        print(f"[{label}] H 手机端面板不越界")
        page.evaluate("(id) => __T.node().setSelection(id)", a)
        page.wait_for_timeout(200)
        if not panel_open(page):
            page.keyboard.press("Control+e")
        page.wait_for_timeout(400)
        r = panel_rect(page)
        check(r["display"] != "none", "手机端面板能打开")
        check(r["x"] >= 0 and r["x"] + r["w"] <= r["vw"] + 1, "手机端面板水平不越界",
              [r["x"], r["w"], r["vw"]])
        check(r["y"] + r["h"] <= r["vh"] + 1, "手机端面板垂直不越界", [r["y"], r["h"], r["vh"]])
        page.screenshot(path=os.path.join(SHOTS, "p27_panel_mobile.png"))

    # ---------------- I 报错 ----------------
    print(f"[{label}] I 无 JS 报错")
    real = [e for e in errs if "Failed to load resource" not in e]
    check(len(real) == 0, "全程没有 JS 报错", real[:3])

    ctx.close()


def main():
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception:
            browser = pw.chromium.launch(
                executable_path=r"C:\Users\Offic\AppData\Local\ms-playwright\chromium_headless_shell-1248\chrome-headless-shell-win64\chrome-headless-shell.exe")
        run(browser, mobile=False)
        run(browser, mobile=True)
        browser.close()
    total = RES["pass"] + RES["fail"]
    print()
    print("通过 %d / %d" % (RES["pass"], total))
    if RES["fail"]:
        print("有 %d 项失败" % RES["fail"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
