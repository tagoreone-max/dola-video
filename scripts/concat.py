# -*- coding: utf-8 -*-
"""把多段 dola / 豆包片段拼接成一条完整成片（15-30s）。

单段上限 15s，超出时长需分段生成后拼接。
脚本会先统一各段的分辨率/帧率/像素格式，再无损 concat。

兜底能力：仅当用户明确要求后期统一铺 BGM 时才使用（默认流程不做——
BGM 应在生成阶段由模型生成，多段靠提示词逐字复制保持一致）：

    python concat.py --inputs s1.mp4 s2.mp4 --out merged.mp4 --bgm bgm.mp3 --bgm-vol 0.2

BGM 时长不足自动循环，超出自动淡出截断；人声为主、BGM 垫底。
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_common as env  # noqa: E402  (仅需输出编码，不需要 playwright)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,duration",
         "-of", "json", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    return json.loads(out.stdout)["streams"][0]


def has_audio(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return bool(out.stdout.strip())


def mix_bgm(video, bgm, vol, duration, out):
    """铺固定 BGM：不足自动循环，超出自动淡出；无原音轨时直接以 BGM 为音轨。"""
    fade_st = max(0.0, duration - 2.0)
    trim = f"atrim=0:{duration:.3f},afade=t=out:st={fade_st:.3f}:d=2"
    if has_audio(video):
        fc = (f"[1:a]volume={vol},{trim}[bg];"
              f"[0:a]volume=1.0[vo];[vo][bg]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        fc = f"[1:a]volume={vol},{trim}[a]"
    tmp = out + ".bgm.tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video,
                    "-stream_loop", "-1", "-i", bgm,
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", tmp], check=True)
    os.replace(tmp, out)


def write_list(inputs):
    """concat 清单写到 ART_DIR，跑完即删，不落在仓库目录里。"""
    lst = env.art_path("_concat_list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in inputs:
            f.write(f"file '{os.path.abspath(p).replace(chr(92), '/')}'\n")
    return lst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reencode", action="store_true",
                    help="强制重编码（默认直接 concat，更快且无损）")
    ap.add_argument("--bgm", help="兜底：后期统一铺的背景音乐（默认不用，BGM 应生成阶段完成）")
    ap.add_argument("--bgm-vol", type=float, default=0.2, help="BGM 音量，默认 0.2（人声为主）")
    args = ap.parse_args()

    for p in args.inputs:
        if not os.path.exists(p):
            print(f"[FAIL] 不存在: {p}")
            return 1
    if args.bgm and not os.path.exists(args.bgm):
        print(f"[FAIL] BGM 不存在: {args.bgm}")
        return 1

    infos = []
    for p in args.inputs:
        i = probe(p)
        infos.append(i)
        print(f"  {os.path.basename(p)}: {i['width']}x{i['height']} "
              f"fps={i['r_frame_rate']} dur={float(i['duration']):.2f}s")

    same = len({(i["width"], i["height"], i["r_frame_rate"]) for i in infos}) == 1
    print(f"参数一致: {same}")

    lst = write_list(args.inputs)
    try:
        if same and not args.reencode:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                            "-i", lst, "-c", "copy", args.out], check=True)
        else:
            # 统一到第一段的规格后重编码
            w, h = infos[0]["width"], infos[0]["height"]
            fps = infos[0]["r_frame_rate"]
            vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                  f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                            "-i", lst, "-vf", vf, "-c:v", "libx264", "-crf", "18",
                            "-preset", "medium", "-c:a", "aac", args.out], check=True)
    finally:
        try:
            os.remove(lst)
        except OSError:
            pass

    total = float(probe(args.out)["duration"])
    if args.bgm:
        mix_bgm(args.out, args.bgm, args.bgm_vol, total, args.out)
        print(f"[OK] 已统一铺 BGM: {os.path.basename(args.bgm)}（音量 {args.bgm_vol}）")
        total = float(probe(args.out)["duration"])

    size = os.path.getsize(args.out) / 1024 / 1024
    print(f"\n[OK] {args.out}  总时长 {total:.2f}s  {size:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
