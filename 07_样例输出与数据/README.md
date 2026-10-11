# 07 样例输出与数据

用途：**让你知道"正常结果"和"异常结果"各长什么样**，以及拿到原始数据自己复算/画图。

| 文件 | 是什么 | 怎么用 |
|---|---|---|
| `跨模型对比拼版.png` | **最有参考价值**：6 个模型 × 20 组（基线 / karras / exponential / kl_optimal）的带标签拼版 | 一眼看清"karras 与 exponential 组整体糊掉"的对比 |
| `对比拼版_19组.png` | Qwen-Image 2.1 的 17 组矩阵 + 2 组补充验证拼版 | 单模型组合矩阵的全景 |
| `聚焦对照_4组.png` | 4 张大图并排：基线 / 最优 / 异常(karras@25) / 修复(karras@50) | 写报告时的头图；也能直观理解"步数补足 → 重影消失" |
| `model_metrics.json` | **跨模型指标表**：模型 / 组合 / 亮度 / 对比度 / 锐度 / 色彩度 / 与基线相似度 / 相对变化% | 直接读；或据此重画图表 |
| `metrics.json` | Qwen-Image 2.1 的单模型指标表 | 同上 |
| `similarity.json` | 组合间相似度与最近邻（证明"多组合实际等价"） | 查"哪两个组合几乎一样" |
| `result_log.json` | 09-22 十七组的逐组日志（组合、耗时、产物、错误；v2 起由 append-only JSONL 重建，历史不再被覆写，见 `03_受控跑测/README.md`「日志格式」） | 查单组耗时/成败 |
| `model_test_log.json` | 跨模型跑测的日志（**历史注：09-22 曾因单模型补跑被全量覆写，只剩 3 条失败记录**；该覆写风险已由 03 脚本 v2 的 append-only JSONL 修复） | 失败原因参考用；完整清单请看 `model_metrics.json` 或直接看图片目录 |
| `cfg_probe_log.json` | cfg × 负向提示词 探针的逐组耗时 | 参考用（该组耗时噪声大，未用于结论） |

## 图片目录不在本包内

跑测产生的**逐张原图**没有拷进来（体积大且是一次性产物），仍在工作区：

- 单模型矩阵：`%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\output\`
- 跨模型跑测：`%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\output_models\`
- ComfyUI 侧原始落盘：`%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\output\`

**命名规则**：`<模型标签>__<组合名>__<原始文件名>.png` —— 用 `模型__组合` 就能定位，`analyze_models.py` 也是靠这个规则从目录重建清单的。

## 从数据里能直接读到的结论

| 现象 | 数据位置 |
|---|---|
| karras 劣化幅度随步数增加而下降 | `model_metrics.json`：50 步 −25% ＜ 8 步 −55~63% ＜ 20 步 −93% ＜ 25 步 −97% |
| exponential 比同模型 karras 更狠 | Qwen_2512：−64% vs −25% |
| kl_optimal 只在 ≤8 步模型上明显发糊 | Z_image_turbo 对比度 −44%、krea2_turbo 锐度 −33% |
| 基线组彼此高度一致（说明固定提示词与种子生效） | `similarity.json` / 拼版图 |
| Flux.2 Klein 换采样器几乎无差别且都干净 | 拼版图最上方三张 |

## 血缘清单（数据 ↔ 来源 ↔ 引用，2026-10-11 数据治理 R2 P1 建立）

本表是 07 样例数据的可追溯链：每个数据文件 → 生成脚本 → 上游输入 → 下游引用。改动生成脚本或数据文件时同步维护本表（与 `03_受控跑测/data-dictionary.md` 的字段字典互为补充）。

| 数据文件 | 生成脚本（来源） | 上游输入 | 下游引用 |
|---|---|---|---|
| `result_log.json` | `03_受控跑测/run_combos.py`（v2 起由 append-only JSONL 重建） | 03 跑测（Qwen-Image 2.1 工作流 + 17 组合） | 04 `focus_sheet.py` 相似度；06 组合推荐文档（实测组） |
| `model_test_log.json` | `03_受控跑测/run_models.py` | 03 跨模型跑测（多模型 × 组合） | 07 本表「从数据里能直接读到的结论」；06 跨模型 σ 矩阵 |
| `cfg_probe_log.json` | `03_受控跑测/cfg_probe.py` | cfg×负向探针（cfg∈{1,2,4}） | 06 组合推荐文档 §6.6（CFG 与负向提示词核查） |
| `metrics.json` | `04_结果分析/metrics.py` | 04 读取外部输出目录（`ss_test/output/`） | 07 单模型指标表；04 README 指标定义 |
| `model_metrics.json` | `04_结果分析/analyze_models.py` | 04 读取外部输出目录（`output_models/`） | 06/07 跨模型结论 |
| `similarity.json` | `04_结果分析/focus_sheet.py` | 04 选取关键组大图 | 06「多组合等价」论证；07「基线组高度一致」 |
| 拼版 PNG（跨模型对比/19 组/聚焦对照） | 04 三个脚本 | 上述 json 同源 | 06 报告头图；07 快速判读 |

> 维护提示：① 03 跑测脚本改输出字段 → 同步 `data-dictionary.md` + 本表；② 04 脚本改指标/文件 → 同步 `04_结果分析/README.md` 指标定义 + 本表；③ 外部输出目录（`%USERPROFILE%\WorkBuddy\...`）为一次性运行产物，本表数据文件是其仓库内审计副本（见上方「图片目录不在本包内」）。
