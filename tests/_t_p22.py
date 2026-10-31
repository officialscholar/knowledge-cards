# -*- coding: utf-8 -*-
"""第 142 条：总结节点落点决定连线方式 + 分组左/右/下大括号说明 回归

覆盖：
  A 落点判定：左 / 右 / 上 / 下 / 框内取最近边
  B 落在左边：保持原逻辑（默认 右→左 连接点，成员挂成下级）
  C 落在右边：最短连线（总结左边 ↔ 成员右边）
  D 落在下边：最短连线（总结上边 ↔ 成员下边）
  E 落在上边：最短连线（总结下边 ↔ 成员上边）
  F 大括号：组头按钮 → 菜单三行 → 加左侧括号（路径/位置/文字）
  G 大字：文字可编辑并落盘，刷新后仍在
  H 拖动分组：大括号跟着走（位移与节点一致）
  I 右 / 下两条边的大括号位置正确
  J 取消成组后大括号一并消失
  K 手机端 390×844：加括号不报错、文字可点
  L 全程无 JS 报错
"""
import os
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
URL = "file:///" + os.path.join(BASE, "index.html").replace("\\", "/")

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


def select_ids(page, ids):
    return page.evaluate("(ids) => __T.node().select(ids)", ids)


def clear(page):
    page.evaluate("() => __T.node().clearAll()")
    page.wait_for_timeout(200)


def bnd(page, gid):
    return page.evaluate("(id) => __T.node().groupBounds(id)", gid)


def edges(page):
    return page.evaluate("() => __T.node().edgeList()")


def summary_at(page, gid, x, y):
    return page.evaluate("([id,x,y]) => __T.node().summary(id,x,y)", [gid, x, y])


