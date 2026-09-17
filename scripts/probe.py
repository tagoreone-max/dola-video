# -*- coding: utf-8 -*-
"""探测 dola.com（豆包国际版）视频生成界面结构。

实测 dola 为**中文界面**（与国内豆包同构），关键词匹配中英并存。
首次使用或界面改版时，先跑本脚本校准选择器。

用法:
    python probe.py          # 打印视频生成入口 / 上传控件 / 参数按钮 / 发送按钮
    python probe.py --snap   # 额外截图到 $DOLA_ART_DIR/dola_probe.png
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browser_common as bc  # noqa: E402

HOST = bc.HOST

SCAN_JS = r"""
() => {
  const out = {url: location.href, title: document.title,
               files: [], editors: [], buttons: [], videos: [],
               body: (document.body.innerText || '').slice(0, 1200)};
  document.querySelectorAll('input[type=file]').forEach(i => {
    const r = i.getBoundingClientRect();
    out.files.push({accept: (i.accept || '(any)').slice(0, 100), multiple: i.multiple,
                    visible: r.width > 0, rect: [Math.round(r.x), Math.round(r.y)]});
  });
  document.querySelectorAll('textarea,[contenteditable=true]').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width <= 0) return;
    out.editors.push({tag: e.tagName, cls: String(e.className).slice(0, 60),
                      ph: (e.getAttribute('placeholder') || e.getAttribute('data-placeholder') || '').slice(0, 80),
                      rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]});
  });
  const KEY = new RegExp('视频生成|图像生成|上传|发送|比例|时长|模型|自动|生成中|排队|创作中'
    + '|video|image|upload|send|ratio|duration|aspect|model|seedance'
    + '|9:16|16:9|\\b4s\\b|\\b5s\\b|\\b10s\\b|\\b15s\\b', 'i');
  [...document.querySelectorAll('button,[role=button],a,div,span')].forEach(el => {
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    const al = el.getAttribute('aria-label') || '';
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return;
    if ((t && t.length < 40 && KEY.test(t)) || (al && KEY.test(al))) {
      out.buttons.push({t: t.slice(0, 40), al: al.slice(0, 40),
                        x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)});
    }
  });
  document.querySelectorAll('video').forEach(v => {
    const src = v.src || v.currentSrc || '';
    if (src) out.videos.push({src: src.slice(0, 100)});
  });
  const seen = new Set();
  out.buttons = out.buttons.filter(b => {
    const k = b.t + b.al + b.x + b.y;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  }).slice(0, 60);
  return out;
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", action="store_true", help="额外截图到 ART_DIR")
    args = ap.parse_args()

    pw, browser, page = bc.connect(HOST)
    try:
        page.bring_to_front()
        page.wait_for_timeout(2000)
        d = page.evaluate(SCAN_JS)
        print(f"=== {d['title']} ===")
        print(f"URL: {d['url']}")
        print("\n--- 文件上传控件 ---")
        for f in d["files"]:
            print(f"  accept={f['accept']} multiple={f['multiple']} visible={f['visible']} rect={f['rect']}")
        print("\n--- 输入区 ---")
        for e in d["editors"]:
            print(f"  {e}")
        print("\n--- 关键按钮（视频/上传/参数/发送） ---")
        for b in d["buttons"]:
            print(f"  ({b['x']:>5},{b['y']:>5}) {b['t']!r} aria={b['al']!r}")
        print("\n--- 页面已有视频（src 已截断） ---")
        for v in d["videos"]:
            print(f"  {v['src']}")
        print("\n--- 页面文本预览（前 800 字） ---")
        print(d["body"][:800])
        print("\n[NOTE] 请据此校准：视频生成入口文案、上传方式、参数按钮文本、提交方式。")
        print("[NOTE] 校准后把实际选择器记入 references/dom-map.md。")
        print("[NOTE] 页面文本可能含账号昵称等个人信息：本脚本输出不要直接贴到公开渠道。")
        if args.snap:
            bc.snap(page, "dola_probe.png")
        return 0
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    sys.exit(main())
