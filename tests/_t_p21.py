# -*- coding: utf-8 -*-
"""第 141 条：节点组 / 批量设父节点 / 标题节点智能连线 回归

覆盖：
  A 多选成组：默认命名、框包住全部成员、成员唯一归属
  B 固定相对位置：拖任一成员整组移动；拖组头整体移动
  C 命名：改名后数据与组头文字同步
  D 取消成组：组消失、节点全留
  E 批量设父节点：选一个父，选中的节点全部挂到它下面
  F 智能连线：1 个标题节点 + 多个其他 → 标题当父，放射状连线（不再顺序串成链）
  G 从组拉出总结节点：新节点标题带组名，组内顶层成员挂到它下面，自己不加入组
  H 自动排列保住组内相对位置
  I 刷新后组仍在（持久化）
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


def groups(page):
    return page.evaluate("() => __T.node().groups()")


def positions(page):
    lst = page.evaluate("() => __T.node().positions()")
    return {p["id"]: (p["x"], p["y"]) for p in lst}


def edge_list(page):
    return page.evaluate("() => __T.node().edgeList()")


def drag(page, sel, dx, dy, steps=10):
    el = page.query_selector(sel)
    if not el:
        return False
    box = el.bounding_box()
    if not box:
        return False
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, steps + 1):
        page.mouse.move(x + dx * i / steps, y + dy * i / steps)
        page.wait_for_timeout(16)
    page.mouse.up()
    page.wait_for_timeout(160)
    return True


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, timeout=90000)
        page.wait_for_timeout(1600)
        enter_node(page)

        # 清空种子节点，只用本用例自己建的
        page.evaluate("() => __T.node().clearAll()")
        page.wait_for_timeout(300)

        print("A 多选成组")
        n1 = add_node(page, 120, 140, "content", "节点A")
        n2 = add_node(page, 120, 340, "content", "节点B")
        n3 = add_node(page, 430, 140, "content", "节点C")
        select_ids(page, [n1, n2, n3])
        page.evaluate("() => __T.node().batch('group')")
        page.wait_for_timeout(300)
        gs = groups(page)
        check(len(gs) == 1, "成组后只有 1 个组", gs)
        g = gs[0] if gs else {}
        check(sorted(g.get("nodeIds", [])) == sorted([n1, n2, n3]), "3 个节点都在组里", g)
        check(g.get("name") == "分组 1", "默认命名为「分组 1」", g.get("name"))
        gid = g.get("id")
        box = page.evaluate("(id) => __T.node().boxRect(id)", gid)
        check(box is not None, "组框已渲染", box)
        rects = [page.evaluate("(id) => __T.node().nodeRect(id)", i) for i in (n1, n2, n3)]
        if box and all(rects):
            inside = all(r["l"] >= box["l"] - 2 and r["t"] >= box["t"] - 2 and
                         r["l"] + r["w"] <= box["l"] + box["w"] + 2 and
                         r["t"] + r["h"] <= box["t"] + box["h"] + 2 for r in rects)
            check(inside, "组框把 3 个成员全部包住", {"box": box, "n1": rects[0]})
            check(box["h"] > max(r["h"] for r in rects), "组框留了内边距（不是贴着节点）", box["h"])

        print("B 固定相对位置：拖成员 = 整组一起走")
        before = positions(page)
        drag(page, '.node-item[data-node-id="%s"] .node-title-text' % n1, 90, 50)
        after = positions(page)
        d = [(after[k][0] - before[k][0], after[k][1] - before[k][1]) for k in (n1, n2, n3)]
        check(all(abs(x - d[0][0]) <= 2 and abs(y - d[0][1]) <= 2 for x, y in d),
              "三个成员位移完全一致（相对位置没变）", d)
        check(abs(d[0][0] - 90) <= 6 and abs(d[0][1] - 50) <= 6, "确实跟着手指动了 ~90/50", d[0])
        box2 = page.evaluate("(id) => __T.node().boxRect(id)", gid)
        check(box2 and abs(box2["l"] - box["l"] - d[0][0]) <= 6,
              "组框跟着整体平移（屏幕像素）", {"before": box["l"], "after": box2 and box2["l"]})

        print("C 拖组头整体移动")
        before2 = positions(page)
        drag(page, '.node-group-box[data-group-id="%s"] .ng-grip' % gid, -60, 30)
        after2 = positions(page)
        d2 = [(after2[k][0] - before2[k][0], after2[k][1] - before2[k][1]) for k in (n1, n2, n3)]
        check(all(abs(a - d2[0][0]) <= 2 and abs(bb - d2[0][1]) <= 2 for a, bb in d2),
              "拖组头时三个成员同步移动", d2)
        check(abs(d2[0][0] + 60) <= 6 and abs(d2[0][1] - 30) <= 6, "组头拖动方向/距离正确", d2[0])

        print("D 命名")
        page.evaluate("([id]) => __T.node().rename(id, '第一章 · 基础概念')", [gid])
        page.wait_for_timeout(200)
        check(groups(page)[0]["name"] == "第一章 · 基础概念", "改名写回数据", groups(page))
        txt = page.evaluate("(id) => { const b = document.querySelector('.node-group-box[data-group-id=\"' + id + '\"] .ng-name'); return b ? b.textContent : null; }", gid)
        check(txt == "第一章 · 基础概念", "组头文字同步", txt)

        print("E 取消成组")
        select_ids(page, [n1, n2])
        page.evaluate("() => __T.node().batch('ungroup')")
        page.wait_for_timeout(300)
        check(len(groups(page)) == 0, "组已解散", groups(page))
        check(page.evaluate("(id) => __T.node().boxRect(id)", gid) is None, "组框已移除")
        check(len(positions(page)) == 3, "节点一个都没少", len(positions(page)))

        print("F 批量设父节点")
        parent = add_node(page, 800, 140, "title", "父节点")
        c1 = add_node(page, 800, 340, "content", "子1")
        c2 = add_node(page, 1050, 340, "content", "子2")
        c3 = add_node(page, 1300, 340, "content", "子3")
        select_ids(page, [c1, c2, c3])
        page.evaluate("([ids, pid]) => __T.node().batchParent(ids, pid)", [[c1, c2, c3], parent])
        page.wait_for_timeout(300)
        es = edge_list(page)
        got = [e for e in es if e["kind"] == "parent" and e["from"] == parent]
        check(len(got) == 3, "三个节点都挂到同一个父节点下", got)
        check(sorted(e["to"] for e in got) == sorted([c1, c2, c3]), "父子方向是 父→子", got)
        # 更常见的用法：父节点也在选中集合里（同一批里挑一个当父）
        p2 = add_node(page, 800, 600, "title", "父节点2")
        d1 = add_node(page, 1050, 560, "content", "子A")
        d2 = add_node(page, 1050, 700, "content", "子B")
        select_ids(page, [p2, d1, d2])
        page.evaluate("([ids, pid]) => __T.node().batchParent(ids, pid)", [[p2, d1, d2], p2])
        page.wait_for_timeout(250)
        es2 = edge_list(page)
        got2 = [e for e in es2 if e["kind"] == "parent" and e["from"] == p2]
        check(len(got2) == 2 and sorted(e["to"] for e in got2) == sorted([d1, d2]),
              "父节点在选中集合里也能批量设父", got2)
        check(not any(e["from"] == p2 and e["to"] == p2 for e in es2), "没有生成指向自己的连线", es2)

        print("G 智能连线：标题节点当父")
        page.evaluate("""() => {
          const s = __T.node();
          s.select([]);
        }""")
        t = add_node(page, 300, 700, "title", "标题节点")
        x1 = add_node(page, 560, 660, "content", "其他1")
        x2 = add_node(page, 560, 820, "content", "其他2")
        select_ids(page, [t, x1, x2])
        star_pick = page.evaluate("(ids) => __T.node().titleParent(ids)", [t, x1, x2])
        check(star_pick == t, "识别出唯一的标题节点", {"expect": t, "got": star_pick})
        page.evaluate("() => __T.node().batch('connect')")
        page.wait_for_timeout(300)
        es = edge_list(page)
        star = [e for e in es if e["kind"] == "parent" and e["from"] == t]
        check(len(star) == 2, "以标题为父生成 2 条连线", star)
        check(sorted(e["to"] for e in star) == sorted([x1, x2]), "两个其他节点都连到标题上", star)
        chain = [e for e in es if (e["from"] == x1 and e["to"] == x2) or (e["from"] == x2 and e["to"] == x1)]
        check(len(chain) == 0, "不再把两个其他节点串成链", chain)

        print("H 从组拉出总结节点")
        g2 = page.evaluate("([ids]) => __T.node().createGroup(ids, '第二章 · 汇总')", [[x1, x2]])
        check(bool(g2), "先建成一个组", g2)
        sid = page.evaluate("(id) => __T.node().summary(id, 900, 900)", g2)
        page.wait_for_timeout(300)
        check(bool(sid), "生成了总结节点", sid)
        title = page.evaluate("(id) => { const el = document.querySelector('.node-item[data-node-id=\"' + id + '\"] .node-title-text'); return el ? el.textContent : null; }", sid)
        check(title and "总结" in title, "总结节点标题带「总结」", title)
        es = edge_list(page)
        s_edge = [e for e in es if e["kind"] == "parent" and e["from"] == sid]
        check(sorted(e["to"] for e in s_edge) == sorted([x1, x2]), "组内两个成员都挂到总结节点下", s_edge)
        check(page.evaluate("(id) => __T.node().groupOf(id)", sid) is None, "总结节点本身不属于这个组")
        check(len(groups(page)) == 1 and groups(page)[0]["id"] == g2, "组还在且成员没变", groups(page))

        # 真拖一次 ⇢：从组头拖到画布空白处，松手就多一个总结节点
        n_before = len(positions(page))
        ok_drag = drag(page, '.node-group-box[data-group-id="%s"] .ng-btn[data-ng="summary"]' % g2, 300, 150)
        page.wait_for_timeout(400)
        n_after = len(positions(page))
        check(ok_drag and n_after == n_before + 1, "从组头 ⇢ 拖到空白处会新建总结节点", {"before": n_before, "after": n_after})
        if n_after == n_before + 1:
            new_id = [k for k in positions(page) if k not in (x1, x2, sid)][-1]
            es_drag = edge_list(page)
            check(any(e["kind"] == "parent" and e["from"] == new_id for e in es_drag),
                  "拖出来的总结节点同样接管组内成员", [e for e in es_drag if e["from"] == new_id])

        print("I 自动排列保住组内相对位置")
        rel_before = None
        pos = positions(page)
        rel_before = (pos[x1][0] - pos[x2][0], pos[x1][1] - pos[x2][1])
        page.evaluate("() => document.getElementById('nodeToolbar').classList.contains('nt-collapsed') && document.getElementById('nodeToolbarMore').click()")
        page.wait_for_timeout(150)
        page.click("#nodeAutoLayoutBtn")
        page.wait_for_timeout(900)
        pos2 = positions(page)
        rel_after = (pos2[x1][0] - pos2[x2][0], pos2[x1][1] - pos2[x2][1])
        check(abs(rel_before[0] - rel_after[0]) <= 2 and abs(rel_before[1] - rel_after[1]) <= 2,
              "自动排列后组内相对位移不变", {"before": rel_before, "after": rel_after})

        print("J 刷新后组还在")
        names_before = [g["name"] for g in groups(page)]
        page.wait_for_timeout(600)
        page.reload()
        page.wait_for_timeout(1600)
        enter_node(page)
        page.wait_for_timeout(400)
        gs2 = groups(page)
        check([g["name"] for g in gs2] == names_before, "分组与名字都落盘了", gs2)
        check(page.evaluate("(id) => __T.node().boxRect(id) !== null", g2), "刷新后组框重新渲染")

        print("K 批量栏按钮真实可点（不是只有钩子）")
        pos_all = positions(page)
        two = [k for k in pos_all if k not in (x1, x2)][:2]
        select_ids(page, two)
        page.wait_for_timeout(150)
        btn = page.query_selector('[data-batch="group"]')
        check(btn is not None, "批量栏出现「🗂 成组」按钮")
        btn2 = page.query_selector('[data-batch="set-parent-batch"]')
        check(btn2 is not None, "批量栏出现「⬆ 设父节点」按钮")
        btn3 = page.query_selector('[data-batch="ungroup"]')
        check(btn3 is not None, "批量栏出现「⊞ 取消成组」按钮")

        # 真点「设父节点」：弹出选择器 → 点一行 → 连线真的生成
        before_edges = len(edge_list(page))
        if btn2:
            btn2.click()
            page.wait_for_timeout(250)
            title = page.evaluate("() => { const m = document.getElementById('nodeMenu'); return m && m.style.display !== 'none' ? m.querySelector('.menu-title').textContent : null; }")
            check(title == "批量设父节点", "打开批量父节点选择器", title)
            row = page.query_selector('.menu-row.pick[data-node-id="%s"]' % two[0])
            check(row is not None, "选择器里列出了节点（含选中的）", two[0])
            if row:
                row.click()
                page.wait_for_timeout(300)
                es3 = edge_list(page)
                check(len(es3) == before_edges + 1, "点一行就生成一条父子连线", {"before": before_edges, "after": len(es3)})
                check(any(e["kind"] == "parent" and e["from"] == two[0] and e["to"] == two[1] for e in es3),
                      "连线方向：选中的那个当父", es3[-2:])
                check(page.evaluate("() => document.getElementById('nodeMenu').style.display") == "none",
                      "选完自动收起菜单")

        # 再点「成组」
        select_ids(page, two)
        page.wait_for_timeout(150)
        btn = page.query_selector('[data-batch="group"]')
        if btn:
            btn.click()
            page.wait_for_timeout(300)
            check(len(groups(page)) == 2, "点按钮就建成第二个组", groups(page))

        print("L 全程无 JS 报错")
        check(len(errs) == 0, "无 pageerror", errs[:3])

        print("M 手机端（390×844）")
        ctx2 = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
        m = ctx2.new_page()
        merrs = []
        m.on("pageerror", lambda e: merrs.append(str(e)))
        m.goto(URL, timeout=90000)
        m.wait_for_timeout(1600)
        enter_node(m)
        m.evaluate("() => __T.node().clearAll()")
        m.wait_for_timeout(200)
        a1 = add_node(m, 60, 120, "content", "手机A")
        a2 = add_node(m, 60, 320, "content", "手机B")
        select_ids(m, [a1, a2])
        m.wait_for_timeout(150)
        mb = m.query_selector('[data-batch="group"]')
        check(mb is not None, "手机端批量栏也有「成组」")
        if mb:
            mb.click()
            m.wait_for_timeout(300)
        mg = groups(m)
        check(len(mg) == 1 and sorted(mg[0]["nodeIds"]) == sorted([a1, a2]), "手机端成组成功", mg)
        mbox = m.evaluate("(id) => __T.node().boxRect(id)", mg[0]["id"]) if mg else None
        check(mbox is not None, "手机端组框渲染", mbox)
        check(mbox and mbox["l"] >= -2 and mbox["l"] + mbox["w"] <= 392,
              "组框没有横向溢出视口", mbox)
        # 组框在下层：点组内节点仍然点得到节点（不会点到框上）
        el = m.query_selector('.node-item[data-node-id="%s"] .node-title-text' % a1)
        if el:
            el.click()
            m.wait_for_timeout(200)
            sel = m.evaluate("() => { const s = __T.node().list(); return s.length; }")
            check(sel == 2, "点组内节点正文没有触发整组拖动/误选", sel)
        check(len(merrs) == 0, "手机端无 JS 报错", merrs[:3])
        ctx2.close()

        b.close()

    print("\n通过 %d / %d" % (RES["pass"], RES["pass"] + RES["fail"]))
    return 0 if RES["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