def edges_from(page, nid):
    return [e for e in edges(page) if e["from"] == nid]


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        errs = []
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, timeout=90000)
        page.wait_for_timeout(1400)
        enter_node(page)

        print("A 落点判定")
        clear(page)
        a1 = add_node(page, 200, 200, "content", "成员1")
        a2 = add_node(page, 200, 420, "content", "成员2")
        gid = page.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[a1, a2], "线性结构"])
        page.wait_for_timeout(250)
        b0 = bnd(page, gid)
        check(page.evaluate("([id,x,y]) => __T.node().dropSide(id,x,y)", [gid, b0["x"] - 120, b0["y"] + 40]) == "left",
              "落点在组左边 → left")
        check(page.evaluate("([id,x,y]) => __T.node().dropSide(id,x,y)", [gid, b0["x"] + b0["w"] + 120, b0["y"] + 40]) == "right",
              "落点在组右边 → right")
        check(page.evaluate("([id,x,y]) => __T.node().dropSide(id,x,y)", [gid, b0["x"] + 40, b0["y"] - 120]) == "top",
              "落点在组上边 → top")
        check(page.evaluate("([id,x,y]) => __T.node().dropSide(id,x,y)", [gid, b0["x"] + 40, b0["y"] + b0["h"] + 120]) == "bottom",
              "落点在组下边 → bottom")
        check(page.evaluate("([id,x,y]) => __T.node().dropSide(id,x,y)", [gid, b0["x"] + 2, b0["y"] + b0["h"] / 2]) == "left",
              "落在框内贴左边 → left")

        print("B 落在左边：保持原逻辑")
        clear(page)
        m1 = add_node(page, 300, 300, "content", "成员A")
        m2 = add_node(page, 300, 500, "content", "成员B")
        g1 = page.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[m1, m2], "组一"])
        page.wait_for_timeout(250)
        bb = bnd(page, g1)
        sL = summary_at(page, g1, bb["x"] - 260, bb["y"] + 60)
        page.wait_for_timeout(300)
        eL = edges_from(page, sL)
        check(len(eL) == 2, "左边落点生成 2 条父子线", eL)
        check(all(e["kind"] == "parent" for e in eL), "都是父子关系（箭头指向成员）", eL)
        check(all(e["fromSide"] == "right" and e["toSide"] == "left" for e in eL),
              "沿用原来的 右→左 连接点", eL)
        sn = page.evaluate("(id) => { const n = __T.node().list().find(x => x.id === id); return n ? n.content : null; }", sL)
        check(True if sn is not None else False, "总结节点存在")

        print("C 落在右边：最短连线")
        clear(page)
        n1 = add_node(page, 300, 300, "content", "成员C")
        n2 = add_node(page, 300, 520, "content", "成员D")
        g2 = page.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[n1, n2], "组二"])
        page.wait_for_timeout(250)
        bb2 = bnd(page, g2)
        sR = summary_at(page, g2, bb2["x"] + bb2["w"] + 400, bb2["y"] + 120)
        page.wait_for_timeout(300)
        eR = edges_from(page, sR)
        check(len(eR) == 2, "右边落点也生成 2 条线", eR)
        check(all(e["fromSide"] == "left" and e["toSide"] == "right" for e in eR),
              "总结用左边、成员用右边（最近的一对）", eR)
        pair = page.evaluate("([a,b]) => __T.node().nearestPorts(a,b)", [sR, n1])
        check(pair is not None and pair["from"] == eR[0]["fromSide"], "与 nearestPorts 的判定一致", pair)

        print("D 落在下边：最短连线")
        sB = summary_at(page, g2, bb2["x"] + 120, bb2["y"] + bb2["h"] + 400)
        page.wait_for_timeout(300)
        eB = edges_from(page, sB)
        check(len(eB) == 2, "下边落点生成 2 条线", eB)
        check(all(e["fromSide"] == "top" and e["toSide"] == "bottom" for e in eB),
              "总结用上边、成员用下边", eB)

        print("E 落在上边：最短连线")
        clear(page)
        p1 = add_node(page, 400, 500, "content", "成员E")
        p2 = add_node(page, 400, 700, "content", "成员F")
        g3 = page.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[p1, p2], "组三"])
        page.wait_for_timeout(250)
        bb3 = bnd(page, g3)
        sT = summary_at(page, g3, bb3["x"] + 100, bb3["y"] - 320)
        page.wait_for_timeout(300)
        eT = edges_from(page, sT)
        check(len(eT) == 2, "上边落点生成 2 条线", eT)
        check(all(e["fromSide"] == "bottom" and e["toSide"] == "top" for e in eT),
              "总结用下边、成员用上边", eT)

        print("F 大括号：按钮 / 菜单 / 左侧括号")
        clear(page)
        q1 = add_node(page, 360, 320, "content", "数组：随机访问 O(1)")
        q2 = add_node(page, 360, 540, "content", "链表：插入删除 O(1)")
        g4 = page.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[q1, q2], "线性结构"])
        page.wait_for_timeout(300)
        btn = page.query_selector('.node-group-box[data-group-id="%s"] .ng-btn[data-ng="brace"]' % g4)
        check(btn is not None, "组头出现「｝」大括号按钮")
        if btn:
            btn.click()
            page.wait_for_timeout(250)
            rows = page.evaluate("() => Array.from(document.querySelectorAll('#nodeMenu .menu-row')).map(b => b.textContent)")
            check(len(rows) == 3, "菜单列出左/右/下三行", rows)
            check(any("左边" in r for r in rows) and any("右边" in r for r in rows) and any("下边" in r for r in rows),
                  "三行分别是左、右、下", rows)
            row = page.query_selector('#nodeMenu .menu-row[data-side="left"]')
            if row:
                row.click()
                page.wait_for_timeout(400)
        check(page.evaluate("() => document.getElementById('nodeMenu').style.display") == "none", "选完自动收起菜单")
        rect = page.evaluate("([id]) => __T.node().braceRect(id,'left')", [g4])
        check(rect is not None, "左侧大括号出现在画布上", rect)
        if rect:
            check(bool(rect["d"]) and rect["d"].startswith("M"), "大括号有路径数据", rect["d"][:40] if rect["d"] else None)
            gb = page.evaluate("(id) => __T.node().boxRect(id)", g4)
            check(rect["l"] + rect["w"] <= gb["l"] + 1, "括号整体在组框左侧、不压住组框",
                  {"braceRight": rect["l"] + rect["w"], "boxLeft": gb["l"]})
            check(rect["textRect"] is not None and rect["textRect"]["l"] + rect["textRect"]["w"] <= gb["l"],
                  "文字在括号外侧（更左边）", rect["textRect"])
        # 关掉自动进入的编辑态，避免影响后续断言
        page.evaluate("() => { const ae = document.activeElement; if (ae && ae.blur) ae.blur(); }")
        page.wait_for_timeout(200)

        print("G 文字编辑与落盘")
        page.evaluate("([id]) => __T.node().braceSetText(id,'left','二者都是线性结构')", [g4])
        page.wait_for_timeout(200)
        txt = page.evaluate("([id]) => __T.node().braceText(id,'left')", [g4])
        check(txt == "二者都是线性结构", "文字写进数据", txt)
        rect2 = page.evaluate("([id]) => __T.node().braceRect(id,'left')", [g4])
        check(rect2 and rect2["text"] == "二者都是线性结构", "画布上的文字同步", rect2["text"] if rect2 else None)
        # 真在页面上编辑：点文字 → 输入 → 回车
        page.evaluate("([id]) => __T.node().braceSetText(id,'left','')", [g4])
        page.wait_for_timeout(150)
        el = page.query_selector('.ng-brace[data-group-id="%s"][data-side="left"] .ng-brace-text' % g4)
        if el:
            el.click()
            page.wait_for_timeout(200)
            page.keyboard.type("点一下就能改")
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
        txt2 = page.evaluate("([id]) => __T.node().braceText(id,'left')", [g4])
        check(txt2 == "点一下就能改", "在页面上直接输入后回车保存", txt2)

        print("H 拖动分组，大括号跟着走")
        before = page.evaluate("([id]) => __T.node().braceRect(id,'left')", [g4])
        pos_before = page.evaluate("(id) => __T.node().positions().find(p => p.id === id)", q1)
        page.evaluate("([id,dx,dy]) => { const n = __T.node().positions().find(p => p.id === id); }", [q1, 0, 0])
        drag_done = page.evaluate("""([gid]) => {
          const box = document.querySelector('.node-group-box[data-group-id="' + gid + '"] .ng-head');
          return !!box;
        }""", [g4])
        check(drag_done, "组头存在，可拖动")
        elh = page.query_selector('.node-group-box[data-group-id="%s"] .ng-head' % g4)
        if elh:
            box = elh.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            for i in range(1, 9):
                page.mouse.move(box["x"] + box["width"] / 2 + 12 * i, box["y"] + box["height"] / 2 + 6 * i)
                page.wait_for_timeout(16)
            page.mouse.up()
            page.wait_for_timeout(300)
        after = page.evaluate("([id]) => __T.node().braceRect(id,'left')", [g4])
        pos_after = page.evaluate("(id) => __T.node().positions().find(p => p.id === id)", q1)
        ddx = pos_after["x"] - pos_before["x"]
        ddy = pos_after["y"] - pos_before["y"]
        check(ddx > 0, "分组确实被拖动了", {"dx": ddx, "dy": ddy})
        if before and after:
            check(abs((after["l"] - before["l"]) - ddx) < 30 and abs((after["t"] - before["t"]) - ddy) < 30,
                  "大括号位移与节点一致（跟着组走）",
                  {"brace": [round(after["l"] - before["l"]), round(after["t"] - before["t"])], "node": [ddx, ddy]})

        print("I 右 / 下两条边")
        page.evaluate("([id]) => { __T.node().braceAdd(id,'right'); __T.node().braceAdd(id,'bottom'); }", [g4])
        page.wait_for_timeout(300)
        page.evaluate("() => { const ae = document.activeElement; if (ae && ae.blur) ae.blur(); }")
        page.wait_for_timeout(200)
        sides = page.evaluate("([id]) => __T.node().braces(id)", [g4])
        check(set(sides.keys()) == {"left", "right", "bottom"}, "三边都有大括号", list(sides.keys()))
        rr = page.evaluate("([id]) => __T.node().braceRect(id,'right')", [g4])
        rd = page.evaluate("([id]) => __T.node().braceRect(id,'bottom')", [g4])
        gbr = page.evaluate("(id) => __T.node().boxRect(id)", g4)
        check(rr and rr["l"] >= gbr["l"] + gbr["w"] - 1, "右侧括号贴组框右边", {"braceLeft": rr["l"] if rr else None, "boxRight": gbr["l"] + gbr["w"]})
        check(rd and rd["t"] >= gbr["t"] + gbr["h"] - 1, "下方括号贴组框下边", {"braceTop": rd["t"] if rd else None, "boxBottom": gbr["t"] + gbr["h"]})
        check(rd and rd["textRect"] and rd["textRect"]["t"] >= rd["t"], "下方文字在括号下面", rd["textRect"] if rd else None)

        print("J 刷新后仍在")
        page.evaluate("() => __T.node().braceSetText(%r,'right','一句话总结')" % g4)
        page.wait_for_timeout(300)
        page.reload()
        page.wait_for_timeout(1600)
        enter_node(page)
        page.wait_for_timeout(600)
        gs = page.evaluate("() => __T.node().groups()")
        same = [g for g in gs if g["name"] == "线性结构"]
        check(len(same) == 1, "刷新后分组还在", gs)
        if same:
            sides2 = page.evaluate("([id]) => __T.node().braces(id)", [same[0]["id"]])
            check(sides2 is not None and "right" in sides2 and sides2["right"] == "一句话总结",
                  "大括号与文字都持久化了", sides2)

        print("K 取消成组 → 括号消失")
        page.evaluate("([id]) => __T.node().dissolve(id)", [same[0]["id"] if same else g4])
        page.wait_for_timeout(300)
        left_braces = page.evaluate("() => document.querySelectorAll('.ng-brace').length")
        check(left_braces == 0, "取消成组后画布上没有大括号", left_braces)

        print("L 手机端 390×844")
        ctx2 = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
        m = ctx2.new_page()
        m.on("pageerror", lambda e: errs.append(str(e)))
        m.goto(URL, timeout=90000)
        m.wait_for_timeout(1600)
        enter_node(m)
        m.evaluate("() => __T.node().clearAll()")
        m.wait_for_timeout(200)
        t1 = add_node(m, 40, 160, "content", "手机成员一")
        t2 = add_node(m, 40, 380, "content", "手机成员二")
        mg = m.evaluate("([ids,nm]) => __T.node().createGroup(ids,nm)", [[t1, t2], "手机分组"])
        m.wait_for_timeout(300)
        mb = m.query_selector('.node-group-box[data-group-id="%s"] .ng-btn[data-ng="brace"]' % mg)
        check(mb is not None, "手机端组头也有大括号按钮")
        if mb:
            mb.click()
            m.wait_for_timeout(400)
            rowm = m.query_selector('#nodeMenu .menu-row[data-side="left"]')
            if rowm:
                rowm.click()
            m.wait_for_timeout(500)
        m.evaluate("() => { const ae = document.activeElement; if (ae && ae.blur) ae.blur(); }")
        m.evaluate("([id]) => __T.node().braceSetText(id,'left','手机上的说明')", [mg])
        m.wait_for_timeout(300)
        mr = m.evaluate("([id]) => __T.node().braceRect(id,'left')", [mg])
        check(mr is not None and bool(mr["d"]), "手机端左括号正常渲染", mr and mr["d"][:30])
        check(mr is not None and mr["textRect"] is not None and mr["textRect"]["l"] >= 0,
              "手机端文字没跑出屏幕左边", mr["textRect"] if mr else None)
        ctx2.close()

        print("M 全程无 JS 报错")
        check(len(errs) == 0, "无 pageerror", errs[:3])
        b.close()

    print("\n通过 %d / 失败 %d" % (RES["pass"], RES["fail"]))
    return RES["fail"] == 0


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
