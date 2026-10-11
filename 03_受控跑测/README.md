# 03 受控跑测

**路线声明：这是「控制变量对照实验」，不是「批量生成」。** 两者不可混用：

| | 控制变量对照（本目录） | 批量生成（不在本包） |
|---|---|---|
| 提示词 | **固定单一常量** | 一次多个，来自 `input/Picture/*.txt` |
| 种子 | **固定** | 常随机 |
| 变化项 | 每轮只变一个维度 | 提示词本身就是变量 |
| 对照方式 | 以同模型自身配置为基线 | 无对照 |

> **硬性要求**：控制变量路线下，工作流里的 `BatchPromptReaderWithClip`（批量提示词读取器）**必须旁路**，改为注入受控提示词。原因：① 留着它提示词就不受控、实验失效；② 该目录为空时直接报错。
> 技术要点：它输出的是 **`CONDITIONING`**（通常接给 `ConditioningZeroOut → CFGGuider.negative`），**不能把它的下游接到它的 `clip` 输入**（类型不符：CLIP ≠ CONDITIONING）。正确做法是删掉它、新建 `CLIPTextEncode`（`clip` 取原来源、`text=""`）接原下游 —— `run_models.py` 的 `DROP_ALWAYS` 已实现这套处理。

| 文件 | 功能 | 使用方式 | 适用场景 |
|---|---|---|---|
| **`unify_prompt_seed.py`** ★ | 把「源工作流」的提示词与种子统一写入其它工作流的容器控件（`widgets_values` 与 `widgets_values_named` **双写**），改前逐个备份为 `.bak-<时间戳>` | `python unify_prompt_seed.py`（dry-run 清单）<br>`python unify_prompt_seed.py --apply`（真正写盘） | 做跨模型/跨工作流对比前，**先把提示词与种子变成常量** |
| **`run_models.py`** ★ | 跨模型统一变量跑测：按 `PLAN` 表逐组扁平化 → 提交 → 等完成 → 复制输出，写日志（v2：append-only JSONL + 合并视图） | `python run_models.py`<br>`ONLY=<模型标签> python run_models.py`（只跑一个模型，可断点补跑） | 采样器/调度器等横向对比，多模型 |
| `run_combos.py` | 单模型的「采样器 × 调度器」矩阵跑测 + 客观指标（v2：append-only JSONL + 合并视图） | `python run_combos.py`<br>`FROM=<组合名> python run_combos.py`（断点续跑） | 只测一个模型、组合多 |
| `probe.py` | **补充验证**：只针对 1~2 个用例，临时改动**另一个维度**（如 steps 25→50）来定位根因 | `python probe.py` | 出现"整组都异常"时，判定是调度器本身的问题还是步数不足 |
| `cfg_probe.py` | cfg × 负向提示词 探针（cfg∈{1,2,4} × 负向∈{空,有}） | `python cfg_probe.py` | 验证 cfg 与负向提示词的相互作用 |

## 日志格式（v2，2026-10-11）

`run_models.py` / `run_combos.py` 的跑测日志改为**双文件**（见 `logutil.py`）：

- `<BASE>\*.jsonl` —— **追加式原始日志（唯一事实源）**：每条记录 append 一行，**永不覆写**，补跑/续跑只会新增记录，历史不再丢失；
- `<BASE>\*.json` —— **合并视图**（`result_log.json` / `model_test_log.json`）：由 jsonl 重建，按 `(模型,组合)`（或组合名）取**最新一条**，保持旧读取方兼容；旧版合并视图会自动迁入 jsonl（`migrate_legacy`）。

每条记录除业务字段（`label/model/combo/sampler/scheduler/ok/sec/files/error`）外，新增实验参数与环境快照字段：

| 字段 | 含义 |
|---|---|
| `schema_version` | 记录 schema 版本（当前 2；旧记录无此字段，读取方 `.get()` 容错，见 `data-dictionary.md`） |
| `ts` | 本地时间（`%Y-%m-%d %H:%M:%S`） |
| `seed` | 实际种子：run_combos 取 `build_prompt.SEED`（1111119）；run_models 取扁平化结果 KSampler 的运行时值 |
| `steps` / `cfg` | 单模型矩阵取固定值（25/1）；跨模型取扁平化 KSampler 运行时值（custom 链路读不到 → `null`） |
| `py` | 解释器版本（`platform.python_version()`） |
| `comfy` | ComfyUI 版本（`/system_stats`；服务未启动 → `null`，不阻塞跑测） |

> 目的（评估报告 P1-1/P1-2）：旧实现每次 `json.dump` 全量覆写，单模型补跑会把完整日志冲掉（07 样例中 `model_test_log.json` 曾只剩 3 条失败记录）；v2 保证三个月后可按日志重建当时的参数与环境全貌。
> 字段权威字典与 schema 版本纪律见同目录 **[`data-dictionary.md`](data-dictionary.md)**（2026-10-11 数据治理 R2 P1 建立）。

---

## 参数集基线（v1，2026-10-11 登记，数据治理 R2 P1）

跑测输入参数集在脚本中以常量登记（未抽为独立文件，先以本表固化当前基线，后续改动按此版本化）：

