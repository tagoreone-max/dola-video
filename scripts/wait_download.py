# -*- coding: utf-8 -*-
"""轮询 dola（豆包国际版）生成状态，出片后下载到本地。

用法:
    python wait_download.py --out shot1.mp4 --timeout 600

结构同豆包版：页面 video 元素轮询 + 页面内 fetch 下载，失败回退 CDN 直链
（实测 dola 的页面内 fetch 会被平台隐私框架拦截，回退分支才是主路径）。
状态文案中英并存——实测界面为中文，只写英文会判不出「生成中」。
"""
import argparse
import base64
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browser_common as bc  # noqa: E402

HOST = bc.HOST

# failed 关键词刻意不含裸 error/blocked：页面上无关文本常带这类词，会误报
CHECK_JS = r"""
() => {
  const body = document.body.innerText || '';
  const out = {videos: [],
               failed: /失败|违规|肖像保护|额度不足|余额不足|failed|violat|insufficient|quota/i.test(body),
               generating: /生成中|排队|创作中|等待|generating|queued|processing|creating|pending/i.test(body)};
  document.querySelectorAll('video').forEach(v => {
    const src = v.src || v.currentSrc || '';
    const srcEl = v.querySelector('source');
    out.videos.push({src: src || (srcEl ? srcEl.src : ''), dur: v.duration || 0});
  });
  document.querySelectorAll('a[href*=".mp4"],video source').forEach(s => {
    const u = s.href || s.src || '';
    if (u && !out.videos.some(x => x.src === u)) out.videos.push({src: u, dur: 0});
  });
  return out;
}
"""

FETCH_JS = r"""
async (u) => {
  const r = await fetch(u, {credentials: 'include'});
  const b = await r.blob();
  const buf = await b.arrayBuffer();
  let binary = '';
  const bytes = new Uint8Array(buf);
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="输出 mp4 路径")
    ap.add_argument("--timeout", type=int, default=600, help="最长等待秒数")
    args = ap.parse_args()

    pw, browser, page = bc.connect(HOST)
    try:
        page.bring_to_front()
        start = time.time()
        baseline = len(page.evaluate(CHECK_JS)["videos"])
        print(f"[init] 页面已有 {baseline} 条视频，等待新出片...", flush=True)

        result = None
        warned = False
        while time.time() - start < args.timeout:
            st = page.evaluate(CHECK_JS)
            el = int(time.time() - start)
            print(f"[{el}s] videos={len(st['videos'])} generating={st['generating']} failed={st['failed']}",
                  flush=True)
            if st["failed"] and not st["generating"] and not st["videos"]:
                if not warned:
                    print("[WARN] 页面含失败字样（可能无关），继续观察", flush=True)
                    warned = True
            if len(st["videos"]) > baseline:
                result = st
                break
            time.sleep(12)

        if not result:
            print("超时未检测到新视频。页面尾部文本：")
            print(page.inner_text("body")[-500:])
            print("可跑 probe.py 校准状态文案，或确认额度是否已用尽。")
            return 1

        v = result["videos"][-1]
        src = v["src"]
        print(f"\n找到视频: dur={v['dur']}s src={src[:110]}")
        if not src:
            print("[FAIL] video src 为空（可能仍在缓冲），稍后重跑本脚本")
            return 1

        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        try:
            b64 = page.evaluate(FETCH_JS, src)
            with open(args.out, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[OK] 页面内下载: {args.out} ({os.path.getsize(args.out)/1024/1024:.2f} MB)")
            return 0
        except Exception as e:
            print(f"页面内下载失败({e})，回退直链...")
            if not src.startswith("http"):
                print("[FAIL] blob 源无法直连下载")
                return 1
            req = urllib.request.Request(src, headers={
                "Referer": "https://www.dola.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with bc.no_proxy_opener().open(req, timeout=180) as r, open(args.out, "wb") as f:
                f.write(r.read())
            print(f"[OK] 直链下载: {args.out} ({os.path.getsize(args.out)/1024/1024:.2f} MB)")
            return 0
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    sys.exit(main())
