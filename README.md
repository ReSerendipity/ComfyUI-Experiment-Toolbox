# ComfyUI 实验与改造工具箱

> **ComfyUI 采样器/调度器受控实验 + 工作流结构改造工具箱**：两条流水线服务一台本机 ComfyUI——参数怎么配对、怎么验证（01~04+07），工作流怎么改对、怎么对齐官方模板（05+08），外加一个零第三方依赖的 Web 面板。
> A two-track toolbox for a local ComfyUI: controlled sampler/scheduler experiments (01–04+07), workflow surgery with official-template alignment (05+08), plus a zero-dependency Web panel.

- 仓库：<https://github.com/ReSerendipity/ComfyUI-Experiment-Toolbox>
- 许可证：[Apache-2.0](LICENSE) · 变更记录：[CHANGELOG.md](CHANGELOG.md)

---

## 一、这是什么

```
                 官方模板 + 源码（最高权威）
                          │
        ┌─────────────────┴──────────────────┐
        ▼                                    ▼
  【参数实验轨 01~04 + 07】            【结构改造轨 05 + 08】
  "参数怎么配对、怎么验证"              "工作流怎么改对"
  控制变量实验流水线：                  结构手术流水线：
  扁平化 → σ离线筛 → 受控跑测          备份 → 模板对齐 → 加槽位
  → 指标 + 拼版 → 结论                 → 清理 → verify 验证
        └─────────────────┬──────────────────┘
                          ▼
            【共享结论内核 06_文档与结论】
```

**收编一个新模型/新工作流的标准路径**：先走结构轨（05 的对齐与 verify），再走参数轨（02 离线筛 → 03 受控跑测 → 04 出结论）。

> 本包是**快照**：参考文档原件仍在 `ComfyUI/user/default/workflows/`，结论若有更新以原件为准。
> 编号目录自 2026-09-24 两份桌面项目合并起沿用至今，历史沿革与维护者备忘见对内维护版（仅本地，不随仓库分发）。

---

## 二、核心能力

**参数实验轨（01~04 + 07）——控制变量，证据说话**
- 工作流扁平化：`definitions.subgraphs` 子图展开为可提交 `/prompt` 的 API 图，bypass 透传、可达性裁剪、类型守卫；反向转换（API 图 → UI 图）供评测产物回流 UI 复核
- σ 离线筛：不跑图即可判定调度器风险（首步 Δσ、高噪声区步数），多模型风险矩阵
- 受控跑测：统一提示词与种子（dry-run + `--apply` 自动备份）、参数矩阵、跨模型统一变量、视频时长档位（适配器驱动）
- 结果分析：客观指标 + 基线相似度 + 拼版大图；另有色彩网格文本投影、封面明度审计等纯文本"读图"工具

**结构改造轨（05 + 08）——节点级手术**
- 工作流"取长补短"融合：备份 → 官方模板对齐 → 加槽位 → 清理 → verify 验证全链脚本
- 与 ComfyUI 官方模板的逐份对照快照（diff），模板升级后可一键复查对齐状态

**09_Web面板——人类用户入口**
- 浏览器四页：工作流真值 / σ 风险矩阵 / 受控跑测（进度条+日志）/ 结果分析（指标+拼版）
- 纯 Python 标准库、零第三方依赖；ComfyUI 没起时点「开始跑测」自动拉起

**10_模型家族横评——同底座换权重横评**
- 家族内单变量横评：SHA256 去重、prompt 台账、断点续跑、名册门禁、ledger×产物对账、趋势回归、视频质检、提示词变体闭环


---

## 三、快速开始

### 前置条件

