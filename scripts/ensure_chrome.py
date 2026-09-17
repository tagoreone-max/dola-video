# -*- coding: utf-8 -*-
"""确保受控 Chrome 已启动且 CDP 可达。

只依赖标准库（走 env_common），不需要 playwright。

用法:
    python ensure_chrome.py status      # 只看状态与生效配置
    python ensure_chrome.py launch      # 未连通则启动（DETACHED，脱离 shell 存活）
    python ensure_chrome.py tabs        # 列出当前标签页
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_common as env  # noqa: E402  (import 时即完成代理绕过)


def cdp_ok(timeout=5):
    try:
        with env.no_proxy_opener().open(f"{env.CDP_HTTP}/json/version", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def launch():
    exe = env.CHROME_EXE
    if not os.path.exists(exe):
        print(f"[FAIL] 找不到 Chrome: {exe}")
        print("       请设环境变量 DOLA_CHROME_EXE 指向实际的 chrome 可执行文件后重试。")
        return False

    os.makedirs(env.PROFILE_DIR, exist_ok=True)
    first_run = not os.path.exists(os.path.join(env.PROFILE_DIR, "Default"))

    args = [
        exe,
        f"--user-data-dir={env.PROFILE_DIR}",
        f"--remote-debugging-port={env.CDP_PORT}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        env.DOLA_URL,
    ]

    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, close_fds=True)

    for _ in range(20):
        time.sleep(1)
        info = cdp_ok()
        if info:
            print(f"[OK] CDP 已就绪: {info.get('Browser')}")
            print(env.config_summary())
            if first_run:
                print("[ACTION] 首次使用该 profile，请在弹出的 Chrome 窗口中登录 dola。")
                print(f"         登录态会保存在 {env.PROFILE_DIR}（敏感目录，勿提交/勿分享）。")
            return True

    print("[FAIL] Chrome 已发起但 CDP 未就绪（20s 超时）")
    print("       若进程被 shell 回收，改用后台保活方式手动启动：")
    print(f'         "{exe}" --user-data-dir="{env.PROFILE_DIR}" '
          f'--remote-debugging-port=9222 --remote-allow-origins=* &')
    return False


def tabs():
    with env.no_proxy_opener().open(f"{env.CDP_HTTP}/json/list", timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
    n = 0
    for t in data:
        if t.get("type") == "page":
            n += 1
            print(f"{t.get('title','')[:50]}\t{t.get('url','')[:110]}")
    if not n:
        print("（CDP 可达，但当前没有页面标签）")
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "launch":
        info = cdp_ok()
        if info:
            print(f"[OK] 已在运行: {info.get('Browser')}")
            print(env.config_summary())
            sys.exit(0)
        sys.exit(0 if launch() else 1)
    elif cmd == "tabs":
        if not cdp_ok():
            print("CDP_NOT_READY —— 先跑: python scripts/ensure_chrome.py launch")
            sys.exit(1)
        tabs()
    else:
        info = cdp_ok()
        print(json.dumps(info, ensure_ascii=False, indent=2) if info else "CDP_NOT_READY")
        if info:
            print(env.config_summary())
