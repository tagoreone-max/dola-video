# -*- coding: utf-8 -*-
"""成片水印定位与去除（通用 ffmpeg 工具）。

自动检测算法（时间差分/方差/最小亮度/最小梯度）在静止背景成片上全部失灵：
背景近乎静止 + 水印是低对比半透明叠加，算法分不清水印与背景。
因此本工具采用**字符画人工判读法**：把可疑区域渲染成 ASCII 输出到终端，
汉字笔画结构会清晰暴露，且每行标注真实像素 Y 坐标，避免"数错行"导致定位偏移。

依赖：ffmpeg / ffprobe（PATH 中）+ numpy + Pillow。不需要 playwright。

用法:
    # 1) 定位：渲染右下角字符画，人工读出边界
    python watermark.py locate --video raw.mp4 --box 420,1150,720,1280
    # 2) 去除：--box 为 x,y,w,h，四边各留 20-40px 余量，务必从原片处理
    python watermark.py remove --video raw.mp4 --out clean.mp4 --box x,y,w,h

中间帧与验证图落在 $DOLA_ART_DIR（默认系统临时目录），不会污染仓库。

> 合规提示：去除平台水印通常违反对应服务条款，请自行确认素材授权与用途。
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_common as env  # noqa: E402  (仅需输出编码，不引入 playwright)

import numpy as np            # noqa: E402
from PIL import Image         # noqa: E402

CHARS = " .:-=+*#%@"


def frame_png(name):
    return env.art_path(name)


def video_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    w, h = out.stdout.strip().split(",")[:2]
    return int(w), int(h)


def grab_frame(video, t, png):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", video,
                    "-frames:v", "1", png], check=True)
    return png


def ascii_art(png, box, cols=120):
    """渲染字符画，每行前缀标注真实像素 Y 坐标。"""
    img = Image.open(png).convert("L").crop(box)
    w, h = img.size
    rows = max(1, int(cols * h / w / 2.1))
    small = img.resize((cols, rows), Image.LANCZOS)
    a = np.asarray(small, dtype=np.float32)
    lo, hi = np.percentile(a, 2), np.percentile(a, 98)
    a = np.clip((a - lo) / max(1e-6, hi - lo), 0, 1)

    x0, y0, x1, y1 = box
    lines = []
    for r in range(rows):
        y = y0 + int((r + 0.5) * h / rows)
        row = "".join(CHARS[min(9, int(v * 9.99))] for v in a[r])
        lines.append(f"y={y:>4} |{row}")
    # 顶部标注列对应的 X 坐标
    ticks = [" "] * cols
    for c in range(0, cols, 20):
        lab = str(x0 + int(c * w / cols))
        for j, ch in enumerate(lab):
            if c + j < cols:
                ticks[c + j] = ch
    header = f"       |{''.join(ticks)}"
    return header + "\n" + "\n".join(lines), (lo, hi)


def cmd_locate(args):
    box = tuple(int(v) for v in args.box.split(","))
    png = frame_png("_wm_frame.png")
    grab_frame(args.video, args.t, png)
    W, H = video_size(args.video)
    print(f"视频尺寸 {W}x{H}  取帧 t={args.t}s  区域 {box}")
    art, rg = ascii_art(png, box, cols=args.cols)
    print("=" * (args.cols + 8))
    print(art)
    print("=" * (args.cols + 8))
    print(f"(亮度归一化 {rg[0]:.0f}~{rg[1]:.0f}  帧文件: {png})")
    print("\n判读要点：密集的 @ % # 笔画团 = 水印文字；平滑渐变 = 画面本身。")
    print("读出笔画团的上/下/左/右边界后，在 remove 时四边各留 20-40px 余量。")
    return 0


def cmd_remove(args):
    x, y, w, h = (int(v) for v in args.box.split(","))
    W, H = video_size(args.video)
    print(f"视频 {W}x{H}  delogo 区域 x={x} y={y} w={w} h={h}")

    # delogo 不允许区域贴到画面边缘，自动内缩
    changed = False
    if x + w >= W:
        w = W - x - 4
        changed = True
    if y + h >= H:
        h = H - y - 4
        changed = True
    if changed:
        print(f"[AUTO] 区域贴边，已内缩为 w={w} h={h}（delogo 要求四边留 >=4px）")
    if x < 1 or y < 1 or w < 1 or h < 1:
        print("[FAIL] 区域无效")
        return 1

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", args.video,
                    "-vf", f"delogo=x={x}:y={y}:w={w}:h={h}",
                    "-c:a", "copy", args.out], check=True)
    print(f"[OK] 已输出 {args.out} ({os.path.getsize(args.out)/1024/1024:.2f} MB)")

    # 自动验证：处理后再渲染一次同区域字符画
    vpng = frame_png("_wm_verify.png")
    grab_frame(args.out, args.t, png=vpng)
    vbox = (max(0, x - 20), max(0, y - 20), min(W, x + w + 20), min(H, y + h + 20))
    print(f"\n=== 处理后验证（区域 {vbox}）===")
    art, _ = ascii_art(vpng, vbox, cols=args.cols)
    print(art)
    print("\n若仍可见笔画结构，说明范围偏小或位置有偏移，扩大 --box 从【原片】重做。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("locate")
    p1.add_argument("--video", required=True)
    p1.add_argument("--box", default="420,1150,720,1280", help="x0,y0,x1,y1 待观察区域")
    p1.add_argument("--cols", type=int, default=120)
    p1.add_argument("--t", type=float, default=2.0, help="取帧时刻(秒)")
    p1.set_defaults(func=cmd_locate)

    p2 = sub.add_parser("remove")
    p2.add_argument("--video", required=True)
    p2.add_argument("--out", required=True)
    p2.add_argument("--box", required=True, help="x,y,w,h")
    p2.add_argument("--cols", type=int, default=110)
    p2.add_argument("--t", type=float, default=2.0)
    p2.set_defaults(func=cmd_remove)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
