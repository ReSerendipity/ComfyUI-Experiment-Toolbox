# 09 Web 面板 · USAGE（怎么跑）

> 本页是**操作手册**：启动命令、端口、每个页面吃什么吐什么、出问题怎么查。
> 面板的设计意图与跑测流程见同目录 [`README.md`](README.md)；σ 判据与指标口径在 `../02_调度器sigma分析/`、`../04_结果分析/`。

---

## 一、这个面板是干什么的

把参数轨（01~04）的 headless 脚本能力包一层浏览器壳：**给人类用户点着用**，不用记命令、不用改 JSON。
面板本身只做编排与展示，判定/计算/跑测逻辑一律复用各轨脚本（依赖方向：09 只准 import 01/02，03 轨走子进程）。

**结构改造（05）刻意不 Web 化**：加参考图槽位、模板对齐这类结构手术低频、高风险、强依赖节点指纹，请在 ComfyUI 前端（Autogrow 加槽最稳）或命令行跑 `05_结构改造脚本/`。

---

## 二、启动命令

| 方式 | 命令 | 说明 |
|---|---|---|
| 双击（推荐） | 工具箱根目录 `start.bat` | 等价 `run.bat panel`；面板退出后窗口停住等按键，方便看报错 |
| 批处理 | `run.bat panel` | 用 ComfyUI 自带 python 起 `run.py`，再以子进程调 `09_Web面板/panel.py` |
| 直接调 | `python run.py panel` | 同上，需自己保证 `python` 是 ComfyUI 那个 |
| 单跑面板 | `"<ComfyUI>\python\python.exe" 09_Web面板\panel.py` | 绕过入口层；**必须在工具箱根目录或面板目录**（`panel.py` 靠 `__file__` 反推 `index.html` 与 01 轨路径） |
| 不自动开浏览器 | 上面任一命令末尾加 `--no-browser` | 例：`run.bat panel --no-browser` |

**端口**：

| 服务 | 地址 | 谁起 |
|---|---|---|
| 面板 | `http://127.0.0.1:8189`（只绑回环，不对外网开放） | 你（上面任一命令） |
| ComfyUI | `http://127.0.0.1:8188` | ③ 页自动拉起，或你手动起 |

启动后自动打开浏览器（先探 `/api/health` 探活，最多等 15s，避免打开「无法连接」的空白页）。停止 = 面板窗口 `Ctrl+C` 或直接关窗口。

> 端口占用不再静默抢绑：已有一个面板在跑时，新实例**直接报错退出（exit 1）**并告诉你怎么办。Windows 的 `SO_REUSEADDR` 会让两个进程绑同一端口、请求随机落到旧代码上，故已关闭。

---

## 三、页面（当前界面实况 = 5 页）

`index.html` 的 nav 现有 5 个页签；下表按实际界面列：

| 页 | 复用 | 做什么 | 输入 | 输出 | 需 ComfyUI |
|---|---|---|---|---|---|
| ① 工作流真值 | `01_工作流扁平化/flatten.py`（面板直接 import） | 列出每份工作流的运行时参数（**以 positional 容器值为准**：采样器 / 调度器 / steps / cfg / seed / 模型），并标出提示词是否为空 | 工作流目录 `...\workflows\Image\*.json`（`.bak` 自动跳过） | 表格（不落盘） | 否 |
| ② σ 风险矩阵 | `02_调度器sigma分析/` | 多模型 × 多调度器**离线**判定（首步 Δσ% > 15% 或高噪声区步数不足 → 高危），不跑图 | 模型清单 + 采样器/调度器全集 | 矩阵表格（结果常驻内存，面板重启后重算） | 否（但需 `comfy`+`torch`，首次 20~60s） |
| ③ 受控跑测 | `03_受控跑测/` 逻辑 | 勾工作流 + 加组合（固定提示词与种子，每轮只变勾选维度），逐组提交 + 进度条 + 日志 | 勾选的工作流、组合（采样器/调度器下拉 + steps/CFG）、提示词、种子、产物子目录 | 图片落到 `09_Web面板/output/<子目录>/`（默认 `web_test`） | **是**（未启动会自动拉起，等就绪上限 5 分钟） |
| ④ 结果分析 | `04_结果分析/` 口径 | 客观指标（亮度 / 对比度σ / 锐度 / 色彩度）+ 与 base 基线的相似度（灰度 128×128 的 `1 − MSE/255²`）+ 4 列带标签拼版 | ③ 产物的子目录名 | `output/<子目录>/_montage.png` + 指标表（页面内嵌图） | 否（读已落盘产物） |
| ⑤ 视频档位 | `03_受控跑测/run_durations.py`（**子进程**调用，不 import） | 适配器驱动的时长档位跑测：E2 显存自适应 + OOM 自动降档；可勾 dry-run 只出计划（0 提交） | 适配器、档位组合、起始档（auto / 顶 1344×768 / 中 1152×640 / 底 960×544）、显存模式（`calibrated` 标定边界表 / `live` 实时可用）、可选 TE/DiT | 日志 + 本次新增的 JSONL 记录（含降档轨迹） | **是** |

> **口径差异（已知）**：同目录 `README.md` 与 `panel.py` 顶部 docstring 仍按「①–④ 四页」记述；⑤ 视频档位是 2026-10 的 E4/E2 扩展，已进 `index.html` 的 nav 与 `/api/video_run`。本轮只改文档、不动代码，故此处按**实际界面**记 5 页，README 的页码表述未同步（差异已进报告）。

