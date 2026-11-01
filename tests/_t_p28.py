# -*- coding: utf-8 -*-
"""第 148 条回归：节点多层结构跟随圆角 + 宽度下限=高度（可收成正方形/正圆）+ 去掉节点 ✕ 删除控件

覆盖：
  A 裁剪层：每个节点都有 .node-clip，overflow:hidden，标题栏/正文/目录行都被裁进圆角
  B 标题栏圆角：跟随 --node-radius 变量（0 时是直角，40 时约 38.5），不是写死 12.5
  C 宽度下限 = 节点高度：minWidth 等于高度，超窄输入被夹住，收窄后锁成正方形
  D 圆角极限 = 正圆：正方形节点把圆角拉满 → 半径 = 宽/2，渲染出正圆
  E 还原：把宽度拉宽回去 → 取消正方形锁定、高度恢复自适应
  F 面板：宽度滑块 min = 节点高度、提示文案点到「正方形/正圆」
  G 删除控件：节点上不再有 ✕（.node-del-btn），右键菜单仍能删节点
  H 持久化：刷新后 width / radius / 正方形状态都还原
  I 导出：设了正方形 + 正圆仍能导出 PNG
  J 手机端 390×844：正方形与面板都正常
  K 全程无 JS 报错
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


def metrics(page, nid):
    return page.evaluate("""(id) => {
      const e = document.querySelector('.node-item[data-node-id="' + id + '"]');
      if (!e) return null;
      const clip = e.querySelector('.node-clip');
      const head = e.querySelector('.node-head');
      const body = e.querySelector('.node-body');
      return {
        w: e.offsetWidth, h: e.offsetHeight,
        square: e.classList.contains('is-square'),
        radius: getComputedStyle(e).borderTopLeftRadius,
        clip: !!clip,
        clipRadius: clip ? getComputedStyle(clip).borderTopLeftRadius : null,
        clipOverflow: clip ? getComputedStyle(clip).overflow : null,
        headRadius: head ? getComputedStyle(head).borderTopLeftRadius : null,
        bodyRadius: body ? getComputedStyle(body).borderTopLeftRadius : null,
        height: e.style.height || ''
      };
    }""", nid)


def node_rect(page, nid):
    return page.evaluate("""(id) => {
      const e = document.querySelector('.node-item[data-node-id="' + id + '"]');
      const r = e.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: r.width, h: r.height };
    }""", nid)


def inside(page, child_sel, nid):
    return page.evaluate("""([id, sel]) => {
      const e = document.querySelector('.node-item[data-node-id="' + id + '"]');
      const outer = e.getBoundingClientRect();
      const kids = Array.from(e.querySelectorAll(sel));
      if (!kids.length) return null;
      let worst = 0;
      kids.forEach(k => {
        const r = k.getBoundingClientRect();
        worst = Math.max(worst, outer.left - r.left, r.right - outer.right,
                          outer.top - r.top, r.bottom - outer.bottom);
      });
      return Math.round(worst * 10) / 10;
    }""", [nid, child_sel])


def min_width(page, nid):
    return page.evaluate("(id) => __T.node().minWidth(id)", nid)


def radius_max(page, nid):
    return page.evaluate("(id) => __T.node().radiusMax(id)", nid)


def computed_radius(page, nid):
    return page.evaluate("(id) => __T.node().borderRadiusPx(id)", nid)


def set_width(page, nid, w):
    page.evaluate("([id, w]) => __T.node().setWidth([id], w)", [nid, w])


def set_radius(page, nid, r):
    page.evaluate("([id, r]) => __T.node().setRadius([id], r)", [nid, r])


def add_toc_items(page, nid, names):
    page.click('.node-item[data-node-id="' + nid + '"] .toc-input')
    for nm in names:
        page.keyboard.type(nm)
        page.keyboard.press("Enter")
    page.wait_for_timeout(400)


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

    base_x = 40 if mobile else 380

    # ---------------- A 裁剪层 ----------------
    print(f"[{label}] A 节点多层结构跟随圆角")
    a = add_node(page, base_x, 110, "content", "内容节点")
    page.wait_for_timeout(350)
    m = metrics(page, a)
    check(m["clip"] is True, "节点内部有裁剪层 .node-clip", m)
    check(m["clipOverflow"] == "hidden", "裁剪层 overflow:hidden（内层不会溢出边框）", m["clipOverflow"])

    set_radius(page, a, 0)
    page.wait_for_timeout(250)
    m0 = metrics(page, a)
    check(m0["headRadius"] in ("0px", "0"), "圆角 0 时标题栏也是直角（不再写死 12.5）", m0["headRadius"])
    check(m0["clipRadius"] in ("0px", "0"), "圆角 0 时裁剪层也是直角", m0["clipRadius"])

    set_radius(page, a, 40)
    page.wait_for_timeout(250)
    m40 = metrics(page, a)
    head_r = float(str(m40["headRadius"]).replace("px", "") or 0)
    clip_r = float(str(m40["clipRadius"]).replace("px", "") or 0)
    check(abs(head_r - 38.5) < 0.6, "圆角 40 时标题栏圆角跟着变成 38.5（40 - 边框 1.5）", m40["headRadius"])
    check(abs(clip_r - 38.5) < 0.6, "圆角 40 时裁剪层圆角 38.5", m40["clipRadius"])
    out = inside(page, ".node-head", a)
    check(out is not None and out <= 0.6, "标题栏没有探出节点边框", out)
    out2 = inside(page, ".node-body", a)
    check(out2 is not None and out2 <= 0.6, "正文没有探出节点边框", out2)

    # 圆角拉到极限，内层仍然被裁在卡片里
    rmax = radius_max(page, a)
    set_radius(page, a, 9999)
    page.wait_for_timeout(300)
    m_big = metrics(page, a)
    check(float(str(m_big["radius"]).replace("px", "")) <= rmax + 0.6,
          "超大圆角被夹到短边一半", [m_big["radius"], rmax])
    out3 = inside(page, ".node-head", a)
    check(out3 is not None and out3 <= 0.6, "极限圆角下标题栏仍在卡片内", out3)

    # ---------------- B 目录节点 / 图片节点 ----------------
    print(f"[{label}] B 目录节点与图片节点的内层同样跟随圆角")
    t = add_node(page, base_x, 420, "toc", "目录节点")
    page.wait_for_timeout(300)
    add_toc_items(page, t, ["条目甲", "条目乙", "条目丙"])
    set_radius(page, t, 30)
    page.wait_for_timeout(350)
    mt = metrics(page, t)
    check(mt["clip"] is True and mt["clipOverflow"] == "hidden", "目录节点也有裁剪层", mt)
    check(abs(float(str(mt["clipRadius"]).replace("px", "")) - 28.5) < 0.6,
          "目录节点裁剪层圆角 = 30 - 1.5", mt["clipRadius"])
    rows_out = inside(page, ".toc-row", t)
    check(rows_out is not None and rows_out <= 0.6, "目录条目行没有探出节点边框", rows_out)

    # 图片节点的内圆角：直接造一个 image-only 结构验证变量跟随
    img_r = page.evaluate("""(id) => {
      const e = document.querySelector('.node-item[data-node-id="' + id + '"]');
      e.classList.add('image-only');
      const d = document.createElement('div');
      d.className = 'node-images';
      d.innerHTML = '<div class="node-img-item"><img alt=""></div>';
      e.querySelector('.node-clip').appendChild(d);
      e.style.setProperty('--node-radius', '40px');
      const item = e.querySelector('.node-img-item');
      const r = getComputedStyle(item).borderTopLeftRadius;
      e.classList.remove('image-only');
      e.style.removeProperty('--node-radius');
      if (d.parentNode) d.remove();
      return r;
    }""", a)
    check(abs(float(str(img_r).replace("px", "") or 0) - 38.5) < 0.6,
          "图片节点内圆角跟随变量（40 - 1.5 = 38.5）", img_r)
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p28_corner_layers.png"))

    # ---------------- C 宽度下限 = 高度 ----------------
    print(f"[{label}] C 宽度下限 = 节点高度")
    b = add_node(page, base_x, 640, "content", "方形试验")
    page.wait_for_timeout(350)
    mb = metrics(page, b)
    mw = min_width(page, b)
    check(mw == mb["h"], "宽度下限等于当前高度", [mw, mb["h"]])
    set_width(page, b, 40)
    page.wait_for_timeout(350)
    m2 = metrics(page, b)
    check(m2["w"] >= 40, "输入 40 不会变成 40（有下限）", m2["w"])
    check(m2["w"] <= mb["h"] + 1, "最窄只收到与高度相等", [m2["w"], mb["h"]])
    check(m2["w"] == m2["h"], "收窄后节点是正方形", [m2["w"], m2["h"]])
    check(m2["square"] is True, "正方形节点带 is-square 标记", m2["square"])
    check(m2["height"] != "", "正方形节点高度被锁定（内联 height）", m2["height"])

    # ---------------- D 圆角极限 = 正圆 ----------------
    print(f"[{label}] D 圆角极限把节点变成正圆")
    sq = metrics(page, b)
    check(radius_max(page, b) == int(sq["w"] // 2), "正方形节点圆角上限 = 宽的一半", [radius_max(page, b), sq["w"]])
    set_radius(page, b, 9999)
    page.wait_for_timeout(300)
    rd = computed_radius(page, b)
    check(abs(rd - sq["w"] / 2) <= 1, "拉满后渲染半径 = 宽的一半（正圆）", [rd, sq["w"]])
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p28_circle_desktop.png"))

    # ---------------- E 拉宽还原 ----------------
    print(f"[{label}] E 拉宽后还原为自适应高度")
    set_width(page, b, 320)
    page.wait_for_timeout(350)
    m3 = metrics(page, b)
    check(m3["square"] is False, "拉宽后取消正方形锁定", m3["square"])
    check(m3["height"] == "", "内联高度被清掉", m3["height"])
    check(m3["w"] == 320, "宽度按设置生效", m3["w"])
    check(m3["h"] < m3["w"], "高度回到自适应（小于宽度）", [m3["w"], m3["h"]])

    # ---------------- F 面板 ----------------
    print(f"[{label}] F 面板宽度下限与提示")
    page.evaluate("(id) => __T.node().setSelection(id)", b)
    page.wait_for_timeout(250)
    page.evaluate("() => __T.node().openPanel()")
    page.wait_for_timeout(400)
    pmin = page.evaluate("() => Number(document.getElementById('nepWidthRange').min)")
    pnum = page.evaluate("() => Number(document.getElementById('nepWidthNum').min)")
    mm = metrics(page, b)
    check(pmin == mm["h"] or pmin == mm["w"], "面板滑块 min = 节点高度", [pmin, mm["h"]])
    check(pnum == pmin, "数字框 min 与滑块一致", [pnum, pmin])
    tipw = page.evaluate("() => document.querySelectorAll('#nepBody .nep-tip')[0].textContent")
    check("正方形" in tipw, "宽度提示里说明了「正方形」", tipw)
    tipl = page.evaluate("() => document.getElementById('nepRadiusTip').textContent")
    check("正圆" in tipl, "圆角提示里说明了「正圆」", tipl)
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p28_panel_limits.png"))

    # 面板里把宽度拉到最小 → 正方形
    page.fill("#nepWidthNum", "40")
    page.wait_for_timeout(500)
    m4 = metrics(page, b)
    check(m4["square"] is True and m4["w"] == m4["h"], "面板里输入超窄值也收成正方形", [m4["w"], m4["h"]])
    page.evaluate("() => __T.node().closePanel()")
    page.wait_for_timeout(250)

    # ---------------- G 删除控件 ----------------
    print(f"[{label}] G 节点上不再有 ✕ 删除控件")
    n_del = page.evaluate("() => document.querySelectorAll('.node-del-btn').length")
    check(n_del == 0, "页面里没有 .node-del-btn", n_del)
    cnt_before = page.evaluate("() => __T.node().list().length")
    mr = node_rect(page, b)
    page.mouse.click(mr["left"] + mr["w"] / 2, mr["top"] + 12, button="right")
    page.wait_for_timeout(400)
    menu_del = page.evaluate("() => { const el = document.querySelector('#nodeMenu'); return el && el.style.display !== 'none'; }")
    check(menu_del is True, "右键能打开节点菜单", menu_del)
    has_del = page.evaluate("() => !!document.querySelector('#nodeMenu button[data-menu=\"delete\"]')")
    check(has_del is True, "菜单里仍有「删除节点」", has_del)
    page.click("#nodeMenu button[data-menu=\"delete\"]")
    page.wait_for_timeout(400)
    confirm_shown = page.evaluate("() => { const o = document.getElementById('confirmOverlay'); return !!o && getComputedStyle(o).display !== 'none'; }")
    check(confirm_shown is True, "删除前有二次确认（防误删）", confirm_shown)
    page.evaluate("() => { const b = document.getElementById('confirmOk'); if (b) b.click(); }")
    page.wait_for_timeout(500)
    cnt_after = page.evaluate("() => __T.node().list().length")
    check(cnt_after == cnt_before - 1, "右键菜单能删掉节点", [cnt_before, cnt_after])

    # ---------------- H 持久化 ----------------
    print(f"[{label}] H 刷新后还原")
    h = add_node(page, base_x, 200, "content", "持久化方形")
    page.wait_for_timeout(350)
    set_width(page, h, 60)
    page.wait_for_timeout(200)
    page.evaluate("(id) => __T.node().setRadius([id], 9999)", h)
    page.wait_for_timeout(700)
    page.reload()
    page.wait_for_timeout(1500)
    enter_node(page)
    page.wait_for_timeout(700)
    m5 = metrics(page, h)
    check(m5 is not None, "刷新后节点还在")
    if m5:
        check(m5["w"] == m5["h"], "刷新后仍然是正方形", [m5["w"], m5["h"]])
        check(m5["square"] is True, "刷新后 is-square 还原", m5["square"])
        check(abs(computed_radius(page, h) - m5["w"] / 2) <= 1, "刷新后圆角仍是正圆",
              [computed_radius(page, h), m5["w"]])
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p28_reload_desktop.png"))

    # ---------------- I 导出 ----------------
    print(f"[{label}] I 导出图片仍可用")
    if page.evaluate("() => document.getElementById('nodeToolbar').classList.contains('nt-collapsed')"):
        page.evaluate("() => document.getElementById('nodeToolbarMore').click()")
        page.wait_for_timeout(250)
    page.evaluate("() => document.getElementById('nodeExportBtn').click()")
    page.wait_for_timeout(500)
    dl_ok, fname = False, ""
    try:
        with page.expect_download(timeout=40000) as di:
            page.click("#nemCurrentBtn")
        d = di.value
        fname = d.suggested_filename
        dl_ok = fname.endswith(".png")
    except Exception as e:
        fname = "ERR " + str(e)[:120]
    check(dl_ok, "正方形 + 正圆状态下导出 PNG 成功", fname)
    page.wait_for_timeout(400)
    page.evaluate("() => { const b = document.getElementById('nemCancelBtn'); if (b && b.offsetParent) b.click(); }")

    # ---------------- K 报错 ----------------
    print(f"[{label}] K 无 JS 报错")
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
