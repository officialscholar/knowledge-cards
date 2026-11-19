# -*- coding: utf-8 -*-
"""第 149 条回归：使用说明弹窗（隐藏滚动条）+ 快捷键管理（可改键 / 冲突 / 恢复默认）

覆盖：
  A 使用说明：工具栏 ? 打开、章节切换、Esc / 遮罩关闭、记住上次章节、F1 呼出
  B 隐藏滚动条：内容区 overflow-y:auto 但滚动条宽度 0，仍能上下滚
  C 快捷键管理：列表项数、录键、冲突自动解绑、清空、固定别名保护、恢复默认、搜索过滤
  D 改键真正生效：新键触发、旧键失效、命令面板提示同步
  E 持久化：刷新后自定义键位还在
  F 原有快捷键不被破坏：Ctrl+K / Ctrl+E / Ctrl+A / Ctrl+D / Delete / Ctrl+Z / 空格
  G 手机端 390×844：弹窗不出屏、内容可滚
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


def sc(page, nid):
    return page.evaluate("(id) => __T.node().shortcut(id)", nid)


def set_sc(page, nid, combo):
    return page.evaluate("([id,c]) => __T.node().setShortcut(id,c)", [nid, combo])


def reset_sc(page):
    page.evaluate("() => __T.node().resetShortcuts()")


def visible(page, sel):
    return page.evaluate("""(s) => {
      const e = document.querySelector(s);
      if (!e) return false;
      if (e.style.display === 'none') return false;
      const r = e.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }""", sel)


def toast_text(page):
    return page.evaluate("() => (document.getElementById('toast') || {}).textContent || ''")


def open_usage(page):
    page.evaluate("() => __T.node().openUsage()")
    page.wait_for_timeout(220)


def close_usage(page):
    page.evaluate("() => __T.node().closeUsage()")
    page.wait_for_timeout(150)


def open_sc(page):
    page.evaluate("() => __T.node().openShortcuts()")
    page.wait_for_timeout(220)


def close_sc(page):
    page.evaluate("() => __T.node().closeShortcuts()")
    page.wait_for_timeout(150)


def record(page, nid, keys):
    page.evaluate("(id) => __T.node().recordShortcut(id)", nid)
    page.wait_for_timeout(120)
    page.keyboard.press(keys)
    page.wait_for_timeout(220)


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
    page.wait_for_timeout(250)
    a = add_node(page, 60 if mobile else 380, 120, "content", "说明测试节点")
    b = add_node(page, 60 if mobile else 760, 120, "content", "第二个节点")
    page.wait_for_timeout(350)

    # ---------------- A 使用说明弹窗 ----------------
    print(f"[{label}] A 使用说明弹窗")
    check(not visible(page, "#nodeUsageModal"), "初始状态说明弹窗是关的")

    page.evaluate("() => __T.node().toggleToolbar()")
    page.wait_for_timeout(250)
    if mobile:
        page.evaluate("() => document.getElementById('nodeHelpBtn').click()")
    else:
        page.click("#nodeHelpBtn")
    page.wait_for_timeout(350)
    check(visible(page, "#nodeUsageModal"), "工具栏 ? 按钮能打开使用说明")
    tabs = page.evaluate("() => __T.node().usageTabs()")
    check(len(tabs) == 6, "说明分 6 个章节（快速上手/节点/连线/分组与页面/导出与备份/快捷键）", tabs)
    check(page.evaluate("() => document.querySelectorAll('#nuTabs .nu-tab').length") == len(tabs),
          "章节按钮数量与数据一致")
    txt = page.evaluate("() => __T.node().usageText()")
    check("三步开始" in txt, "默认停在「快速上手」，正文有上手步骤", txt[:60])
    check("…" in txt or "⋯" in txt, "正文提到工具栏 ⋯ 展开", txt[:80])

    # ---------------- B 隐藏滚动条 ----------------
    print(f"[{label}] B 内容区可滚动但滚动条隐藏")
    bar = page.evaluate("""() => {
      const b = document.getElementById('nuBody');
      const cs = getComputedStyle(b);
      return { bar: b.offsetWidth - b.clientWidth, oy: cs.overflowY, sw: cs.scrollbarWidth };
    }""")
    check(bar["bar"] == 0, "滚动条宽度为 0（滑块隐藏）", bar)
    check(bar["oy"] == "auto", "内容区仍是可滚动的 overflow:auto", bar["oy"])
    check(bar["sw"] == "none", "computed scrollbar-width = none", bar["sw"])
    scroll = page.evaluate("""() => {
      const b = document.getElementById('nuBody');
      const old = b.style.maxHeight;
      b.style.maxHeight = '120px';
      const sh = b.scrollHeight, ch = b.clientHeight;
      b.scrollTop = 240;
      const st = b.scrollTop;
      b.style.maxHeight = old;
      b.scrollTop = 0;
      return { sh: sh, ch: ch, st: st };
    }""")
    check(scroll["sh"] > scroll["ch"], "内容高度超出可视高度（有可滚内容）", scroll)
    check(scroll["st"] > 0, "压矮后仍能滚动（scrollTop 变了）", scroll)

    # ---------------- 章节切换 ----------------
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p29_usage_desktop.png"))
    page.click('#nuTabs [data-nu-tab="edge"]')
    page.wait_for_timeout(250)
    check(page.evaluate("() => __T.node().usageTab()") == "edge", "点章节切到「连线」")
    t_edge = page.evaluate("() => __T.node().usageText()")
    check("折线" in t_edge and "组织架构图" in t_edge, "连线章节讲了折线与组织架构图", t_edge[:80])
    check("节点下面" in t_edge or "底下" in t_edge, "连线章节说明连线在节点下层", t_edge[:120])
    if not mobile:
        page.screenshot(path=os.path.join(SHOTS, "p29_usage_edge.png"))

    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    check(not visible(page, "#nodeUsageModal"), "Esc 关闭使用说明")
    open_usage(page)
    check(page.evaluate("() => __T.node().usageTab()") == "edge", "再打开时记住上次看的章节")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    # 遮罩点击关闭
    open_usage(page)
    page.mouse.click(6, vp["height"] - 6)
    page.wait_for_timeout(250)
    check(not visible(page, "#nodeUsageModal"), "点弹窗外的遮罩也能关闭")

    # F1 呼出
    page.keyboard.press("F1")
    page.wait_for_timeout(300)
    check(visible(page, "#nodeUsageModal"), "F1 能呼出使用说明")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    # 右键菜单入口
    rect = page.evaluate("(id) => { const r = document.querySelector('.node-item[data-node-id=\"' + id + '\"]').getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; }", a)
    page.mouse.click(rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] - 12, button="right")
    page.wait_for_timeout(400)
    menu_txt = page.evaluate("() => (document.getElementById('nodeMenu')||{}).innerText || ''")
    check("使用说明" in menu_txt and "快捷键管理" in menu_txt,
          "节点右键菜单里有「使用说明 / 快捷键管理」", menu_txt[-80:])
    page.evaluate("() => { const b = document.querySelector('#nodeMenu [data-menu=\"usage\"]'); if (b) b.click(); }")
    page.wait_for_timeout(350)
    check(visible(page, "#nodeUsageModal"), "右键菜单点「使用说明」能打开弹窗")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    # 「快捷键管理」按钮跳转
    open_usage(page)
    page.click("#nuShortcutBtn")
    page.wait_for_timeout(300)
    check(visible(page, "#nodeShortcutModal"), "说明里的「⌨ 快捷键管理」能打开快捷键面板")
    check(not visible(page, "#nodeUsageModal"), "跳转后使用说明已关闭")

    # ---------------- C 快捷键管理 ----------------
    print(f"[{label}] C 快捷键管理面板")
    rows = page.evaluate("() => document.querySelectorAll('#skBody .sk-row').length")
    lst = page.evaluate("() => __T.node().shortcutList()")
    check(rows == len(lst) and rows >= 15, "列表项数量与快捷键表一致", [rows, len(lst)])
    check(all(x["id"] not in ("delAlt", "redoAlt", "newpageAlt") for x in lst),
          "隐藏的备用键不在管理面板里露出", [x["id"] for x in lst][:5])
    check(page.evaluate("() => document.querySelectorAll('#skBody .sk-copy').length") == rows,
          "每行都有一个可点的按键块")
    check(sc(page, "editpanel") == "Ctrl+E", "默认键位与原来一致（编辑面板 Ctrl+E）", sc(page, "editpanel"))

    # 录键改 Ctrl+E → Ctrl+Shift+E? 会与导出冲突，用 Ctrl+Shift+E 试冲突
    record(page, "search", "Control+Shift+F")
    check(sc(page, "search") == "Ctrl+Shift+F", "录键后 search = Ctrl+Shift+F", sc(page, "search"))
    check(page.evaluate("() => __T.node().recording()") is None, "录完自动退出录键状态")
    check("已改" in page.evaluate("() => document.getElementById('skBody').innerText"),
          "被改过的项有「已改」标记")
    check("已自定义 1 项" in page.evaluate("() => (document.getElementById('skSub')||{}).textContent||''"),
          "标题栏统计自定义项数")

    # 冲突：把 export 抢到 Ctrl+K
    record(page, "export", "Control+K")
    check(sc(page, "export") == "Ctrl+K", "冲突键被新动作占用", sc(page, "export"))
    check(sc(page, "palette") == "", "被占用的「命令面板」自动解绑", sc(page, "palette"))
    check("解绑" in toast_text(page), "提示里说明另一个动作已解绑", toast_text(page))
    page.keyboard.press("Control+K")
    page.wait_for_timeout(300)
    check(not visible(page, "#commandPalette"), "解绑后 Ctrl+K 不再打开命令面板")
    check(visible(page, "#nodeExportModal"), "Ctrl+K 现在触发导出面板")
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)

    # 固定别名保护
    page.evaluate("() => __T.node().openShortcuts()")
    page.wait_for_timeout(200)
    record(page, "search", "Control+Alt+N")
    check(sc(page, "search") == "Ctrl+Shift+F", "固定别名 Ctrl+Alt+N 不能被抢（保持原值）", sc(page, "search"))
    check("固定占用" in toast_text(page), "提示该键被固定别名占用", toast_text(page))

    # 清空
    record(page, "duplicate", "Backspace")
    check(sc(page, "duplicate") == "", "Backspace 把该动作的键清空", sc(page, "duplicate"))
    check("未设置" in page.evaluate("() => document.getElementById('skBody').innerText"),
          "清空后列表显示「未设置」")

    # 搜索过滤
    page.fill("#skSearch", "页面")
    page.wait_for_timeout(200)
    n_page = page.evaluate("() => document.querySelectorAll('#skBody .sk-row').length")
    check(0 < n_page < rows, "搜索框按名字过滤", n_page)
    page.fill("#skSearch", "zzz")
    page.wait_for_timeout(200)
    check(page.evaluate("() => !!document.querySelector('#skBody .sk-empty')"), "无匹配时显示空状态")
    page.fill("#skSearch", "")
    page.wait_for_timeout(200)

    # 恢复默认
    page.click("#skResetAll")
    page.wait_for_timeout(300)
    check(sc(page, "search") == "Ctrl+F" and sc(page, "palette") == "Ctrl+K" and sc(page, "export") == "Ctrl+Shift+E",
          "恢复默认把所有键位还原", [sc(page, "search"), sc(page, "palette"), sc(page, "export")])
    check(sc(page, "duplicate") == "Ctrl+D", "被清空的动作也恢复默认")
    check("已改" not in page.evaluate("() => document.getElementById('skBody').innerText"),
          "恢复后不再有「已改」标记")

    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    check(not visible(page, "#nodeShortcutModal"), "Esc 关闭快捷键面板")

    # ---------------- D 改键真正生效 ----------------
    print(f"[{label}] D 改键后新键生效、旧键失效")
    set_sc(page, "search", "Ctrl+Shift+F")
    page.keyboard.press("Control+Shift+F")
    page.wait_for_timeout(300)
    check(visible(page, "#nodeSearchPanel"), "新键 Ctrl+Shift+F 能打开搜索面板")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    page.keyboard.press("Control+F")
    page.wait_for_timeout(300)
    check(not visible(page, "#nodeSearchPanel"), "旧键 Ctrl+F 已失效")
    # 命令面板提示同步
    page.keyboard.press("Control+K")
    page.wait_for_timeout(300)
    hint = page.evaluate("""() => {
      const it = Array.from(document.querySelectorAll('#cmdList .cmd-item'))
        .find(e => e.textContent.indexOf('搜索节点') !== -1);
      return it ? it.querySelector('.ci-hint').textContent : null;
    }""")
    check(hint == "Ctrl+Shift+F", "命令面板右侧提示跟着变成新键", hint)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    # 改回默认，方便后续
    set_sc(page, "search", "Ctrl+F")

    # ---------------- E 持久化 ----------------
    print(f"[{label}] E 刷新后自定义键位还在")
    set_sc(page, "editpanel", "Ctrl+Shift+P")
    page.wait_for_timeout(200)
    page.reload(timeout=90000)
    page.wait_for_timeout(1400)
    enter_node(page)
    check(sc(page, "editpanel") == "Ctrl+Shift+P", "刷新后自定义键位保留", sc(page, "editpanel"))
    check(sc(page, "search") == "Ctrl+F", "没改过的键位仍是默认", sc(page, "search"))
    ids = page.evaluate("() => __T.node().list().map(n => n.id)")
    check(len(ids) > 0, "刷新后节点还在（键盘测试要有节点）", len(ids))
    if ids:
        page.evaluate("() => __T.node().select([])")
        page.evaluate("(id) => __T.node().setSelection(id)", ids[0])
        page.wait_for_timeout(250)
    page.keyboard.press("Control+Shift+P")
    page.wait_for_timeout(350)
    check(page.evaluate("() => __T.node().panelOpen()"), "刷新后新键仍能打开编辑面板")
    page.keyboard.press("Control+Shift+P")
    page.wait_for_timeout(250)
    set_sc(page, "editpanel", "Ctrl+E")
    reset_sc(page)

    # ---------------- F 原有快捷键 ----------------
    print(f"[{label}] F 原有快捷键没被破坏")
    page.evaluate("() => __T.node().clearAll()")
    page.wait_for_timeout(200)
    n1 = add_node(page, 60 if mobile else 380, 120, "content", "快捷键甲")
    n2 = add_node(page, 60 if mobile else 760, 120, "content", "快捷键乙")
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.wait_for_timeout(250)
    sel = page.evaluate("() => __T.node().selection().multi")
    check(len(sel) == 2, "Ctrl+A 全选两个节点", sel)
    page.keyboard.press("Control+D")
    page.wait_for_timeout(400)
    check(len(page.evaluate("() => __T.node().list()")) == 4, "Ctrl+D 复制选中节点",
          len(page.evaluate("() => __T.node().list()")))
    before = page.evaluate("() => __T.node().hist()")
    page.keyboard.press("Control+Z")
    page.wait_for_timeout(400)
    after = page.evaluate("() => __T.node().hist()")
    check(after["redoNode"] > before["redoNode"], "Ctrl+Z 撤销（进重做栈）", [before, after])
    page.keyboard.press("Control+Y")
    page.wait_for_timeout(400)
    check(len(page.evaluate("() => __T.node().list()")) == 4, "Ctrl+Y 重做回来",
          len(page.evaluate("() => __T.node().list()")))
    page.evaluate("() => __T.node().select([])")
    page.evaluate("(id) => __T.node().setSelection(id)", n1)
    page.wait_for_timeout(250)
    page.keyboard.press("Delete")
    page.wait_for_timeout(400)
    if page.evaluate("() => { const o = document.getElementById('confirmOverlay'); return !!(o && o.classList.contains('show')); }"):
        page.click("#confirmOk")
        page.wait_for_timeout(450)
    check(len(page.evaluate("() => __T.node().list()")) == 3, "Delete 删除选中节点（二次确认后）",
          len(page.evaluate("() => __T.node().list()")))
    page.evaluate("() => __T.node().clearAll()")
    page.wait_for_timeout(250)
    n3 = add_node(page, 60 if mobile else 380, 120, "content", "聚焦节点")
    page.wait_for_timeout(300)
    page.evaluate("(id) => __T.node().select([id])", n3)
    page.wait_for_timeout(200)
    page.keyboard.press("Space")
    page.wait_for_timeout(450)
    check(page.evaluate("() => !!document.getElementById('nodeFocusView')"),
          "空格进入聚焦视图（最佳视图）")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # ---------------- G 手机端布局 ----------------
    if mobile:
        print(f"[{label}] G 弹窗不出屏")
        open_usage(page)
        box = page.evaluate("""() => {
          const p = document.querySelector('#nodeUsageModal .nu-panel');
          const r = p.getBoundingClientRect();
          return { l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width };
        }""")
        check(box["l"] >= -1 and box["r"] <= vp["width"] + 1, "说明弹窗宽度不超出屏幕", box)
        check(box["t"] >= -1 and box["b"] <= vp["height"] + 1, "说明弹窗高度不超出屏幕", box)
        check(page.evaluate("() => getComputedStyle(document.getElementById('nuFtip')).display") == "none",
              "窄屏隐藏底部提示文字，把空间留给内容")
        page.screenshot(path=os.path.join(SHOTS, "p29_usage_mobile.png"))
        close_usage(page)
        open_sc(page)
        box2 = page.evaluate("""() => {
          const p = document.querySelector('#nodeShortcutModal .nu-panel');
          const r = p.getBoundingClientRect();
          return { l: r.left, r: r.right, w: r.width };
        }""")
        check(box2["l"] >= -1 and box2["r"] <= vp["width"] + 1, "快捷键弹窗也不超出屏幕", box2)
        page.screenshot(path=os.path.join(SHOTS, "p29_shortcuts_mobile.png"))
        close_sc(page)
    else:
        open_sc(page)
        page.screenshot(path=os.path.join(SHOTS, "p29_shortcuts.png"))
        close_sc(page)

    # ---------------- H 报错 ----------------
    print(f"[{label}] H 无 JS 报错")
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