---

## 四、输入与输出

| | 内容 |
|---|---|
| **输入（配置常量）** | `panel.py` 顶部：`COMFY_ROOT`（ComfyUI 根）、`WF_DIR`（工作流目录）、`CF_OUT`（ComfyUI 输出目录）、`OUT_ROOT`（面板产物根）、`PORT`（8189）、`COMFY_MAIN`（拉起 ComfyUI 的入口）。复用到别处只改这几行 |
| **输入（用户操作）** | ① 无；② 无；③ 工作流勾选 + 组合 + 提示词 + 种子 + 子目录名；④ 子目录名；⑤ 适配器 + 档位 + 起始档 + 显存模式（+ dry-run） |
| **输出（文件）** | `09_Web面板/output/<子目录>/`：③ 从 ComfyUI `output` 拷过来的成图；④ 同名目录下的 `_montage.png`。目录名经 `[\w-]` 之外字符替换为 `_` |
| **输出（HTTP）** | `GET /api/health` `GET /api/workflows` `GET /api/sigma` `GET /api/run_status` `GET /api/video_status` `GET /api/image` `GET /api/comfy_lists` `GET /api/adapters` `GET /api/vram` `GET /api/default_prompt`；`POST /api/run` `POST /api/analyze` `POST /api/comfy_start` `POST /api/video_run` |

---

## 五、零依赖说明

- **面板本体零第三方依赖**：`panel.py` 只用标准库（`http.server` / `json` / `re` / `subprocess` / `threading` / `urllib` / `webbrowser` / `shutil`），`index.html` 是单文件静态页（无构建、无 CDN、无 npm）。**不需要 `pip install` 任何东西**。
- **但必须用 ComfyUI 自带的 python 启动**：①③ 复用 `01` 轨 `flatten.py`，② 要 `import comfy.*` + `torch`，④ 要 `numpy` + `Pillow`。这些只在那套环境里齐。
- 两句话分开看：「零依赖」= 不装额外包；「用哪个 python」= 必须 ComfyUI 那个。混起来就会得到 `ModuleNotFoundError: No module named 'torch'`。
- 复用到别的机器：改 `panel.py` 顶部常量 + 用目标机 ComfyUI 的 python 起，不需要装依赖。

---

## 六、最小示例

```powershell
# 1) 起面板（不弹浏览器，先看日志）
cd "$env:USERPROFILE\APP\repository\ComfyUI-Experiment-Toolbox"
.\run.bat panel --no-browser

# 2) 浏览器打开
#    http://127.0.0.1:8189  →  ① 工作流真值：确认参数与「提示词是否为空」
# 3) ③ 页：勾 1 个工作流、只留 base 组合（steps/CFG 留空 = 用当前值）、点「开始跑测」
# 4) ④ 页：子目录填 web_test，点「分析」→ 看指标表与 _montage.png
```

只想验证服务活着、连不通时先排除面板自身问题：

```powershell
Invoke-RestMethod http://127.0.0.1:8189/api/health
```

---

## 七、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动即 `× 端口 8189 被占用，面板未能启动` + exit 1 | 已有一个面板在跑（这是有意为之：不抢绑） | 直接访问 `http://127.0.0.1:8189`；要跑新代码，先到旧面板窗口 `Ctrl+C` 关掉 |
| 浏览器打开是「无法连接」 | 浏览器开得比服务快（探活失败也会兜底打开） | 手动刷新地址；仍不行看面板窗口日志有无 traceback |
| ② 页长期「计算中」 | 首次要导入 `comfy` + `torch`（20~60s，冷盘更久） | 等；超 2 分钟看面板日志 |
| ③ 页卡在「ComfyUI 加载中… 已等 Ns」 | ComfyUI 冷启动 + 模型加载，等就绪上限 5 分钟 | 看自动拉起的**独立控制台窗口**；页面提示 `exit=N` 说明进程已退出（多为显存不足/依赖报错） |
| ③ 页提交直接 400 | 非法采样器/调度器，或 steps/CFG 不是数字（后端与下拉框同源校验） | 用下拉选项；steps/CFG 留空 = 用各工作流当前值 |
| ③ 页提示「未勾选任何工作流」「未添加任何组合」 | 缺项点名 | 按提示补 |
| ④ 相似度全是 `1.0` | 没跑 base 组合（基线 = base，缺 base 时取字母序第一个组合） | 补跑 base 组合再分析 |
| ④ 拼版图没出来 | 中文标签字体 `msyh.ttc` 取不到时回落默认字体，或拼版异常 | 日志有「拼版失败」；指标表本身仍可用，看 `_montage.png` 是否存在 |
| ⑤ 页跑测立刻结束、0 提交 | 勾了「dry-run」 | 取消勾选再跑 |
| `ModuleNotFoundError: No module named 'torch'` | 用了非 ComfyUI 的 python | 用 `run.bat` / `run.py`，或指向 `%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\python.exe` |
| 改了 `index.html` 前端逻辑 | — | 跑 `test_dom.js` 做真实 DOM 回归（jsdom；通过标准见 README 末节），别只 grep 源码 |
| 想改端口 | `PORT` 写死 8189 | 改 `panel.py` 顶部 `PORT`；同步改本页与 README 的地址说法 |