| 项 | 要求 | 说明 |
|---|---|---|
| ComfyUI | 一套可运行的本机 ComfyUI | 脚本要用它自带的 Python（算 σ 需 `comfy.model_sampling` / `comfy.samplers`，分析需 `numpy` / `Pillow`，只有它这套环境齐） |
| 服务地址 | ComfyUI 已启动在 `127.0.0.1:8188` | 02 轨离线 σ 分析不需要服务；03 轨跑测需要 |
| 显卡 | NVIDIA 独显 | 跑测按 11.94GB 显存标定，换卡主要影响耗时；显存紧张可用 `lib_vram.py` 探测预算与降档 |
| 第三方依赖 | 仅 `numpy` / `Pillow` | 版本锁定在 [`requirements-lock.txt`](requirements-lock.txt)（实测 numpy 2.3.5 / Pillow 12.1.0，Python 3.13.11）；新机器或 CI 复跑：`python -m pip install -r requirements-lock.txt` |

> 入口脚本 `run.bat` 顶部 `PY=` 变量写死了 ComfyUI 自带 python 的路径（`%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\python.exe`）——**换机器只改这一行**，根目录入口本身不用动。

### 方式一：Windows（最省事，推荐）

```bat
start.bat              :: 双击即启动 Web 面板（自动打开浏览器）

run.bat                :: 列出所有入口
run.bat panel          :: ★ 启动 Web 面板 → http://127.0.0.1:8189（自动开浏览器；--no-browser 可关）
run.bat sigma          :: 参数轨① 离线 σ 风险矩阵
run.bat unify --apply  :: 参数轨② 统一提示词与种子（写盘；先不加 --apply 看 dry-run）
run.bat models         :: 参数轨③ 跨模型跑测
run.bat analyze        :: 参数轨④ 结果分析
run.bat h3dur --dry-run:: 参数轨⑤ H3 t2v 时长档位（先看计划）
run.bat pipeline       :: ①→②→③→④ 一次跑完
run.bat full           :: ★ E3 一键全链（默认全只读 0 提交；--apply 才实跑；--skip=bench,vqc 跳环节）
run.bat vqc            :: ★ E1 视频质检（容器/帧/时序三层，只读）
run.bat dur --adapter minimax_h3_t2v --dry-run  :: ★ E4 适配器驱动档位跑测
run.bat ftrend         :: ★ E5 历史趋势回归（跨快照比，检出硬回归 exit 1）
```

### 方式二：任意终端（含 Git Bash），自己指定解释器

```bash
PY="%USERPROFILE%/APP/ComfyUI-aki-v3.2/python/python.exe"
"$PY" run.py list        # 同一套子命令：19 个入口 + pipeline / full / list
"$PY" run.py panel       # 启动 Web 面板
```

### Web 面板（09）两条省事行为

- **启动即自动打开浏览器**；不想要加 `--no-browser`
- **ComfyUI 没起时点「开始跑测」会自动拉起**并等就绪（与下方"启动 ComfyUI"同命令，独立控制台窗口）；顶栏也有「启动 ComfyUI」按钮可单独启动

面板端口 `8189`、绑定 `127.0.0.1`，不对外网开放；①② 页不需要 ComfyUI，③④ 页需要。细节见 [`09_Web面板/README.md`](09_Web面板/README.md)。


---

## 四、启动 / 停止 ComfyUI（无人值守）

```bash
cd "%USERPROFILE%/APP/ComfyUI-aki-v3.2"
python/python.exe -s ComfyUI/main.py --port 8188 --disable-auto-launch --disable-comfy-compiler
```

停止：本包脚本不负责停服务。用 `tasklist | grep -i python` 找 PID 精确结束，**不要用 `taskkill /IM python.exe`**（会连带杀其它 python 进程）。

> 走 Web 面板（09）时不用手动执行上面这条：③ 页点「开始跑测」若发现 ComfyUI 没起，会自动按同样命令拉起它并等就绪（上限 5 分钟）。

---

## 五、目录导览

