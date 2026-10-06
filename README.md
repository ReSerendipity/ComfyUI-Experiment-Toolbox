# ComfyUI 实验与改造工具箱

> 2026-09-24 由桌面两份项目合并而成：
> ① `ComfyUI-采样器调度器实验工具包`（2026-09-22~23 采样器×调度器受控对比实验的脚本与方法沉淀）
> ② `ComfyUI-工作流改造经验`（2026-09 Image 8 份 + Edit 3 份工作流「取长补短」融合改造的脚本与经验沉淀）
> 两者共享同一份结论内核（`06_文档与结论/` 三份文档，合并时已 MD5 校验字节一致，重复副本移入 `99_归档/`）。
> 本包是**快照**：参考文档原件仍在 `ComfyUI\user\default\workflows\`，结论若有更新以原件为准。

---

## 一、两条轨道：这套工具箱是什么

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

---

## 二、目录总览与合并映射

```
ComfyUI-实验与改造工具箱/
├── README.md                      ← 本文件（总索引）
├── run.py                         ★ 根目录统一入口（panel/sigma/unify/models/analyze/pipeline/flatten）
├── run.bat                        ★ Windows 命令行入口（内含 ComfyUI python 路径，转发给 run.py）
├── start.bat                      ★ Windows 双击入口 = `run.bat panel`（启动 Web 面板）
├── 01_工作流扁平化/               ← 【原实验工具包01，编号不变】
│   ├── flatten.py               ★ 通用扁平化器（bypass 透传、可达性裁剪、类型守卫）
│   └── build_prompt.py            单工作流手写版（已被 flatten 取代，留作范本）
├── 02_调度器sigma分析/            ← 【原实验工具包02】不跑图离线筛调度器
│   ├── sigma_matrix.py          ★ 多模型风险矩阵
│   └── sigma_report.py            单模型 σ 曲线详情
├── 03_受控跑测/                   ← 【原实验工具包03】控制变量实验
│   ├── unify_prompt_seed.py     ★ 统一提示词与种子（dry-run + --apply，自动备份）
│   ├── run_combos.py              单模型参数矩阵
│   ├── run_models.py            ★ 跨模型统一变量跑测
│   └── probe.py / cfg_probe.py    补充验证探针
├── 04_结果分析/                   ← 【原实验工具包04】指标 + 拼版
│   ├── analyze_models.py        ★ 跨模型指标 + 基线相似度
│   ├── metrics.py                 单模型指标
│   └── focus_sheet.py             关键结果大图并排
├── 05_结构改造脚本/               ← 【原"工作流改造经验/01_可复用脚本"改名】24 个改造脚本
│   └── README.md                  ★ 本轨完整经验文档（脚本速查/JSON 坑/操作清单）
├── 06_文档与结论/                 ← 【原实验工具包05_文档与结论】共享结论内核
│   ├── 采样器和调度器的组合推荐.md ★ 主文档（结论索引→官方原值→17组实测→σ离线→矩阵→跨模型验证）
│   ├── 采样器名称.md / 调度器名称.md  45 采样器 / 9 调度器速查（含证据等级）
│   ├── 采样器与调度器组合实测对比报告.md  09-22 报告（⚠️ 根因部分已被主文档第7节推翻，见文首标注）
│   └── skill_comfyui-headless-ab-test.md 操作方法技能快照
├── 07_样例输出与数据/             ← 【原实验工具包06】拼版 PNG ×3 + 指标/相似度/日志 JSON
├── 08_官方模板对齐/               ← 【原"工作流改造经验/03_官方模板对齐"】预留位（见其 README）
├── 09_Web面板/                    ← ★ 人类用户入口：浏览器四页操作参数轨（8189 端口，零依赖）
└── 99_归档/                       ← 合并前的两份旧 README + 去重移除的重复文档副本
```

| 原位置 | 新位置 | 变化 |
|---|---|---|
| 实验工具包 01~04 | 01~04（同名） | 无变化，内部引用依然有效 |
| 实验工具包 05_文档与结论 | **06_文档与结论** | 改编号；并吸收改造经验的 3 份同名文档（MD5 一致，唯一副本在此） |
| 实验工具包 06_样例输出与数据 | **07_样例输出与数据** | 改编号 |
| 改造经验 01_可复用脚本 | **05_结构改造脚本** | 改名+改编号（原名没说清"改的是什么"） |
| 改造经验 03_官方模板对齐 | 08_官方模板对齐 | 补了 README 说明用途与填法 |
| 两份旧 README | 99_归档/ | 保留原件；本文件取代二者 |

---

## 三、环境前置

| 项 | 要求 | 说明 |
|---|---|---|
| Python | **用 ComfyUI 自带的那个** | `%USERPROFILE%\APP\ComfyUI-aki-v3\python\python.exe`。脚本要用 `comfy.model_sampling` / `comfy.samplers`（算 σ）、`numpy`、`Pillow`（算指标），只有它这套环境齐 |
| ComfyUI | 已启动在 `127.0.0.1:8188` | 02 轨离线 σ 分析不需要服务；03 轨跑测需要 |
| 显卡 | 本机 RTX 5070 Ti Laptop（11.94GB） | 参数矩阵跑测按此写的，换卡只影响耗时 |

> `run.bat` 已把 ComfyUI 的 python 路径写死在顶部 `PY=` 变量；换机器只改那一行，根目录入口本身不用动。
>
> 第三方依赖版本锁定在根目录 `requirements-lock.txt`（实测：numpy 2.3.5 / Pillow 12.1.0；`comfy.*` 由 ComfyUI 自带 Python 提供，不在此文件）。新机器或 CI 复跑时用 `python -m pip install -r requirements-lock.txt` 对齐。

启动 ComfyUI（无人值守）：

```bash
cd "%USERPROFILE%/APP/ComfyUI-aki-v3"
python/python.exe -s ComfyUI/main.py --port 8188 --disable-auto-launch --disable-comfy-compiler
```

停止：本包脚本不负责停服务。用 `tasklist | grep -i python` 找 PID 精确结束，**不要用 `taskkill /IM python.exe`**（会连带杀其它 python 进程）。

> 走 Web 面板（09）时**不用手动执行上面这条**：③ 页点「开始跑测」若发现 ComfyUI 没起，会自动按同样命令拉起它并等就绪；顶栏也有「启动 ComfyUI」按钮可单独启动。

---

## 四、脚本依赖与 PYTHONPATH（跨目录 import 必读）

脚本靠**同目录 import** 互调（每个脚本开头有 `sys.path.insert(0, 脚本所在目录)`）。直接双击会 import 失败。

**方式 0（最省事，推荐）**：走根目录 `run.py`——它已自动把 `01~04` 注入 `PYTHONPATH`，无需手工 export：

```bat
run.bat models          :: 等价于下面方式 A/B，但不用配任何环境变量
```

**方式 A（手工指定，不改脚本）**：

```bash
ROOT="%USERPROFILE%/Desktop/ComfyUI-实验与改造工具箱"
export PYTHONPATH="$ROOT/01_工作流扁平化;$ROOT/03_受控跑测;$ROOT/04_结果分析"
"$PY" "$ROOT/03_受控跑测/run_models.py"
```

> Windows 下 `PYTHONPATH` 分隔符是分号 `;`。

**方式 B（兜底）**：把要用的脚本临时拷到同一目录再跑。

依赖矩阵：

| 脚本 | 依赖 |
|---|---|
| `flatten.py` | 无（只依赖标准库） |
| `sigma_report.py` / `sigma_matrix.py` | 需 `import comfy.*` → 用 ComfyUI 的 python |
| `run_combos.py` | `build_prompt` |
| `probe.py` / `cfg_probe.py` | `build_prompt`、`run_combos` |
| `run_models.py` | `flatten` |
| `metrics.py` / `focus_sheet.py` / `analyze_models.py` | 无（numpy + Pillow），只依赖输出目录 |
| `05_结构改造脚本/*` | 各自独立，无跨目录依赖（详见该目录 README） |

---

## 五、必须按需修改的硬编码常量

**参数轨**（都在文件顶部）：

| 文件 | 常量 | 现在指向 |
|---|---|---|
| `01/build_prompt.py` | `WF` | `...\workflows\Image\Qwen_image_2_1_t2i.json` |
| `02/sigma_report.py`、`sigma_matrix.py` | `COMFY`、`MODELS` | ComfyUI 根；7 模型预设表 |
| `03/unify_prompt_seed.py` | `WF`、`SRC`、`MAP` | 工作流目录；源工作流；输入名映射 |
| `03/run_combos.py` | `COMFY`、`OUT`、`CF_OUT` | 服务地址、结果目录、ComfyUI 输出目录 |
| `03/run_models.py` | `COMFY`、`BASE`、`OUT`、`WF`、`CF_OUT`、`PLAN`/`PLAN_CUSTOM` | 同上；模型×组合计划表（`BASE` 指向工作区 `ss_test`） |
| `03/cfg_probe.py` | `NEG_REAL`、`CASES`、`NODE_ENCODE` | 负向内容；用例；编码节点 id |
| `04/metrics.py` `analyze_models.py` `focus_sheet.py` | `BASE`、`OUT` | 结果目录 |

**结构轨**：`05_结构改造脚本/` 各脚本的 `D`/`CONFIG` 表（含 `main_id`/`unet_link_id` 等节点 id 指纹）——这些是**针对本机那 11 份工作流写的**，换工作流必须重写 CONFIG，把它们当操作说明书读，不要直接跑。

> 全包共 6 个文件含本机绝对路径（`README.md`、`09_Web面板/panel.py`、`09_Web面板/README.md`、`09_Web面板/test_dom.js`、`06_文档与结论/skill_comfyui-headless-ab-test.md`、`99_归档/README-旧-实验工具包-20260923.md`），换机器需逐项调整。

---

## 六、快速上手

**先记住一件事：根目录就是入口。** 不用 cd 进子目录，也不用记 ComfyUI 的 python 路径。

```bat
:: 方式一：Windows 双击
start.bat              :: 启动 Web 面板（最常用）—— 启动后自动帮你打开浏览器

:: 方式二：Windows 命令行
run.bat                :: 列出所有入口
run.bat panel          :: ★ 启动 Web 面板 → http://127.0.0.1:8189（自动开浏览器）
run.bat sigma          :: 参数轨① 离线 σ 风险矩阵
run.bat unify --apply  :: 参数轨② 统一提示词与种子（写盘）
run.bat models         :: 参数轨③ 跨模型跑测
run.bat analyze        :: 参数轨④ 结果分析
run.bat pipeline       :: ①→②→③→④ 一次跑完
```

> 面板内建两条省事行为：**启动即自动打开浏览器**；**ComfyUI 没起时点「开始跑测」会自动帮你拉起**。
> 不想要自动开浏览器就加 `--no-browser`（`run.bat panel --no-browser`）。细节见 `09_Web面板/README.md`。

```bash
# 方式三：任意终端（含 Git Bash），自己指定解释器
PY="%USERPROFILE%/APP/ComfyUI-aki-v3/python/python.exe"
"$PY" run.py list      # 同一套子命令：panel/sigma/unify/models/analyze/pipeline/flatten
```

> `run.py` 只做三件事：把 `01~04` 子目录加进 `PYTHONPATH`（脚本之间靠同目录 import 互调）、
> 强制 UTF-8 输出（避免 GBK 控制台打印中文报 UnicodeEncodeError）、以子进程方式调用目标脚本。
> 因此每个脚本的行为与「单独运行」完全一致——**脚本本体刻意不搬到根目录**：`panel.py` 靠
> `__file__` 反推 TOOLBOX 并读同目录 `index.html`，`run_models.py` 裸 `import flatten`，搬运会直接破坏它们。

**参数轨四步（根入口 ↔ 原生命令对照）**：

| 步 | 根入口 | 等价原生命令 |
|---|---|---|
| ① 离线筛调度器（不跑图） | `run.bat sigma` | `python 02_调度器sigma分析/sigma_matrix.py` |
| ② 统一提示词与种子 | `run.bat unify`（先 dry-run，确认后加 `--apply`，会自动备份） | `python 03_受控跑测/unify_prompt_seed.py` |
| ③ 跨模型跑测 | `run.bat models` | `python 03_受控跑测/run_models.py` |
| ④ 指标 + 拼版 | `run.bat analyze` | `python 04_结果分析/analyze_models.py` |

**结构轨**：见 `05_结构改造脚本/README.md` 的操作清单（选基准→补节点→删冗余→融合→官方对齐→统一布局→清 prompt→备份）。结构轨**刻意不进根入口**——低频高风险，且 `05` 的 `CONFIG` 是本机 11 份工作流的节点指纹，必须当说明书读、不能盲跑。

---

## 七、适用与不适用

**适用**
- flow matching 类模型（Qwen-Image 系、Krea2、FLUX 系、Z-Image 系）的采样器/调度器/steps/cfg 对比
- 任意新版 `definitions.subgraphs` 子图工作流的 headless 跑图
- 固定提示词与种子的对照实验设计

**不适用 / 需另做**
- **Non-KSampler 采样链路**（如 MiniMax H3 视频走 Spectrum 自定义链路）：扁平化能跑，但「换调度器」这个维度不存在
- 图生图/编辑类工作流：需参考图，提示词维度不通用
- 分辨率、LoRA 等其它维度：框架通用，但 `PLAN` 表与覆盖参数要自己改

---

## 八、先记住这几条结论（能省很多时间）

1. **调度器的适配性由「模型自身的 σ 曲线」决定，换模型等于重新洗牌** —— 别照搬别的模型上好用的调度器。
2. **flow 系模型统一避开 `karras` 与 `exponential`**（7/7 模型高危）；步数 ≤8 的蒸馏模型再避开 `kl_optimal`。
3. **安全白名单**：`simple` / `beta` / `sgm_uniform` / `normal` / `ddim_uniform` / `linear_quadratic`。
4. **换调度器的影响远大于换采样器**（7 组不同采样器 + karras 全部同样翻车，两两相似度 0.999~1.000）。
5. **判断调度器能不能用，先离线算，不用跑图**：首步 Δσ > 15% 基本判死；高噪声区（σ>0.5σ_max）步数不足同样判死。
6. **cfg=1 时负向提示词完全不被使用**；唯一例外 `*_cfg_pp` 全族。「没有负向提示词」不是提高 cfg 的理由。
7. **子图容器的 `widgets_values`（positional）才是运行时真值**（`Comfy.Workflow.NamedValuesRestore` 默认 false）；改参数时 positional 与 `widgets_values_named` 两处一起改。
8. **官方模板 > 联网搜索**：本机 `comfyui_workflow_templates_json\templates\` 下的官方模板是最权威依据（结构轨最深刻教训）。
9. 任何工作流改动前先备份（`.bak-<时间戳>` 或独立备份目录），改后必跑 verify。

> 完整证据链（官方源原文、源码位置、实测数据）见 `06_文档与结论/采样器和调度器的组合推荐.md` 第〇~九节。

---

## 九、改造方向（Roadmap）

- **Web UI 化（已落地，2026-09-24）**：`09_Web面板/` —— 本机轻量面板（纯标准库，端口 8189），四页复用参数轨 01~04：工作流真值 / σ 风险矩阵 / 受控跑测（进度条+日志）/ 结果分析（指标+拼版）。启动方式见 `09_Web面板/README.md`。结构轨（05/08）**刻意不 Web 化**——低频高风险的 JSON 手术，前端（Autogrow 加槽）或 agent 脚本更稳。
- 官方模板升级时：用 `05_结构改造脚本/diff_edit.py` 复查对齐状态。
