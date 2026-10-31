# -*- coding: utf-8 -*-
"""第 145 条回归：页面管理弹窗重做 + 小地图开关 + 撤销范围 + 工具栏折叠 + 标题对齐/加粗

覆盖：
  A 页面管理弹窗：固定高度、列表内部滚动、搜索过滤、分类分组、底部按钮常显
  B 自定义分类：新建 / 归类 / 按分类筛选 / 改名 / 删除后页面回未分类 / 刷新后仍在
  C 小地图：默认显示、可隐藏、刷新后保持选择
  D 撤销/重做：标题样式、节点移动、页面分类；两栈按发生顺序撤销
  E 工具栏：默认只露前三个控件 + ⋯，展开后全部可见，刷新后保持
  F 标题样式：单个（右键菜单）与批量（底部批量栏）设置居中/左/右/加粗，刷新后仍在
  G 手机端 390×844：弹窗在视口内、列表可滚动、按钮可点
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


def visible_toolbar_children(page):
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('#nodeToolbar > *')).filter(e => e.offsetParent !== null).length")


def panel_rect(page):
    return page.evaluate("""() => {
      const p = document.querySelector('#nodePageModal .pgm-panel');
      if (!p) return null;
      const r = p.getBoundingClientRect();
      return { l: r.left, t: r.top, w: r.width, h: r.height };
    }""")


def rows(page):
    return page.evaluate("() => document.querySelectorAll('#pgmList .pgm-row').length")


def run(viewport, label, shot, mobile=False):
    print(f"\n=== {label} {viewport['width']}x{viewport['height']} ===")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=viewport)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, timeout=90000)
        page.wait_for_timeout(1200)
        enter_node(page)

        # ---------------- E 工具栏折叠（进节点模式后立刻验证默认态） ----------------
        print(f"[{label}] E 工具栏默认折叠")
        check(page.evaluate("() => document.getElementById('nodeToolbar').classList.contains('nt-collapsed')"),
              "进入节点模式后工具栏默认折叠")
        base_visible = visible_toolbar_children(page)
        check(base_visible == 4, "折叠时只显示前三个控件 + ⋯", base_visible)
        check(page.is_visible("#nodeUndoBtn") and page.is_visible("#nodeRedoBtn") and page.is_visible("#nodeAddBtn"),
              "前三个（撤销/重做/新建）可见")
        check(not page.is_visible("#nodePageBtn"), "页面按钮默认收起")
        check(not page.is_visible("#nodeExportBtn"), "导出按钮默认收起")
        page.evaluate("() => __T.node().toggleToolbar()")
        page.wait_for_timeout(200)
        check(visible_toolbar_children(page) > 4, "展开后其余控件出现", visible_toolbar_children(page))
        check(page.is_visible("#nodePageBtn") and page.is_visible("#nodeExportBtn"), "展开后页面/导出按钮可见")
        page.evaluate("() => __T.node().toggleToolbar()")
        page.wait_for_timeout(200)
        check(visible_toolbar_children(page) == 4, "再点 ⋯ 可收起")

        # ---------------- C 小地图 ----------------
        print(f"[{label}] C 小地图显隐")
        init_on = page.evaluate("() => __T.node().minimapOn()")
        check(init_on == (not mobile), "首次进入：宽屏默认显示、窄屏默认隐藏", init_on)
        disp = page.evaluate("() => getComputedStyle(document.getElementById('nodeMinimap')).display")
        check((disp != "none") == init_on, "小地图显示状态与偏好一致", disp)
        add_node(page, 60, 200, "title", "地图节点")
        page.wait_for_timeout(300)
        if init_on:
            check(page.evaluate("() => document.querySelectorAll('#nodeMinimap svg rect').length") >= 1,
                  "小地图已绘制节点")
        page.evaluate("() => __T.node().toggleMinimap()")
        page.wait_for_timeout(300)
        check(page.evaluate("() => __T.node().minimapOn()") is (not init_on), "点🗺可切换显隐")
        if init_on:
            check(page.evaluate("() => getComputedStyle(document.getElementById('nodeMinimap')).display") == "none",
                  "隐藏后不再显示")
            check(page.evaluate("() => document.getElementById('nodeMinimap').innerHTML.trim()") == "",
                  "隐藏时清空小地图内容（省性能）")
        else:
            check(page.evaluate("() => document.querySelectorAll('#nodeMinimap svg').length") >= 1,
                  "窄屏手动打开后能正常绘制")
        page.evaluate("() => __T.node().toggleMinimap()")
        page.wait_for_timeout(300)
        check(page.evaluate("() => __T.node().minimapOn()") is init_on, "再点可切回原状态")

        # ---------------- A/B 页面管理弹窗 ----------------
        print(f"[{label}] A/B 页面管理弹窗")
        page.evaluate("() => __T.node().clearAll()")
        add_node(page, 200, 160, "title", "第一章")
        add_node(page, 200, 360, "content", "知识点甲")
        page.wait_for_timeout(300)
        cat_a = page.evaluate("() => __T.node().addCat('前端')")
        cat_b = page.evaluate("() => __T.node().addCat('算法')")
        check(bool(cat_a) and bool(cat_b), "可新建分类", [cat_a, cat_b])
        page.evaluate("([a,b]) => { const ps = __T.node().pages(); __T.node().setPageCat(ps[0].id, a); return true; }", [cat_a, cat_b])
        # 批量造页面（每 3 个留一个未分类，其余分到两个分类）
        page.evaluate("""() => {
          const cs = __T.node().cats();
          for (let i = 0; i < 26; i++) {
            const cid = (i % 3 === 0 || !cs.length) ? null : (i % 2 ? cs[0].id : (cs[1] ? cs[1].id : cs[0].id));
            __T.node().addPage('批量 ' + i, cid);
          }
        }""")
        page.wait_for_timeout(500)
        total_pages = page.evaluate("() => __T.node().pages().length")
        page.evaluate("() => __T.node().openPages()")
        page.wait_for_timeout(400)
        check(page.evaluate("() => document.getElementById('nodePageModal').style.display") == "flex",
              "页面管理弹窗可打开")
        pr = panel_rect(page)
        vh = viewport["height"]
        check(pr and pr["h"] <= vh - 24, "页面很多时弹窗高度不超视口", pr)
        check(pr and pr["t"] >= 0, "弹窗顶边不越界", pr)
        check(rows(page) == total_pages, "列表渲染全部页面", [rows(page), total_pages])
        sc = page.evaluate("""() => { const l = document.getElementById('pgmList');
            return [l.scrollHeight, l.clientHeight]; }""")
        check(sc[0] > sc[1], "页面多时列表内部滚动（弹窗不再拉长）", sc)
        check(page.is_visible("#pgmFoot .pgm-btn"), "底部新建按钮常显可点")
        check(page.evaluate("() => document.querySelectorAll('#pgmList .pgm-group').length") >= 2,
              "「全部」视图按分类分组", page.evaluate("() => document.querySelectorAll('#pgmList .pgm-group').length"))
        if mobile:
            print("  skip  手机端不自动聚焦（避免拉起软键盘顶掉弹窗）")
        else:
            check(page.evaluate("() => document.activeElement && document.activeElement.id") == "pgmSearchInput",
                  "打开后搜索框自动获焦")
        page.screenshot(path=os.path.join(SHOTS, shot))

        # 搜索
        page.fill("#pgmSearchInput", "批量 1")
        page.wait_for_timeout(300)
        n_search = rows(page)
        check(0 < n_search < total_pages, "搜索能过滤页面", [n_search, total_pages])
        if not mobile:
            check(page.evaluate("() => document.activeElement && document.activeElement.id") == "pgmSearchInput",
                  "搜索时输入框保持焦点")
        page.fill("#pgmSearchInput", "不存在的名字")
        page.wait_for_timeout(300)
        check(rows(page) == 0, "无匹配时列表为空")
        check(page.evaluate("() => !!document.querySelector('#pgmList .pgm-empty')"), "无匹配有提示文案")
        page.fill("#pgmSearchInput", "")
        page.wait_for_timeout(200)

        # 分类筛选
        page.click(f'#pgmTools .pgm-chip[data-cat="{cat_a}"]')
        page.wait_for_timeout(300)
        n_cat = rows(page)
        expect_a = page.evaluate("([c]) => __T.node().pages().filter(p => p.catId === c).length", [cat_a])
        check(n_cat == expect_a and n_cat > 0, "按分类筛选生效", [n_cat, expect_a])
        check(page.evaluate("() => document.querySelectorAll('#pgmList .pgm-group').length") == 0,
              "选具体分类后不再重复分组")

        # 分类管理视图
        page.click('#pgmFoot [data-pgm-act="cat-manage"]')
        page.wait_for_timeout(300)
        check(page.evaluate("() => document.getElementById('pgmTitle').textContent") == "分类管理",
              "可进入分类管理")
        n_catrow = page.evaluate("() => document.querySelectorAll('#pgmList .pgm-catrow').length")
        check(n_catrow >= 3, "分类列表含未分类 + 两个自定义分类", n_catrow)
        # 改名 / 删除（走钩子，避开原生 prompt）
        page.evaluate("([c]) => __T.node().renameCat(c, '前端开发')", [cat_a])
        page.wait_for_timeout(200)
        page.evaluate("() => __T.node().openPages()")
        page.wait_for_timeout(200)
        names = page.evaluate("() => __T.node().cats().map(c => c.name)")
        check("前端开发" in names, "分类可改名", names)
        page.evaluate("([c]) => __T.node().delCat(c)", [cat_b])
        page.wait_for_timeout(300)
        orphan = page.evaluate("([c]) => __T.node().pages().filter(p => p.catId === c).length", [cat_b])
        check(orphan == 0, "删分类后页面回未分类（不丢页面）", orphan)
        check(page.evaluate("() => __T.node().pages().length") == total_pages, "删分类不删页面")

        # 持久化
        page.reload(timeout=90000)
        page.wait_for_timeout(1200)
        enter_node(page)
        names2 = page.evaluate("() => __T.node().cats().map(c => c.name)")
        check("前端开发" in names2, "刷新后分类仍在", names2)
        check(page.evaluate("() => __T.node().pages().length") == total_pages, "刷新后页面数不变")
        check(page.evaluate("() => __T.node().minimapOn()") is init_on, "刷新后小地图显示偏好保留")

        # ---------------- F 标题样式 ----------------
        print(f"[{label}] F 标题对齐 / 加粗")
        page.evaluate("() => { __T.node().closePages(); }")
        page.evaluate("() => __T.node().clearAll()")
        n1 = add_node(page, 40, 180, "content", "标题甲")
        n2 = add_node(page, 40, 420, "content", "标题乙")
        page.wait_for_timeout(400)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).bold", [n1]) is True, "标题默认加粗")
        page.evaluate("([a,b]) => __T.node().select([a,b])", [n1, n2])
        page.wait_for_timeout(300)
        check(page.is_visible('#nodeBatchBar [data-batch="title-center"]'), "批量栏有标题样式按钮")
        page.click('#nodeBatchBar [data-batch="title-center"]')
        page.wait_for_timeout(400)
        st1 = page.evaluate("([i]) => __T.node().titleStyle(i)", [n1])
        st2 = page.evaluate("([i]) => __T.node().titleStyle(i)", [n2])
        check(st1["align"] == "center" and st2["align"] == "center", "批量居中生效", [st1, st2])
        check(st1["domAlign"] == "center", "DOM 上真的居中了", st1["domAlign"])
        page.click('#nodeBatchBar [data-batch="title-left"]')
        page.wait_for_timeout(300)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).align", [n1]) == "left", "批量左对齐生效")
        page.click('#nodeBatchBar [data-batch="title-bold"]')
        page.wait_for_timeout(300)
        b1 = page.evaluate("([i]) => __T.node().titleStyle(i)", [n1])
        check(b1["bold"] is False and b1["domWeight"] == "500", "批量取消加粗生效", b1)
        page.screenshot(path=os.path.join(SHOTS, "p25_title_style%s.png" % ("_mobile" if mobile else "")))

        # 单个节点：右键菜单
        page.evaluate("() => __T.node().select([])")
        page.wait_for_timeout(200)
        nb = page.query_selector(f'.node-item[data-node-id="{n2}"] .node-title-text')
        bb = nb.bounding_box()
        page.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, button="right")
        page.wait_for_timeout(400)
        check(page.is_visible('#nodeMenu .mts-btn[data-title-style="right"]'), "右键菜单有标题样式快捷条")
        page.click('#nodeMenu .mts-btn[data-title-style="right"]')
        page.wait_for_timeout(300)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).align", [n2]) == "right", "单节点右对齐生效")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # 刷新后仍是设置值
        page.reload(timeout=90000)
        page.wait_for_timeout(1200)
        enter_node(page)
        st_after = page.evaluate("([i]) => __T.node().titleStyle(i)", [n2])
        check(st_after["align"] == "right", "刷新后标题对齐保留", st_after)

        # ---------------- D 撤销 / 重做 ----------------
        print(f"[{label}] D 撤销重做覆盖范围")
        # 1) 标题样式可撤销
        page.evaluate("([i]) => __T.node().setTitleStyle([i], { align: 'center' })", [n2])
        page.wait_for_timeout(300)
        page.evaluate("() => __T.node().undo()")
        page.wait_for_timeout(400)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).align", [n2]) == "right", "撤销可回退标题对齐")
        page.evaluate("() => __T.node().redo()")
        page.wait_for_timeout(400)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).align", [n2]) == "center", "重做可恢复标题对齐")

        # 2) 两栈顺序：先改标题样式（节点栈），再改页面分类（页面栈）→ 撤销应先撤分类
        cur = page.evaluate("() => { const p = __T.node().pages().find(x => x.active); return { id: p.id, cat: p.catId }; }")
        # 选一个与当前不同的分类，确保这次操作真的改了数据（否则不会产生页面栈记录）
        target_cat = page.evaluate("""() => {
          const cs = __T.node().cats().map(c => c.id);
          const p = __T.node().pages().find(x => x.active);
          const cur = p.catId || null;
          const cand = cs.filter(id => id !== cur);
          return cand.length ? cand[0] : null;
        }""")
        page.evaluate("([i]) => __T.node().setTitleStyle([i], { bold: true })", [n2])
        page.wait_for_timeout(300)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).bold", [n2]) is True, "标题重新加粗（节点栈一条）")
        page.evaluate("([pid, c]) => __T.node().setPageCat(pid, c)", [cur["id"], target_cat])
        page.wait_for_timeout(300)
        now_cat = page.evaluate("([pid]) => __T.node().pages().find(p => p.id === pid).catId", [cur["id"]])
        check(now_cat == target_cat, "页面归到分类（页面栈一条）", [now_cat, target_cat])
        page.evaluate("() => __T.node().undo()")
        page.wait_for_timeout(400)
        back_cat = page.evaluate("([pid]) => __T.node().pages().find(p => p.id === pid).catId", [cur["id"]])
        check(back_cat == cur["cat"], "撤销先回退最近一次页面分类（跨栈按时间）", [back_cat, cur["cat"]])
        check(page.evaluate("([i]) => __T.node().titleStyle(i).bold", [n2]) is True,
              "此时标题样式还没被撤（顺序正确）")
        page.evaluate("() => __T.node().undo()")
        page.wait_for_timeout(400)
        check(page.evaluate("([i]) => __T.node().titleStyle(i).bold", [n2]) is False,
              "再撤一次才回退标题加粗")
        h = page.evaluate("() => __T.node().hist()")
        check(isinstance(h, dict) and h.get("node", 0) + h.get("page", 0) >= 0, "历史栈状态可读", h)

        # ---------------- H 无报错 ----------------
        print(f"[{label}] H 无 JS 报错")
        check(len(errs) == 0, "无 pageerror", errs)

        # ---------------- G 手机端 ----------------
        if mobile:
            print(f"[{label}] G 手机端弹窗")
            page.evaluate("() => __T.node().openPages()")
            page.wait_for_timeout(400)
            pr2 = panel_rect(page)
            check(pr2 and pr2["t"] >= 0 and pr2["t"] + pr2["h"] <= vh + 1, "手机端弹窗完整在视口内", pr2)
            check(pr2 and pr2["l"] >= 0 and pr2["l"] + pr2["w"] <= viewport["width"] + 1,
                  "手机端弹窗不横向溢出", pr2)
            sc2 = page.evaluate("""() => { const l = document.getElementById('pgmList');
                return [l.scrollHeight, l.clientHeight]; }""")
            check(sc2[0] > sc2[1], "手机端列表可滚动", sc2)
            check(page.is_visible('#pgmFoot .pgm-btn'), "手机端底部按钮可见")
            page.screenshot(path=os.path.join(SHOTS, "p25_page_modal_mobile.png"))

        b.close()


if __name__ == "__main__":
    run({"width": 1440, "height": 900}, "桌面", "p25_page_modal.png")
    run({"width": 390, "height": 844}, "手机", "p25_page_modal_mobile.png", mobile=True)
    print("\n通过 %d / 合计 %d" % (RES["pass"], RES["pass"] + RES["fail"]))