```
ComfyUI-Experiment-Toolbox/
├── README.md                  ← 本文件（对外总索引）
├── run.py / run.bat / start.bat  ★ 根目录统一入口（19 个子命令 + pipeline / full）
├── requirements-lock.txt      ← 第三方依赖锁定（numpy / Pillow）
├── 01_工作流扁平化/            ★ 子图扁平化器 + 反向转换（API → UI）
├── 02_调度器sigma分析/         ★ 不跑图离线筛调度器（风险矩阵 / 单模型详情）
├── 03_受控跑测/               ★ 控制变量实验（统一提示词种子 / 参数矩阵 / 跨模型 / 视频档位）
├── 04_结果分析/               ★ 指标 + 相似度 + 拼版；文本投影 / 明度审计
├── 05_结构改造脚本/           ★ 结构轨全链脚本（⚠️ CONFIG 是节点指纹，见第六节）
├── 06_文档与结论/             ★ 共享结论内核（采样器×调度器主文档、H3 笔记、技能快照）
├── 07_样例输出与数据/          拼版 PNG + 指标/相似度/日志 JSON
├── 08_官方模板对齐/           11 份「工作流 vs 官方模板」对照快照（diff_edit.py 批量生成）
├── 09_Web面板/                ★ 人类用户入口：浏览器四页（端口 8189，零依赖）
├── 10_模型家族横评/           ★ 换权重横评（去重/台账/断点续跑/门禁/对账/趋势/质检/闭环）
├── 99_归档/                   合并前的旧 README + 去重移除的重复副本
├── tests/                     标准库单测（接入 CI）
└── docs/                      CONTRIBUTING.md、release-governance.md
```


---

## 六、脚本调用方式与硬编码常量（改之前必读）

脚本靠**同目录 import** 互调（每个脚本开头有 `sys.path.insert(0, 脚本所在目录)`），**直接双击会 import 失败**。

- **方式 0（最省事）**：走根目录 `run.py`——它已自动把 `01~04` 与 `10_模型家族横评` 注入 `PYTHONPATH`，并把 ComfyUI 根也加进去（σ 计算要 `import comfy.*`），同时强制 UTF-8 输出，无需手工配置任何环境变量。
- **方式 A（手工指定）**：

```bash
ROOT="$PWD"   # 工具箱根目录
export PYTHONPATH="$ROOT/01_工作流扁平化:$ROOT/02_调度器sigma分析:$ROOT/03_受控跑测:$ROOT/04_结果分析:$ROOT/10_模型家族横评:$ROOT/../ComfyUI-aki-v3.2/ComfyUI"
"$USERPROFILE/APP/ComfyUI-aki-v3.2/python/python.exe" "$ROOT/03_受控跑测/run_models.py"
```

> Windows 下 `PYTHONPATH` 分隔符是分号 `;`，ComfyUI 根按本机实际位置替换。

- **方式 B（兜底）**：把要用的脚本临时拷到同一目录再跑。

**硬编码常量**：各脚本运行时路径集中在文件顶部，已统一用 `%USERPROFILE%` 展开（`os.path.expandvars`），换机器无需改脚本本体；**改常量不改逻辑**。

| 位置 | 常量 | 指向 |
|---|---|---|
| `01/build_prompt.py` | `WF` | 工作流文件 |
| `02/sigma_report.py`、`sigma_matrix.py` | `COMFY`、`MODELS` | ComfyUI 根；7 模型预设表 |
| `03/unify_prompt_seed.py` | `WF`、`SRC`、`MAP` | 工作流目录；源工作流；输入名映射 |
| `03/run_combos.py`、`run_models.py` | `COMFY`、`OUT`、`CF_OUT` | 服务地址、结果目录、ComfyUI 输出目录 |
| `03/cfg_probe.py` | `NEG_REAL`、`CASES`、`NODE_ENCODE` | 负向内容；用例；编码节点 id |
| `04/*.py` | `BASE`、`OUT` | 结果目录 |
| `05_结构改造脚本/*` | `D`/`CONFIG` 表 | ⚠️ **本机 11 份工作流（Image 8 + Edit 3）的节点指纹**——换工作流必须重写 CONFIG，把它们当操作说明书读，不要直接跑 |

