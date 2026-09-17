# -*- coding: utf-8 -*-
"""dola（豆包国际版）配置参数、输入提示词并提交。

实测：dola 为**中文界面**，与国内豆包高度同构——
  - 输入框：tiptap ProseMirror（同豆包）
  - 底部工具栏有「视频生成」模式入口
  - 参数按钮（比例/时长/模型）点「视频生成」后出现，文案中文
  - **没有发送按钮**：填完提示词按 Enter 提交（本脚本自动 fallback）

用法:
    python generate.py --prompt "提示词" --ratio 9:16 --duration 4s
    python generate.py --list                  # 枚举可选项
    python generate.py --prompt "..." --dry-run
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browser_common as bc  # noqa: E402

HOST = bc.HOST

RATIOS = ["自动", "9:16", "16:9", "3:4", "4:3", "1:1", "21:9"]
DURATIONS = ["4s", "5s", "10s", "15s"]
MODELS = ["Seedance"]

# 状态文案中英并存：实测 dola 界面为中文，只写英文会永远判不出来
STATUS_KEYS = ("生成中", "排队", "创作中", "generating", "queued", "processing", "creating")

# "自动" 整词匹配，防误伤"自动化"
ENUM_JS = r"""
(pat) => {
  const re = pat ? new RegExp(pat) : null;
  const KEY = /9:16|16:9|3:4|4:3|1:1|21:9|\b4s\b|\b5s\b|\b10s\b|\b15s\b|Seedance|^自动$/i;
  const out = [];
  document.querySelectorAll('button,[role=button],[class*=select],[class*=Select]').forEach(el => {
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    const r = el.getBoundingClientRect();
    if (!t || r.width <= 0 || r.height <= 0) return;
    if ((re && re.test(t)) || KEY.test(t)) {
      out.push({t: t.slice(0, 50), x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2),
                w: Math.round(r.width), h: Math.round(r.height)});
    }
  });
  const seen = new Set();
  return out.filter(b => { const k = b.t + b.x + b.y;
    if (seen.has(k)) return false; seen.add(k); return true; });
}
"""


def enum_buttons(page, pat=None):
    return page.evaluate(ENUM_JS, pat)


def click_text(page, text, timeout=6):
    for _ in range(int(timeout * 2)):
        hit = page.evaluate(r"""
        (txt) => {
          for (const el of document.querySelectorAll('button,[role=button],[role=option],li,span,div')) {
            const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
            const r = el.getBoundingClientRect();
            if (t === txt && r.width > 0 && r.height > 0) {
              return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
            }
          }
          return null;
        }""", text)
        if hit:
            page.mouse.click(hit["x"], hit["y"])
            return True
        time.sleep(0.5)
    return False


def ensure_video_mode(page):
    """确保已进入「视频生成」模式（底部工具栏入口）。"""
    # 已在视频模式时页面会出现参数按钮；否则点「视频生成」
    if enum_buttons(page):
        return True
    if click_text(page, "视频生成"):
        time.sleep(2)
        print("[模式] 已点击「视频生成」")
        return True
    print("[WARN] 未找到「视频生成」入口（可能已在视频模式或界面改版）")
    return False


def set_option(page, label, value, cur_buttons):
    if not value:
        return True
    keys = {"比例": RATIOS, "时长": DURATIONS, "模型": MODELS}.get(label, [value])
    grp = [b for b in cur_buttons if any(k in b["t"] for k in keys)]
    if not grp:
        print(f"[WARN] 未找到 {label} 当前值按钮")
        return False
    if any(b["t"] == value for b in grp):
        print(f"[{label}] 已是 {value}，跳过")
        return True
    print(f"[{label}] 尝试切换到 {value} ...")
    btn = grp[0]
    page.mouse.click(btn["x"], btn["y"])
    time.sleep(1.2)
    ok = click_text(page, value)
    print(f"[{label}] {'已选择 ' + value if ok else '选择失败，请人工确认'}")
    return ok


FIND_SEND_JS = """
() => {
  const cands = [...document.querySelectorAll('button,[role=button]')];
  let el = cands.find(b => /发送|send/i.test(b.getAttribute('aria-label') || ''));
  if (!el) {
    const ed = document.querySelector('div.ProseMirror');
    let box = ed;
    for (let d = 0; d < 5 && box; d++) {
      const bs = [...box.querySelectorAll('button')].filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 20 && r.height > 20 && !b.disabled;
      });
      if (bs.length) { el = bs[bs.length - 1]; break; }
      box = box.parentElement;
    }
  }
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
}
"""


def submit(page, editor):
    """提交：优先点发送按钮；dola 实测无发送按钮，则回退按 Enter。"""
    sent = page.evaluate(FIND_SEND_JS)
    if sent:
        print(f"\n点击发送 @({sent['x']},{sent['y']})")
        page.mouse.click(sent["x"], sent["y"])
        return True
    print("\n[INFO] 未找到发送按钮（dola 实测即无），按 Enter 提交")
    editor.click()
    time.sleep(0.4)
    page.keyboard.press("Enter")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", help="提示词（台词/字幕保留中文，描述可英文）")
    ap.add_argument("--ratio", default="", help="比例：9:16 / 16:9 / 1:1 ...")
    ap.add_argument("--duration", default="", help="时长：4s / 5s / 10s / 15s")
    ap.add_argument("--model", default="", help="模型：Seedance ...")
    ap.add_argument("--list", action="store_true", help="枚举可选项")
    ap.add_argument("--dry-run", action="store_true", help="填好但不发送")
    args = ap.parse_args()

    pw, browser, page = bc.connect(HOST)
    try:
        page.bring_to_front()
        time.sleep(1)
        ensure_video_mode(page)
        time.sleep(1)

        btns = enum_buttons(page)
        print("=== 当前参数按钮 ===")
        for b in btns:
            print(f"  {b['t']!r} @({b['x']},{b['y']}) {b['w']}x{b['h']}")
        if args.list:
            return 0

        if args.ratio:
            set_option(page, "比例", args.ratio, btns)
            time.sleep(0.8)
        if args.duration:
            set_option(page, "时长", args.duration, enum_buttons(page))
            time.sleep(0.8)
        if args.model:
            set_option(page, "模型", args.model, enum_buttons(page))
            time.sleep(0.8)

        if not args.prompt:
            print("[FAIL] 缺少 --prompt")
            return 1

        editor = page.locator("div.ProseMirror").first
        editor.click()
        time.sleep(0.6)
        page.keyboard.insert_text(args.prompt)
        time.sleep(1)
        shown = page.evaluate(
            "() => { const e = document.querySelector('div.ProseMirror'); return e ? e.innerText : ''; }")
        print(f"\n=== 提示词已输入（{len(shown)} 字）===")
        print(shown[:200] + ("..." if len(shown) > 200 else ""))

        if args.dry_run:
            print("\n[DRY-RUN] 未发送。确认后去掉 --dry-run 重跑。")
            bc.snap(page, "dola_dryrun.png")
            return 0

        submit(page, editor)
        time.sleep(10)
        body = page.inner_text("body").lower()
        status = "生成中" if any(k in body for k in STATUS_KEYS) else "未知"
        print(f"=== 提交后状态: {status} ===")
        bc.snap(page, "dola_submitted.png")
        if status == "未知":
            print("[WARN] 未看到生成中/排队字样，请核对截图或跑 probe.py 校准文案")
        return 0
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    sys.exit(main())