| 参数集 | 位置 | 内容（2026-10-11 时点） |
|---|---|---|
| 固定提示词 | `unify_prompt_seed.py`（写入各工作流） | 818 字符受控提示词；krea2_turbo 输入名 `value` + `seed_1`，且 `value_1`（prompt_enhance）须为 `False` |
| 固定种子 | `run_models.py` `FIXED_SEED` | `1111119`（run_combos 用 `build_prompt.SEED` 同值） |
| 跨模型 PLAN | `run_models.py` `PLAN` / `PLAN_CUSTOM` | Z_image_turbo_8step / krea2_turbo_8step / Z_image_25step / Qwen_image_2512_50step（KSampler 轨）+ flux1dev_20step / Flux2Klein_4step（custom 轨）；steps/cfg 取各工作流运行时值 |
| 单模型矩阵 | `run_combos.py` | euler+simple 等 17 组；steps 25 / cfg 1（Qwen-Image 2.1 基线） |
| cfg 探针 | `cfg_probe.py` `CASES` | cfg∈{1,2,4} × 负向∈{空,实际} 共 5 组；其余保持工作流原值（euler+simple / 25 步 / 种子 1111119）——**探针刻意偏离基线**，结论仅用于 cfg×负向交互，不并入采样器结论 |

**与 10_模型家族横评 的参数口径**（同名参数必须一致，防止口径打架）：
- `krea2_turbo` cfg：本表与 `10_模型家族横评/family_config.json`（cfg=1.0）、`06_文档与结论`（官方原值 1）一致；**05 权威值表曾误记 cfg=4，已修正**（见 05 README 采样参数权威值表复核注）。
- 修改任一参数集：同步更新本表「内容」列并递增「基线版本」（v1→v2…），记录修改日期与理由；跨轨参数（cfg/steps/sampler/scheduler）变更须同时核对 `10_模型家族横评/family_config.json` 与 `06_文档与结论`。

## 要改的常量
- `run_models.py`：`COMFY`（服务地址）、`BASE`/`OUT`/`WF`/`CF_OUT`（路径）、`PLAN`（KSampler 路线）与 `PLAN_CUSTOM`（SamplerCustomAdvanced 路线，如 flux.1-dev 的 `KSamplerSelect`+`BasicScheduler`、Flux.2 Klein 的 `KSamplerSelect`+`Flux2Scheduler`）。
- `unify_prompt_seed.py`：`WF`（工作流目录）、`SRC`（源工作流）、`MAP`（目标文件 → `(提示词输入名, 种子输入名, 额外覆盖)`）。
  ⚠️ **不同工作流的输入名不一样**：多数是 `positive_prompt` + `seed`；**krea2_turbo 是 `value` + `seed_1`**，且要额外把 `value_1`（`prompt_enhance`）设为 `False` —— 它官方模板内置 LLM 扩写提示词，不关掉提示词会被改写、单一变量失效。
- `cfg_probe.py`：`NEG_REAL`（负向提示词内容）、`CASES`、`NODE_ENCODE`（文本编码节点的**扁平化后 ID**，必须对上你的工作流）。

## 使用注意
- **先提交单组校验**：`POST /prompt` 返回的 `node_errors` 为空才继续，别一次性把 20 组都排进去。
- 连续提交即可，ComfyUI 自带队列，不必等前一组结束。
- 跑测日志为 **append-only JSONL + 合并视图**（v2，见上方「日志格式」）：`*.jsonl` 永不覆写，`*.json` 由 jsonl 重建，**补跑单模型不会再冲掉历史**。`04_结果分析/analyze_models.py` 依旧直接从输出目录重建清单，不依赖日志。
- 耗时参考（1024²，RTX 5070 Ti Laptop）：8 步约 15~33s，20 步约 40~50s，25 步约 80~90s，50 步约 130~220s；首个任务含模型加载会多几十秒。
- **采样器耗时差异可达 2 倍**（二阶及以上每步多次模型评估）。

---

## 日志与产物保留策略（v1，2026-10-11 数据治理 R2 P2）

| 数据 | 位置 | 保留策略 |
|---|---|---|
| 跑测日志 JSONL（唯一事实源） | `03_受控跑测`（`<BASE>`） | **append-only，永不删除/覆写**；建议按季度将历史 `*.jsonl` 归档压缩（如 `logs-archive-YYYY-QN.zip`）后移出工作目录，归档后合并视图仍可随时由 jsonl 重建 |
| 合并视图 JSON | 同上 | 可再生资产：由 jsonl 重建，丢失不影响事实源；不单独归档 |
| 运行产物（图片/输出目录） | 外部 `%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\` 等 | 一次性运行产物，**不进仓库**；07 样例数据是其在仓库内的审计副本。清理由系统磁盘管理，本仓不承担备份责任 |
| `__pycache__` / `*.pyc` | 各脚本目录 | 可再生，已被 `.gitignore` 排除；无需保留 |

触发归档的条件：`*.jsonl` 累计体积超过 ~5 MB 或跨季度；归档前先跑一次合并视图重建确认当前结论可复现。删除前须确认对应结论已写入 06/07 文档（结论留痕于文档，数据可归档）。