依赖矩阵：

| 脚本 | 依赖 |
|---|---|
| `flatten.py` / `api_to_ui.py` | 无（只依赖标准库） |
| `text_grid.py` / `light_audit.py` | 无（numpy + Pillow），只读输入图片 |
| `sigma_report.py` / `sigma_matrix.py` | 需 `import comfy.*` → 用 ComfyUI 的 python |
| `run_combos.py` | `build_prompt` |
| `probe.py` / `cfg_probe.py` | `build_prompt`、`run_combos` |
| `run_models.py` | `flatten` |
| `metrics.py` / `focus_sheet.py` / `analyze_models.py` | 无（numpy + Pillow），只依赖输出目录 |
| `05_结构改造脚本/*` | 各自独立，无跨目录依赖（详见该目录 README） |


---

## 七、适用与不适用

**适用**
- flow matching 类模型（Qwen-Image 系、Krea2、FLUX 系、Z-Image 系）的采样器/调度器/steps/cfg 对比
- 任意新版 `definitions.subgraphs` 子图工作流的 headless 跑图
- 固定提示词与种子的对照实验设计

**不适用 / 需另做**
- **Non-KSampler 采样链路**（如 MiniMax H3 视频走 Spectrum 自定义链路）：扁平化能跑，但「换调度器」这个维度不存在
- 图生图/编辑类工作流：需参考图，提示词维度不通用
- 分辨率、LoRA 等其它维度：框架通用，但计划表与覆盖参数要自己改

---

## 八、先记住这几条结论（能省很多时间）

1. **调度器的适配性由「模型自身的 σ 曲线」决定，换模型等于重新洗牌** —— 别照搬别的模型上好用的调度器。
2. **flow 系模型统一避开 `karras` 与 `exponential`**（7/7 模型高危）；步数 ≤8 的蒸馏模型再避开 `kl_optimal`。
3. **安全白名单**：`simple` / `beta` / `sgm_uniform` / `normal` / `ddim_uniform` / `linear_quadratic`。
4. **换调度器的影响远大于换采样器**（7 组不同采样器 + karras 全部同样翻车，两两相似度 0.999~1.000）。
5. **判断调度器能不能用，先离线算，不用跑图**：首步 Δσ > 15% 基本判死；高噪声区（σ>0.5σ_max）步数不足同样判死。
6. **cfg=1 时负向提示词完全不被使用**；唯一例外 `*_cfg_pp` 全族。「没有负向提示词」不是提高 cfg 的理由。
7. **子图容器的 `widgets_values`（positional）才是运行时真值**（`Comfy.Workflow.NamedValuesRestore` 默认 false）；改参数时 positional 与 `widgets_values_named` 两处一起改。
8. **官方模板 > 联网搜索**：ComfyUI 自带 python 的 `site-packages/comfyui_workflow_templates_json/templates/` 下的官方模板（2026-10-20 实测 651 份，全为 `.json`）是最权威依据（结构轨最深刻教训）。
9. 任何工作流改动前先备份（`.bak-<时间戳>` 或独立备份目录），改后必跑 verify。

> 完整证据链（官方源原文、源码位置、实测数据）见 [`06_文档与结论/采样器和调度器的组合推荐.md`](06_文档与结论/采样器和调度器的组合推荐.md)。

---

## 九、参与方式

- 提交 Issue / PR 前请读 [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- 发布与回滚口径见 [`docs/release-governance.md`](docs/release-governance.md)（版本位为 Git tag `v*`）
- 本仓为公开仓：随仓库分发的权威文档即根 `README.md` 与 `.github/**`；`AGENTS.md`、`local/` 为本地维护者上下文，**不在仓库中属预期行为**
