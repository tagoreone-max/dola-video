---
name: dola-video
description: 通过 CDP 接管用户已登录的 Chrome，在 dola.com（豆包国际版，前身 Cici）网页版用产品白底图与模特图生成电商视频。dola 为免费额度、成片右下角有固定水印（截单帧即可定位），流程为上传 → 生成 → 下载 → 去水印 →（多段）拼接。当用户要求用 dola / 豆包海外版 / Cici 生成视频时，应使用本技能。
agent_created: true
---

# dola（豆包国际版）视频生成

## 用途

在 dola.com（豆包国际版，前身 Cici，字节海外产品，同用 Seedance 模型）网页版生成视频。
免费额度有限（每日积分以页面显示为准），成片**右下角有固定水印**（静态烧录，截单帧即可定位）。

流程：`上传 → 生成 → 下载 → 去水印 →（多段）拼接`。

## 何时使用

- 用户明确说用 dola / 豆包海外版 / Cici
- 需要走海外站生成（与国内豆包的账号、额度、水印完全独立，不要混用）
- 注意：访问 dola.com 需海外网络出口（系统代理即可）；界面实测为中文

## 环境与配置

脚本内的本机路径全部可通过环境变量覆盖，不设则用跨平台默认值：

| 变量 | 作用 | 默认值 |
|---|---|---|
| `DOLA_CHROME_EXE` | Chrome 可执行文件路径 | 自动探测 Windows / macOS / Linux 常见安装位置 |
| `DOLA_PROFILE_DIR` | 受控 Chrome 的 `--user-data-dir`（保存登录态） | `~/.dola-video/browser-profile` |
| `DOLA_CDP_HTTP` | CDP 连接地址 | `http://127.0.0.1:9222` |
| `DOLA_ART_DIR` | 脚本截图/临时产物输出目录 | 系统临时目录下的 `dola-video/` |

> 登录态存在 `DOLA_PROFILE_DIR` 里，**属于敏感数据，不要提交、不要分享该目录**。

依赖：Python + `playwright` + `numpy` + `Pillow`，以及 PATH 中的 `ffmpeg` / `ffprobe`。

## 与国内豆包（`doubao-video-generation` skill）的关系

同族产品、同模型引擎，但**账号、额度、水印彼此独立**：

| 维度 | doubao.com | dola.com |
|---|---|---|
| 界面语言 | 中文 | **中文**（实测：界面与豆包几乎同构，非英文） |
| 输入框 | tiptap ProseMirror | **tiptap ProseMirror（同款）** |
| 视频入口 | 底部工具栏「视频生成」 | **同款底部工具栏「视频生成」** |
| 账号 | 国内手机号 | 独立海外账号（支持 Google / FB / 海外手机号登录） |
| 额度 | 免费版每日限额 | 免费额度少（每日积分有限，以页面显示为准） |
| 水印 | 右下角「豆包AI生成」 | **右下角固定位置水印**（静态、截单帧可定位） |
| 网络 | 直连 | 需海外网络出口（系统代理）；CDP 本地连接仍须绕代理 |

**实测结论：dola 界面与国内豆包高度同构**——同样的 ProseMirror 输入框、同样的底部「视频生成」
入口、中文参数文案。豆包 skill 的选择器逻辑大部分直接适用，仅在细节不同处（如时长档位多 5s）
需按 `probe.py` 输出微调。

---

## 阶段一：需求采集（强制）

同豆包 skill 全套清单（平台/比例/时长/模型/卖点/口播/字幕/BGM/品牌型号），
另有 dola 特有检查：

| # | 项目 | 说明 |
|---|---|---|
| 1 | **额度确认** | 先看 dola 页面显示的剩余积分/次数，评估今天还能跑几条，告知用户 |
| 2 | **肖像保护（硬规则）** | **Seedance 2.0 拒绝真人脸参考图**（未认证人脸）。若素材含清晰人脸：不传人物图，只传**产品白底图**，人物改用文字反推描述（实测可行）。需要真人形象应走支持人脸认证的平台 |
| 3 | **语言** | 提示词用中文还是英文写？**Seedance 系对英文提示词响应通常更稳**（海外版训练分布），建议英文提示词 + 中文台词（台词保留原文） |

## 阶段二：环境准备

```bash
python scripts/ensure_chrome.py status   # 先看 CDP 是否已就绪
python scripts/ensure_chrome.py launch   # 未就绪则启动受控 Chrome
```

