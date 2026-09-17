# -*- coding: utf-8 -*-
"""dola（豆包国际版）上传参考图。

实测：视频生成模式下页面有**常驻** input[type=file]（accept 含 .jpg/.png/.jpeg/.webp），
直接 set_input_files 注入即可，多图会**追加**到输入区。
若找不到 file input，先跑 probe.py 查看上传控件结构。

用法:
    python upload_images.py --images 白底图.png 模特.jpg
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browser_common as bc  # noqa: E402

HOST = bc.HOST


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True, help="本地图片路径")
    args = ap.parse_args()

    images = [os.path.abspath(p) for p in args.images]
    for p in images:
        if not os.path.exists(p):
            print(f"[FAIL] 不存在: {p}")
            return 1

    pw, browser, page = bc.connect(HOST)
    try:
        page.bring_to_front()
        time.sleep(1.5)
        n = page.locator("input[type=file]").count()
        print(f"[init] file input 数量: {n}")
        if n == 0:
            print("[FAIL] 未找到 file input。可能未进入「视频生成」模式，或上传走自定义弹窗。")
            print("       先跑 probe.py 查看结构；若上传按钮触发系统选择器，")
            print("       改用 playwright expect_file_chooser 方式。")
            bc.snap(page, "dola_nofile.png")
            return 1

        target = None
        for i in range(n):
            acc = page.locator("input[type=file]").nth(i).get_attribute("accept") or ""
            print(f"  input[{i}] accept={acc[:70]}")
            if any(k in acc.lower() for k in ("image", ".jpg", ".png", ".webp")):
                target = i
                break
        if target is None:
            target = 0

        page.locator("input[type=file]").nth(target).set_input_files(images)
        print(f"[OK] 已注入 {len(images)} 张图片到 input[{target}]")
        time.sleep(4)
        bc.snap(page, "dola_upload_done.png")
        print("已截图（请核对缩略图已出现；截图路径见上方 [snap]）")
        return 0
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    sys.exit(main())
