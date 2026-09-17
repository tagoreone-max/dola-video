# -*- coding: utf-8 -*-
"""跨平台环境准备：代理绕过 + 输出编码 + 可配置路径。

只依赖标准库。纯命令行工具（watermark.py / concat.py）import 本模块即可，
不必被 playwright 依赖拖累；需要连浏览器的脚本请 import browser_common
（它会先经本模块完成代理绕过）。

可用环境变量：
    DOLA_CHROME_EXE   Chrome 可执行文件路径（默认自动探测）
    DOLA_PROFILE_DIR  受控 Chrome 的 user-data-dir，含登录态（默认 ~/.dola-video/browser-profile）
    DOLA_CDP_HTTP     CDP 地址（默认 http://127.0.0.1:9222）
    DOLA_ART_DIR      截图/临时产物目录（默认 系统临时目录/dola-video）
"""
import io
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request

# --- 代理绕过：必须在 import playwright 之前生效 ---
for _k in ("NO_PROXY", "no_proxy"):
    os.environ[_k] = "127.0.0.1,localhost,<-loopback>"
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

# --- Windows 控制台中文输出 ---
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _override(name, default):
    v = os.environ.get(name)
    return os.path.expanduser(v) if v else default


def find_chrome():
    """按常见安装位置探测 Chrome；找不到时返回供报错展示的名字。"""
    if os.name == "nt":
        roots = [os.environ.get("PROGRAMFILES"),
                 os.environ.get("PROGRAMFILES(X86)"),
                 os.environ.get("LOCALAPPDATA")]
        for root in roots:
            if root:
                p = os.path.join(root, "Google", "Chrome", "Application", "chrome.exe")
                if os.path.exists(p):
                    return p
        return os.path.join(roots[0] or "C:\\Program Files",
                            "Google", "Chrome", "Application", "chrome.exe")
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
              "/usr/bin/chromium-browser", "/usr/bin/chromium", "/snap/bin/chromium"):
        if os.path.exists(p):
            return p
    return "google-chrome"


CDP_HTTP = _override("DOLA_CDP_HTTP", "http://127.0.0.1:9222")
PROFILE_DIR = _override("DOLA_PROFILE_DIR",
                        os.path.join(os.path.expanduser("~"), ".dola-video", "browser-profile"))
ART_DIR = _override("DOLA_ART_DIR", os.path.join(tempfile.gettempdir(), "dola-video"))
CHROME_EXE = _override("DOLA_CHROME_EXE", find_chrome())

DOLA_URL = "https://www.dola.com/chat/"
HOST = "dola"  # find_page() 的 URL 子串匹配关键词

CDP_PORT = urllib.parse.urlparse(CDP_HTTP).port or 9222


def art_path(name):
    """截图/临时产物的落盘路径（默认在系统临时目录，不会被误提交进仓库）。"""
    os.makedirs(ART_DIR, exist_ok=True)
    return os.path.join(ART_DIR, name)


def no_proxy_opener():
    """返回一个不走任何代理的 urllib opener（CDP 是回环地址，必须绕代理）。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def config_summary():
    return json.dumps({
        "CDP_HTTP": CDP_HTTP,
        "CHROME_EXE": CHROME_EXE,
        "PROFILE_DIR": PROFILE_DIR,
        "ART_DIR": ART_DIR,
    }, ensure_ascii=False, indent=2)