然后在受控窗口打开 `https://www.dola.com/chat/`。未登录则让用户在该窗口登录一次
（Google / FB / 海外手机号），之后登录态永久保存在 `DOLA_PROFILE_DIR`。

**注意双代理问题**：
- 访问 dola.com 需要走系统代理——浏览器正常上网即可，不用改
- 但 **Python 脚本连 CDP（127.0.0.1:9222）必须绕代理**——`browser_common.py` 已内置处理

## 阶段三：生成

脚手架与豆包 skill 同构（已实测界面同构，中文文案匹配）：

```bash
python scripts/upload_images.py --images 白底图.png   # file input 直注，多图会追加
python scripts/generate.py --prompt "..." --ratio 9:16 # 无发送按钮，脚本自动按 Enter 提交
python scripts/wait_download.py --out shot1.mp4 --timeout 600
```

**实测要点（全链路已跑通）**：
- 视频生成模式下有常驻 `input[type=file]`（accept=.jpg,.png,.jpeg,.webp），直注成功；多图追加
- **无发送按钮——填完提示词直接按 Enter 提交**（`generate.py` 已实现该 fallback）
- 下载走直链回退（页面 fetch 被平台隐私框架拦截，`wait_download.py` 已处理）
- 提交后页面出现「生成中」即成功；等 2-3 分钟出片（10s 档实测约 200s）
- 真人脸参考图会触发肖像保护拦截（见阶段一规则 2）

> 首跑若某步匹配失败，跑 `scripts/probe.py` 打印实际结构校准，并把选择器补进
> `references/dom-map.md`。

提示词模板、多段一致性锚点、字幕避让——与豆包 skill 基本共用一套，见 `references/prompt-templates.md`。
**多段时同一会话连续提交、固定锚点逐字复制**（模型同引擎，规则一致）。

## 阶段四：去水印

dola 水印固定在右下角，静态烧录，**截单帧即可定位位置**。但具体坐标随画幅与平台改版浮动，
**每次出片都要先 `locate` 复核，不要照搬别处的数字**。

```bash
# 1. 提单帧 + 字符画定位（每行标注真实像素 Y 坐标，防数错行）
python scripts/watermark.py locate --video raw1.mp4 --box 420,1150,720,1280

# 2. 按字符画读出的边界做 delogo + 自动复核
python scripts/watermark.py remove --video raw1.mp4 --out clean1.mp4 --box x,y,w,h
```

要点（继承自豆包实测经验）：
- `--box` 为 `x,y,w,h`，四边各留 20-40px 余量
- delogo 区域**不能贴画面边缘**（右/下留 ≥4px，否则 `outside of frame` 报错；脚本已自动内缩）
- **从原片处理**，不做二次涂抹
- 定位靠字符画人工判读——自动检测算法（差分/方差/梯度）在静止背景 + 半透明水印场景全部失灵

多段时各段水印位置一致，**逐段去水印参数可复用**，或先拼接后对整片去一次。

> 合规提示：去除平台水印通常违反对应服务条款，请自行确认素材授权与用途，责任由使用者承担。

## 阶段五：交付

1. 交付成片 + 原片
2. 汇报：额度消耗、去水印坐标、分镜与提示词

## 常见故障速查

| 现象 | 原因 | 解法 |
|---|---|---|
| dola 打不开/转圈 | 未走代理 | 确认系统代理开着；受控 Chrome 走系统代理即可 |
| Python 连 CDP 502 | 代理劫持 127.0.0.1 | browser_common.py 已绕；勿删其中 ProxyHandler 逻辑 |
| 报 Chrome 不存在 | 非默认安装路径 | 设 `DOLA_CHROME_EXE` 指向实际 chrome 路径 |
| 报错「肖像保护/未认证人脸」 | Seedance 拒绝真人脸参考图 | 撤人物图，只传产品白底图，人物改文字描述（见阶段一规则 2） |
| 找不到发送按钮 | dola 无发送按钮 | 正常，脚本会自动按 Enter 提交 |
| 下载 Failed to fetch | 页面 fetch 被平台隐私框架拦截 | 走直链回退（wait_download.py 已实现） |
| 免费额度不足 | 每日额度有限 | 换其它已开通额度的平台，或次日再跑 |
| 水印去后有残留 | 定位 Y 坐标数错行 | 字符画每行标注真实像素坐标，逐行核对 |

坑位详见 `references/pitfalls.md`。
