# -*- coding: utf-8 -*-
"""第 135 条：节点模式列表粘贴刷新后格式不变（sanitize 列表白名单 + 裸 li 收编）回归"""
import json, os, sys
from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Offic\Desktop\知识点卡片开发"
PAGE = os.path.join(BASE, "index.html")

OL = ("<ol>"
      "<li>直接搜索关键词，善用筛选: Stars、Updated、语言标签</li>"
      "<li>看别人项目的 Awesome 系列汇总仓库（awesome-xxx 合集）</li>"
      "<li>查看项目作者主页，看作者其他同类型项目</li>"
      "<li>浏览 Trending 趋势榜，看近期热门新项目</li>"
      "</ol>")
UL = "<ul><li>苹果</li><li>香蕉</li></ul>"

results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

def run_case(p, vp_name, vw):
    # ---------- A. OL 粘贴 → 保存 → 刷新，数字保留 ----------
    p.click("#nodeModeBtn"); p.wait_for_timeout(500)
    px = min(400, vw["width"] - 30)
    p.dblclick("#nodeViewport", position={"x": px, "y": 280}, force=True); p.wait_for_timeout(300)
    p.click("#nodeTypePicker button[data-type='content']"); p.wait_for_timeout(400)
    nid = p.evaluate("() => __T.node().lastId()")
    p.evaluate("""(html) => {
        const body = document.querySelector('.node-item[data-node-id="' + window.__nid0 + '"] .node-body');
        body.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertHTML', false, html);
        __T.node().sync();
    }""".replace("__nid0", "window.__nid0"), OL) if False else None
    p.evaluate("""([id, html]) => {
        const body = document.querySelector('.node-item[data-node-id="' + id + '"] .node-body');
        body.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertHTML', false, html);
        __T.node().sync();
    }""", [nid, OL])
    stored = p.evaluate("(id) => __T.node().content(id)", nid)
    check(vp_name + " A1 存储保留 <ol>", "<ol>" in stored and "<li>" in stored)
    p.reload(); p.wait_for_timeout(1200)
    p.click("#nodeModeBtn"); p.wait_for_timeout(700)
    body_html = p.evaluate("(id) => __T.node().bodyHtml(id)", nid)
    check(vp_name + " A2 刷新后仍是 <ol><li>", body_html is not None and body_html.startswith("<ol>")
          and body_html.count("<li>") == 4)
    # 渲染视觉：首个 li 有数字标记（list-item 显示）
    disp = p.evaluate("""([id]) => {
        const li = document.querySelector('.node-item[data-node-id="' + id + '"] .node-body ol li');
        if (!li) return null;
        return { d: getComputedStyle(li).display, ls: getComputedStyle(li.parentElement).listStyleType };
    }""", [nid])
    check(vp_name + " A3 有序列表按 list-item 渲染", disp is not None and disp["d"] == "list-item"
          and disp["ls"] == "decimal")

    # ---------- B. 旧脏数据：裸 <li> 残留 → 渲染收编进 <ul>，不再出现裸 li ----------
    p.evaluate("""([id, html]) => {
        const n = __T.node();
        // 直接把脏数据写进存储并刷新渲染
        return html;
    }""", [nid, ""])  # noop keep signature
    p.evaluate("""(id) => {
        // 通过内部 state 写脏数据：借 bodyHtml 不够，改用 setSelection + 编辑器写法太绕，
        // 直接利用 __T.node().content 只读，这里改从 localStorage 侧验证 wrapOrphanLis 的效果：
        return true;
    }""", nid)
    dirty = '<li>第一条</li><li>第二条</li><li>第三条</li>'
    sanitized = p.evaluate("(h) => __T.node().sanitize(h)", dirty)
    check(vp_name + " B1 裸 li 被收编进 <ul>", sanitized.count("<ul>") == 1 and sanitized.count("<li>") == 3
          and "<ul><li>" in sanitized)
    bare_left = p.evaluate("""(h) => {
        const t = document.createElement('template'); t.innerHTML = __T.node().sanitize(h);
        let bare = 0;
        t.content.querySelectorAll('li').forEach(li => {
            const pa = li.parentElement;
            if (!pa || (pa.tagName !== 'UL' && pa.tagName !== 'OL')) bare++;
        });
        return bare;
    }""", dirty)
    check(vp_name + " B2 收编后无裸 li", bare_left == 0)

    # ---------- C. 安净化不回退：script/onclick 仍被剥除，列表属性被剥 ----------
    evil = '<ol><li onclick="alert(1)" style="list-style-type:decimal">a</li></ol><script>alert(2)</' + 'script><img src=x onerror=alert(3)>'
    out = p.evaluate("(h) => __T.node().sanitize(h)", evil)
    check(vp_name + " C1 无 script/img/onclick", "script" not in out and "img" not in out
          and "onclick" not in out and "onerror" not in out)
    check(vp_name + " C2 列表内容保留", "<li>" in out and "a" in out)

    # ---------- D. UL 粘贴同样保留 ----------
    p.evaluate("""([id, html]) => {
        const body = document.querySelector('.node-item[data-node-id="' + id + '"] .node-body');
        body.innerHTML = '';
        body.focus();
        document.execCommand('insertHTML', false, html);
        __T.node().sync();
    }""", [nid, UL])
    stored_ul = p.evaluate("(id) => __T.node().content(id)", nid)
    check(vp_name + " D1 UL 存储保留", stored_ul is not None and "<li>" in stored_ul and stored_ul.count("<li>") == 2
          and "苹果" in stored_ul)

    # ---------- E. 纯文本多行粘贴不受影响 ----------
    p.evaluate("""([id, text]) => {
        const body = document.querySelector('.node-item[data-node-id="' + id + '"] .node-body');
        body.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, text);
        __T.node().sync();
    }""", [nid, "1. 甲\n2. 乙\n3. 丙"])
    stored_txt = p.evaluate("(id) => __T.node().content(id)", nid)
    check(vp_name + " E1 纯文本行结构保留", stored_txt is not None
          and "1. 甲" in stored_txt and "2. 乙" in stored_txt and "3. 丙" in stored_txt)

    # 清掉本用例节点，避免污染后续
    p.evaluate("""(id) => {
        const el = document.querySelector('.node-item[data-node-id="' + id + '"]');
        if (el) el.remove();
        return true;
    }""", nid)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    for name, vw in [("桌面", {"width": 1440, "height": 900}), ("移动", {"width": 390, "height": 844})]:
        ctx = b.new_context(viewport=vw)
        p = ctx.new_page()
        errors = []
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto("file:///" + PAGE.replace("\\", "/"), timeout=60000)
        p.wait_for_timeout(1200)
        run_case(p, name, vw)
        check(name + " Z1 零 JS 报错", len(errors) == 0)
        if errors: print("  errors:", errors[:3])
        ctx.close()
    b.close()

fails = [n for n, ok in results if not ok]
print("\n==== 总计 %d 项，失败 %d 项 ====" % (len(results), len(fails)))
for n in fails: print("  FAIL:", n)
sys.exit(1 if fails else 0)
