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
| **`run_models.py`** ★ | 跨模型统一变量跑测：按 `PLAN` 表逐组扁平化 → 提交 → 等完成 → 复制输出，写日志 | `python run_models.py`<br>`ONLY=<模型标签> python run_models.py`（只跑一个模型，可断点补跑） | 采样器/调度器等横向对比，多模型 |
| `run_combos.py` | 单模型的「采样器 × 调度器」矩阵跑测 + 客观指标 | `python run_combos.py`<br>`FROM=<组合名> python run_combos.py`（断点续跑） | 只测一个模型、组合多 |
| `probe.py` | **补充验证**：只针对 1~2 个用例，临时改动**另一个维度**（如 steps 25→50）来定位根因 | `python probe.py` | 出现"整组都异常"时，判定是调度器本身的问题还是步数不足 |
| `cfg_probe.py` | cfg × 负向提示词 探针（cfg∈{1,2,4} × 负向∈{空,有}） | `python cfg_probe.py` | 验证 cfg 与负向提示词的相互作用 |

## 要改的常量
- `run_models.py`：`COMFY`（服务地址）、`BASE`/`OUT`/`WF`/`CF_OUT`（路径）、`PLAN`（KSampler 路线）与 `PLAN_CUSTOM`（SamplerCustomAdvanced 路线，如 flux.1-dev 的 `KSamplerSelect`+`BasicScheduler`、Flux.2 Klein 的 `KSamplerSelect`+`Flux2Scheduler`）。
- `unify_prompt_seed.py`：`WF`（工作流目录）、`SRC`（源工作流）、`MAP`（目标文件 → `(提示词输入名, 种子输入名, 额外覆盖)`）。
  ⚠️ **不同工作流的输入名不一样**：多数是 `positive_prompt` + `seed`；**krea2_turbo 是 `value` + `seed_1`**，且要额外把 `value_1`（`prompt_enhance`）设为 `False` —— 它官方模板内置 LLM 扩写提示词，不关掉提示词会被改写、单一变量失效。
- `cfg_probe.py`：`NEG_REAL`（负向提示词内容）、`CASES`、`NODE_ENCODE`（文本编码节点的**扁平化后 ID**，必须对上你的工作流）。

## 使用注意
- **先提交单组校验**：`POST /prompt` 返回的 `node_errors` 为空才继续，别一次性把 20 组都排进去。
- 连续提交即可，ComfyUI 自带队列，不必等前一组结束。
- 跑测期间日志会被脚本反复覆写（`json.dump` 全量重写），**补跑单模型时注意别把完整日志冲掉** —— 本包提供的 `04_结果分析/analyze_models.py` 已改成**直接从输出目录重建清单**，不依赖日志。
- 耗时参考（1024²，RTX 5070 Ti Laptop）：8 步约 15~33s，20 步约 40~50s，25 步约 80~90s，50 步约 130~220s；首个任务含模型加载会多几十秒。
- **采样器耗时差异可达 2 倍**（二阶及以上每步多次模型评估）。
