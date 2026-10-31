# -*- coding: utf-8 -*-
"""第 146 条回归：连线画在节点下层 + 三种走线方式（曲线 / 直线 / 折线）

覆盖：
  A 图层顺序：连线 SVG 在节点层之下；连线穿过节点时命中节点而不是连线；标签/浮动条仍在节点之上
  B 走线几何：曲线含 C；直线只有 M/L 两点；折线全为正交折线段（每段要么水平要么垂直）
  C 单条切换：数据、DOM class、刷新后保持、撤销可回退
  D 全部切换：本页全部连线一次改样式；新连线继承默认样式；排版面板按钮生效并高亮
  E 浮动条：选中连线出现三个样式按钮、当前项高亮、点击即切、可单独改回
  F 导出图片：当前页导出 PNG 仍能成功（导出走同一套几何计算）
  G 手机端 390×844：连线仍在下层、浮动条不溢出、三种样式都能切
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


def connect(page, a, b, fs="right", ts="left"):
    return page.evaluate("([a,b,fs,ts]) => __T.node().connect(a,b,fs,ts)", [a, b, fs, ts])


def edges(page):
    return page.evaluate("() => __T.node().edgeList()")


def path_points(page, edge_id):
    return page.evaluate("""(id) => {
      const d = __T.node().edgePathD(id);
      if (!d) return null;
      const nums = (d.match(/-?\\d+(?:\\.\\d+)?/g) || []).map(Number);
      const pts = [];
      for (let i = 0; i + 1 < nums.length; i += 2) pts.push({ x: nums[i], y: nums[i + 1] });
      return { d: d, pts: pts };
    }""", edge_id)


def is_orthogonal(pts, tol=0.6):
    for i in range(1, len(pts)):
        dx = abs(pts[i]["x"] - pts[i - 1]["x"])
        dy = abs(pts[i]["y"] - pts[i - 1]["y"])
        if not (dx <= tol or dy <= tol):
            return False
    return True


def select_edge(page, edge_id):
    return page.evaluate("""(id) => {
      const g = document.querySelector('.node-edge-group[data-edge-id="' + id + '"] .node-edge-hit');
      if (!g) return false;
      g.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      return true;
    }""", edge_id)


def z_of(page, sel):
    return page.evaluate("(s) => { const e = document.querySelector(s); return e ? getComputedStyle(e).zIndex : null; }", sel)


def run(viewport, label, mobile=False):
    print(f"\n=== {label} {viewport['width']}x{viewport['height']} ===")
    vw, vh = viewport["width"], viewport["height"]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=viewport)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, timeout=90000)
        page.wait_for_timeout(1200)
        enter_node(page)
        page.evaluate("() => __T.node().clearAll()")
        page.wait_for_timeout(200)

        # ---------------- A 图层顺序 ----------------
        print(f"[{label}] A 连线在节点下层")
        z_svg = z_of(page, "#nodeEdgeSvg")
        z_layer = z_of(page, "#nodeLayer")
        z_label = z_of(page, "#edgeLabelLayer")
        check(z_svg is not None and z_layer is not None and int(z_svg) < int(z_layer),
              "连线层 z-index < 节点层 z-index", {"edge": z_svg, "node": z_layer})
        check(z_label is not None and int(z_label) > int(z_layer),
              "标签/浮动条层仍在节点之上（否则点不到）", {"label": z_label, "node": z_layer})

        # 造一条横穿中间节点的斜直线（终点故意错开高度，避免退化成水平线）
        a = add_node(page, 40, 200, "content", "起点")
        c = add_node(page, 780, 520, "content", "终点")
        mid = add_node(page, 300, 330, "content", "中间节点")
        page.wait_for_timeout(150)
        eid = connect(page, a, c, "right", "left")
        page.evaluate("() => __T.node().setEdgeRouteAll('line')")
        page.wait_for_timeout(300)
        page.evaluate("() => __T.node().fit()")
        page.wait_for_timeout(350)
        cross = page.evaluate("""([id, eid]) => {
          const el = document.querySelector('.node-item[data-node-id="' + id + '"]');
          const r = el.getBoundingClientRect();
          const svg = document.getElementById('nodeEdgeSvg');
          const cm = svg.getScreenCTM();
          const d = __T.node().edgePathD(eid) || '';
          const nums = (d.match(/-?\\d+(?:\\.\\d+)?/g) || []).map(Number);
          const pts = [];
          for (let i = 0; i + 1 < nums.length; i += 2) {
            pts.push({ x: cm.a * nums[i] + cm.c * nums[i+1] + cm.e,
                       y: cm.b * nums[i] + cm.d * nums[i+1] + cm.f });
          }
          // 线段与节点矩形是否相交（Liang-Barsky）
          const hitRect = (p1, p2) => {
            let t0 = 0, t1 = 1;
            const dx = p2.x - p1.x, dy = p2.y - p1.y;
            const clip = (p, q) => {
              if (p === 0) return q >= 0;
              const t = q / p;
              if (p < 0) { if (t > t1) return false; if (t > t0) t0 = t; }
              else { if (t < t0) return false; if (t < t1) t1 = t; }
              return true;
            };
            return clip(-dx, p1.x - r.left) && clip(dx, r.right - p1.x) &&
                   clip(-dy, p1.y - r.top) && clip(dy, r.bottom - p1.y);
          };
          let crosses = false;
          for (let i = 1; i < pts.length; i++) if (hitRect(pts[i-1], pts[i])) { crosses = true; break; }
          const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
          const list = document.elementsFromPoint(cx, cy).map(n =>
            (n.className && n.className.baseVal !== undefined) ? n.className.baseVal : (n.className || n.tagName));
          return { crosses: crosses, rect: { l: r.left, t: r.top, w: r.width, h: r.height }, hit: list, pts: pts };
        }""", [mid, eid])
        check(cross["crosses"] is True, "连线确实横穿了这个节点（几何相交）", cross.get("pts"))
        check(cross["rect"]["w"] > 5, "被测节点在视口内（已适应画布）", cross.get("rect"))
        hit = cross["hit"]
        check(any("node-item" in x for x in hit), "连线穿过的位置顶层是节点卡片", hit)
        check(not any("node-edge-group" in x or x == "node-edge" for x in hit[:3]),
              "连线没有盖在节点上面（命中顺序里连线在节点之后）", hit)
        if not mobile:
            page.screenshot(path=os.path.join(SHOTS, "p26_cross_under.png"))

        # ---------------- B 走线几何 ----------------
        print(f"[{label}] B 三种走线几何")
        check(len(edges(page)) == 1 and edges(page)[0]["route"] == "line", "先设成直线，数据已记录", edges(page))
        g = path_points(page, eid)
        check(g and "C" not in g["d"] and "Q" not in g["d"], "直线 d 里没有曲线指令", g and g["d"][:120])
        check(g and len(g["pts"]) == 2, "直线只有两个端点", g and g["pts"])
        straight_ok = g and len(g["pts"]) == 2 and (
            abs(g["pts"][0]["x"] - g["pts"][1]["x"]) > 1 and abs(g["pts"][0]["y"] - g["pts"][1]["y"]) > 1)
        check(straight_ok, "直线确实是斜直连（不是退化成水平/垂直）", g and g["pts"])

        page.evaluate("() => __T.node().setEdgeRouteAll('curve')")
        page.wait_for_timeout(250)
        g2 = path_points(page, eid)
        check(g2 and " C " in g2["d"], "曲线 d 里是三次贝塞尔", g2 and g2["d"][:120])

        page.evaluate("() => __T.node().setEdgeRouteAll('elbow')")
        page.wait_for_timeout(250)
        g3 = path_points(page, eid)
        check(g3 and "C" not in g3["d"], "折线不含曲线指令", g3 and g3["d"][:160])
        check(g3 is not None and len(g3["pts"]) >= 4, "折线段数足够（两端直段 + 中线）", g3 and len(g3["pts"]))
        check(g3 is not None and is_orthogonal(g3["pts"]), "折线每一段都是水平或垂直", g3 and g3["pts"])
        cls = page.evaluate("(id) => __T.node().edgeDomTag(id)", eid)
        check(cls is not None and "route-elbow" in cls, "连线组带 route-elbow 标记", cls)

        # 折线的中点应落在路径上（用于关系说明标签）
        midp = page.evaluate("""(id) => {
          const g = document.querySelector('.node-edge-group[data-edge-id="' + id + '"]');
          const p = g ? g.querySelector('.node-edge') : null;
          if (!p) return null;
          const L = p.getTotalLength();
          const m = p.getPointAtLength(L / 2);
          return { len: L, x: m.x, y: m.y };
        }""", eid)
        check(midp and midp["len"] > 100, "折线路径长度正常（可算中点）", midp)

        # ---------------- C 单条切换 + 持久化 + 撤销 ----------------
        print(f"[{label}] C 单条切换 / 持久化 / 撤销")
        page.evaluate("([id]) => __T.node().setEdgeRoute(id, 'line')", [eid])
        page.wait_for_timeout(200)
        check(edges(page)[0]["route"] == "line", "单条改成直线", edges(page))
        page.evaluate("() => __T.node().undo()")
        page.wait_for_timeout(300)
        check(edges(page)[0]["route"] == "elbow", "撤销回折线", edges(page))
        page.evaluate("() => __T.node().redo()")
        page.wait_for_timeout(300)
        check(edges(page)[0]["route"] == "line", "重做回直线", edges(page))
        page.evaluate("([id]) => __T.node().setEdgeRoute(id, 'elbow')", [eid])
        page.wait_for_timeout(400)
        page.reload()
        page.wait_for_timeout(1500)
        enter_node(page)
        page.wait_for_timeout(400)
        persisted = [e["route"] for e in edges(page)]
        check(persisted and persisted[0] == "elbow", "刷新后走线方式仍在", persisted)

        # ---------------- D 全部切换 ----------------
        print(f"[{label}] D 本页全部切换 + 新连线继承")
        page.evaluate("() => __T.node().clearAll()")
        p0 = add_node(page, 300, 120, "title", "父")
        k1 = add_node(page, 120, 420, "content", "子一")
        k2 = add_node(page, 520, 420, "content", "子二")
        page.wait_for_timeout(150)
        n_all = page.evaluate("([ids,pid]) => __T.node().batchParent(ids, pid)", [[k1, k2], p0])
        page.wait_for_timeout(300)
        es = edges(page)
        check(len(es) == 2 and all(e["kind"] == "parent" for e in es), "父子连线已建立", es)
        check(all(e["fromSide"] in ("bottom", "top") for e in es),
              "子节点在下方 → 父子连线自动走 上→下 端口（组织架构图竖排）", es)
        page.evaluate("() => __T.node().setEdgeRouteAll('elbow')")
        page.wait_for_timeout(300)
        check(all(e["route"] == "elbow" for e in edges(page)), "本页全部改为折线", edges(page))
        if not mobile:
            page.evaluate("() => __T.node().fit()")
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(SHOTS, "p26_org_elbow.png"))
        e_new = connect(page, k1, k2, "right", "left")
        page.wait_for_timeout(250)
        new_route = [e["route"] for e in edges(page) if e["id"] == e_new]
        check(new_route == ["elbow"], "之后新连的线继承折线默认", new_route)

        # 排版面板：三个按钮 + 高亮
        if page.evaluate("() => document.getElementById('nodeToolbar').classList.contains('nt-collapsed')"):
            page.evaluate("() => document.getElementById('nodeToolbarMore').click()")
            page.wait_for_timeout(200)
        page.evaluate("() => document.getElementById('nodeLayoutBtn').click()")
        page.wait_for_timeout(250)
        btns = page.evaluate("""() => Array.from(document.querySelectorAll('#nodeLayoutPanel [data-edge-route]'))
            .map(b => ({ r: b.dataset.edgeRoute, on: b.classList.contains('on'), w: b.getBoundingClientRect().width }))""")
        check(len(btns) == 3, "排版面板有三个连线样式按钮", btns)
        check(any(x["on"] and x["r"] == "elbow" for x in btns), "当前样式（折线）高亮", btns)
        check(all(x["w"] > 20 for x in btns), "三个按钮都有可点面积", btns)
        page.click('#nodeLayoutPanel [data-edge-route="curve"]')
        page.wait_for_timeout(350)
        check(all(e["route"] == "curve" for e in edges(page)), "点面板「曲线」→ 全部改回曲线", edges(page))
        on_curve = page.evaluate("""() => Array.from(document.querySelectorAll('#nodeLayoutPanel [data-edge-route]'))
            .map(b => b.dataset.edgeRoute + (b.classList.contains('on') ? '*' : ''))""")
        check(on_curve == ["curve*", "line", "elbow"], "面板高亮跟着切换", on_curve)
        page.evaluate("() => document.getElementById('nodeLayoutBtn').click()")
        page.wait_for_timeout(150)

        # ---------------- E 浮动条 ----------------
        print(f"[{label}] E 浮动条三个样式按钮")
        page.evaluate("() => __T.node().clearAll()")
        m1 = add_node(page, 80, 200, "content", "节点一")
        m2 = add_node(page, 80, 460, "content", "节点二")
        page.wait_for_timeout(150)
        e2 = connect(page, m1, m2, "right", "left")
        page.wait_for_timeout(300)
        check(select_edge(page, e2) is True, "点击连线可选中")
        page.wait_for_timeout(250)
        bar = page.evaluate("""() => {
          const b = document.querySelector('.edge-toolbar');
          if (!b) return null;
          const r = b.getBoundingClientRect();
          return {
            routes: Array.from(b.querySelectorAll('[data-action="route"]')).map(x => x.dataset.route),
            active: Array.from(b.querySelectorAll('[data-action="route"]')).filter(x => x.classList.contains('active')).map(x => x.dataset.route),
            others: Array.from(b.querySelectorAll('[data-action="label"],[data-action="reverse"],[data-action="delete"]')).length,
            svg: b.querySelectorAll('[data-action="route"] svg').length,
            rect: { l: r.left, t: r.top, w: r.width, h: r.height }
          };
        }""")
        check(bar is not None, "浮动条已出现", bar)
        check(bar and bar["routes"] == ["curve", "line", "elbow"], "浮动条有三个样式按钮", bar and bar["routes"])
        check(bar and bar["active"] == ["curve"], "默认高亮曲线", bar and bar["active"])
        check(bar and bar["svg"] == 3, "按钮用 SVG 图标（区分度更好）", bar and bar["svg"])
        check(bar and bar["others"] == 3, "原有 编辑/反转/删除 三个按钮还在", bar and bar["others"])
        if bar:
            check(bar["rect"]["l"] >= -1 and bar["rect"]["l"] + bar["rect"]["w"] <= vw + 1,
                  "浮动条不横向溢出视口", bar["rect"])
        page.click('.edge-toolbar [data-action="route"][data-route="elbow"]')
        page.wait_for_timeout(300)
        check([e["route"] for e in edges(page) if e["id"] == e2] == ["elbow"], "点浮动条「折线」→ 该条变折线", edges(page))
        act2 = page.evaluate("""() => Array.from(document.querySelectorAll('.edge-toolbar [data-action="route"]'))
            .filter(x => x.classList.contains('active')).map(x => x.dataset.route)""")
        check(act2 == ["elbow"], "浮动条高亮切到折线", act2)
        page.click('.edge-toolbar [data-action="route"][data-route="line"]')
        page.wait_for_timeout(300)
        check([e["route"] for e in edges(page) if e["id"] == e2] == ["line"], "再点「直线」→ 该条变直线", edges(page))
        if not mobile:
            page.screenshot(path=os.path.join(SHOTS, "p26_edge_toolbar.png"))

        # ---------------- F 导出 ----------------
        print(f"[{label}] F 导出图片仍可用")
        page.evaluate("() => __T.node().setEdgeRouteAll('elbow')")
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
        check(ok_dl, "折线状态下导出 PNG 成功", fname)
        page.wait_for_timeout(500)
        page.evaluate("() => { const b = document.getElementById('nemCancelBtn'); if (b && b.offsetParent) b.click(); }")

        # ---------------- H 无报错 ----------------
        print(f"[{label}] H 无 JS 报错")
        check(len(errs) == 0, "无 pageerror", errs)

        # ---------------- G 手机端 ----------------
        if mobile:
            print(f"[{label}] G 手机端")
            page.evaluate("() => __T.node().clearAll()")
            s1 = add_node(page, 30, 120, "content", "甲")
            s2 = add_node(page, 30, 400, "content", "乙")
            page.wait_for_timeout(150)
            e3 = connect(page, s1, s2, "bottom", "top")
            page.wait_for_timeout(300)
            zs = z_of(page, "#nodeEdgeSvg")
            zl = z_of(page, "#nodeLayer")
            check(int(zs) < int(zl), "手机端连线同样在节点下层", {"edge": zs, "node": zl})
            for r in ("line", "elbow", "curve"):
                page.evaluate("([id,r]) => __T.node().setEdgeRoute(id, r)", [e3, r])
                page.wait_for_timeout(150)
                got = [x["route"] for x in edges(page) if x["id"] == e3]
                check(got == [r], f"手机端可切到 {r}", got)
            page.evaluate("([id]) => { __T.node().setEdgeRoute(id,'elbow'); }", [e3])
            page.wait_for_timeout(200)
            select_edge(page, e3)
            page.wait_for_timeout(250)
            br = page.evaluate("""() => { const b = document.querySelector('.edge-toolbar'); if (!b) return null;
                const r = b.getBoundingClientRect(); return { l: r.left, t: r.top, w: r.width, h: r.height }; }""")
            check(br is not None and br["l"] >= -1 and br["l"] + br["w"] <= vw + 1,
                  "手机端浮动条不横向溢出", br)
            check(br is not None and br["t"] >= 0, "手机端浮动条不被顶出屏幕", br)
            page.screenshot(path=os.path.join(SHOTS, "p26_elbow_mobile.png"))

        b.close()


if __name__ == "__main__":
    run({"width": 1440, "height": 900}, "桌面")
    run({"width": 390, "height": 844}, "手机", mobile=True)
    print("\n通过 %d / 合计 %d" % (RES["pass"], RES["pass"] + RES["fail"]))
    if RES["fail"]:
        raise SystemExit(1)
