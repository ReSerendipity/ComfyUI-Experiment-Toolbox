# family_bench_20261006 · 模型家族横评首轮全量跑测（审计数据副本）

`10_模型家族横评` 模块的**第一轮全量跑测**归档：3 个家族 × 8 个 checkpoint × 9 组提示词 × 3 个种子。

| 项 | 值 |
|---|---|
| 运行窗口 | 2026-09-30 ~ 2026-10-01（跑测）/ 2026-10-06（分析） |
| 生成脚本 | 跑测 `10_模型家族横评/bench_family.py`；分析 `10_模型家族横评/analyze_family.py` |
| 数据规模 | **216 / 216 全部 ok，failed=0**（8 模型 × S1–S9 × 3 种子） |
| 家族 | FLUX-1-dev（3 权重）、FLUX-2-klein-9b（3 权重，含 1 个 declared_exception 走 zimage 链）、Krea2-turbo（2 权重） |
| 耗时参考 | `elapsed_s` min 18.1 / max 156.9 / mean 55.6（RTX 5070 Ti Laptop，1024²，单机单卡口径） |

## 文件清单

| 文件 | 是什么 | 来源 |
|---|---|---|
| `family_metrics.json` | 逐张客观指标：亮度 / 对比度σ / 锐度 LapVar / 色彩度 + family/model/prompt/seed/chain | `analyze_family.py`（原 `metrics.json`，改名避免与 07 根目录同名文件混淆） |
| `family_similarity.json` | 同模型同 prompt 跨种子稳定性（72 组，每组 3×3 相似度矩阵） | 同上 |
| `report_skeleton.md` | 读图评分报告骨架：家族清单 + 双口径排名空表（Stratum A/B） | 同上 |
| `ledger_sanitized.json` | 跑测台账脱敏版：每条 family/model/prompt/seed/ok/elapsed_s | `bench_family.py` 实时写盘的原 `ledger.json`，剥除路径后重排 |

## 口径与脱敏说明

- **seed 口径**：统一采用 `analyze_family.py` 的文件名口径 `s<种子>`（如 `s20260930`），三个数据文件可直接按 `(family, model, prompt, seed)` join；原始配置种子为 `20260930 / 424242 / 7777777`（见 `family_config.json`）。
- **脱敏**：原 `ledger.json` 每条含指向本机 output 的绝对路径（`image` 字段），违反本仓公开红线，故整字段剥除；`ok` / `elapsed_s` 与原值逐条一致。原文件随原始输出目录留档于本机，不入库。
- **相似度口径**：`family_similarity.json` 仅用于**同模型同 prompt 跨种子**稳定性，禁止拿它跨架构/跨家族比像素（见 10 README「重要陷阱」§4）。
- **客观指标是辅助参考**：`family_metrics.json` 不替代读图评分；`report_skeleton.md` 的 100 分制评分表当时**未填写**（空模板），故未随包。

## 图片不在本包内（与 07 根目录约定一致）

逐张原图（含 `family_montage.png` 拼版）为一次性产物且含限制级内容（S8 等提示词出图），**不入公开仓**，已随本机原始输出目录清理。复现路径：

```powershell
# 跑测（需 ComfyUI 在 8188；comfy_root 按本机实际改）
python run.py fbench --families FLUX-1-dev,FLUX-2-klein-9b,Krea2-turbo
# 分析（重算 metrics/similarity/拼版/评分表骨架）
python run.py fanalyze --root <跑测输出根> --out <分析输出目录>
```

> 注：本轮归档时（2026-10-15）`family_config.json` 等处默认 `comfy_root` 仍指向旧安装目录；复现前需先对齐到本机现行 ComfyUI 根。
