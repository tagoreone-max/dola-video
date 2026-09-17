# -*- coding: utf-8 -*-
"""CDP 浏览器控制公共模块。

所有要连浏览器的脚本都必须先 import 本模块再 import playwright——
本模块会先经 env_common 完成代理绕过，否则系统代理会拦截 127.0.0.1
导致 CDP 请求返回 502。

与站点相关的只有 find_page() 的 host 参数，其余逻辑通用。
路径类配置（Chrome / profile / CDP / 产物目录）全部来自 env_common，可用环境变量覆盖。
"""
import json
import urllib.request

import env_common as env  # noqa: E402  (必须先于 playwright：代理绕过 + 输出编码)

from playwright.sync_api import sync_playwright  # noqa: E402

# 向下兼容导出
CDP_HTTP = env.CDP_HTTP
CHROME_EXE = env.CHROME_EXE
PROFILE_DIR = env.PROFILE_DIR
DOLA_URL = env.DOLA_URL
HOST = env.HOST
art_path = env.art_path
no_proxy_opener = env.no_proxy_opener


def get_ws_url(timeout=8):
    """拿 webSocketDebuggerUrl。失败抛出带诊断信息的异常。"""
    try:
        with no_proxy_opener().open(f"{CDP_HTTP}/json/version", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))["webSocketDebuggerUrl"]
    except Exception as e:
        raise RuntimeError(
            f"无法连接 CDP ({CDP_HTTP}): {e}\n"
            f"请先运行: python scripts/ensure_chrome.py launch\n"
            f"当前生效配置:\n{env.config_summary()}\n"
            f"若 Chrome 进程被 shell 回收，改用后台保活方式启动：\n"
            f'  "{CHROME_EXE}" --user-data-dir="{PROFILE_DIR}" '
            f"--remote-debugging-port=9222 --remote-allow-origins=* &"
        ) from e


def find_page(browser, host):
    """在已连接的浏览器中按 host 子串定位页面。"""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if host in pg.url.lower():
                return pg
    raise RuntimeError(
        f"未找到 {host} 页面，请确认受控 Chrome 已打开 {DOLA_URL}（可先跑 ensure_chrome.py tabs 看标签）。")


def connect(host=None):
    """返回 (playwright, browser, page)。调用方负责 pw.stop() / browser.close()。"""
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(get_ws_url())
    page = find_page(browser, host or HOST)
    page.bring_to_front()
    return pw, browser, page


def open_or_focus(browser, url, host, timeout=60):
    """打开新标签或聚焦已有标签，等待 DOM 就绪。返回 page。"""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if host in pg.url.lower():
                pg.bring_to_front()
                return pg
    ctx = browser.contexts[0]
    pg = ctx.new_page()
    pg.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
    pg.bring_to_front()
    pg.wait_for_timeout(2000)
    return pg


def snap(page, name, full=False):
    """截图到 ART_DIR（不落在仓库目录里）。返回实际路径。"""
    path = art_path(name)
    page.bring_to_front()
    page.wait_for_timeout(1200)
    page.screenshot(path=path, full_page=full)
    print(f"[snap] {path}")
    return path


def dump_buttons(page, pattern="", limit=40):
    """枚举可见可点击元素：文本 / 位置 / 标签。pattern 为正则（可选）。"""
    items = page.evaluate("""(pat) => {
        const re = pat ? new RegExp(pat, 'i') : null;
        const out = [];
        document.querySelectorAll('button,a,[role=button],[class*=btn],[class*=Btn],[class*=select],[class*=Select]')
        .forEach(el => {
            const t = (el.innerText || el.textContent || el.getAttribute('aria-label') || '')
                .replace(/\\s+/g, ' ').trim();
            const r = el.getBoundingClientRect();
            if (!t || t.length > 40) return;
            if (r.width <= 0 || r.height <= 0) return;
            if (r.bottom < 0 || r.right < 0) return;
            if (re && !re.test(t)) return;
            out.push({t: t.slice(0, 40),
                      x: Math.round(r.x + r.width / 2),
                      y: Math.round(r.y + r.height / 2),
                      w: Math.round(r.width), h: Math.round(r.height),
                      tag: el.tagName});
        });
        return out.slice(0, 200);
    }""", pattern)
    seen, uniq = set(), []
    for it in items:
        key = (it["t"], it["x"], it["y"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda i: (i["y"], i["x"]))
    for it in uniq[:limit]:
        print(f"  ({it['x']:>5},{it['y']:>5}) {it['w']:>4}x{it['h']:<3} [{it['tag'][:6]}] {it['t']}")
    return uniq


def page_text(page, limit=3000):
    """返回页面可见文本（前 limit 字符），用于判断登录态/页面结构。"""
    t = page.evaluate("() => document.body ? document.body.innerText : ''")
    return t[:limit]


def login_state(page, login_keywords=("登录/注册", "登录", "注册", "sign in", "log in")):
    """粗判是否未登录：页面文本含登录关键词即视为可能未登录（仅供参考，需人工确认）。"""
    t = page_text(page, 4000).lower()
    hit = [k for k in login_keywords if k.lower() in t]
    return {"login_buttons": hit, "maybe_logged_out": len(hit) > 0}
