# 架构 — ComfyUI-Experiment-Toolbox

> 治理定位：`delivery=tool`、`lifecycle=active`（`governance/desired-state.json`）。
> 本文按 2026-11-03 的实际目录结构生成；数据流与边界须由维护者在实现变更时同步复核。

## 1. 定位

**ComfyUI 采样器/调度器受控实验 + 工作流结构改造工具箱**

## 2. 组件与依赖方向

```text
测试层：tests/ (4)
支撑层：docs/ (7)、.github/ (6)
其他层：11_版式化文生图/ (222)、10_模型家族横评/ (45)、05_结构改造脚本/ (29)、07_样例输出与数据/ (16)、03_受控跑测/ (12)、06_文档与结论/ (12)、08_官方模板对齐/ (12)、04_结果分析/ (6)、99_归档/ (6)、01_工作流扁平化/ (5)、02_调度器sigma分析/ (5)、09_Web面板/ (4)
根级层：根级文件 (13)
```

| 组件 | 目录 | 文件数 | 代表文件 |
|---|---|---|---|
| `11_版式化文生图` | `11_版式化文生图/` | 222 | `11_版式化文生图/README.md`, `11_版式化文生图/ab_matrix.html`, `11_版式化文生图/build_ab.py` |
| `10_模型家族横评` | `10_模型家族横评/` | 45 | `10_模型家族横评/README.md`, `10_模型家族横评/analyze_family.py`, `10_模型家族横评/bench_family.py` |
| `05_结构改造脚本` | `05_结构改造脚本/` | 29 | `05_结构改造脚本/README.md`, `05_结构改造脚本/add_flux2_8.py`, `05_结构改造脚本/add_ref_images.py` |
| `07_样例输出与数据` | `07_样例输出与数据/` | 16 | `07_样例输出与数据/README.md`, `07_样例输出与数据/cfg_probe_log.json`, `07_样例输出与数据/family_bench_20261006/README.md` |
| 根级文件 | `/` | 13 | `.editorconfig`, `.gitattributes`, `.gitignore` |
| `03_受控跑测` | `03_受控跑测/` | 12 | `03_受控跑测/README.md`, `03_受控跑测/adapters.json`, `03_受控跑测/cfg_probe.py` |
| `06_文档与结论` | `06_文档与结论/` | 12 | `06_文档与结论/MOSS-Image-书法与诗画合一实测结论.md`, `06_文档与结论/MOSS-Image-版式化文生图实测结论.md`, `06_文档与结论/README.md` |
| `08_官方模板对齐` | `08_官方模板对齐/` | 12 | `08_官方模板对齐/Flux.2_Klein-9B-Distilled.json.diff.md`, `08_官方模板对齐/Qwen_image.json.diff.md`, `08_官方模板对齐/Qwen_image_2512.json.diff.md` |
| `docs` | `docs/` | 7 | `docs/CONTRIBUTING.md`, `docs/agent-contract.md`, `docs/assets/readme-comfyui-experiment-toolbox-1-20261026.png` |
| `04_结果分析` | `04_结果分析/` | 6 | `04_结果分析/README.md`, `04_结果分析/analyze_models.py`, `04_结果分析/focus_sheet.py` |
| `99_归档` | `99_归档/` | 6 | `99_归档/02_经验文档-重复副本-已去重-20260924/调度器名称.md`, `99_归档/02_经验文档-重复副本-已去重-20260924/采样器名称.md`, `99_归档/02_经验文档-重复副本-已去重-20260924/采样器和调度器的组合推荐.md` |
| `01_工作流扁平化` | `01_工作流扁平化/` | 5 | `01_工作流扁平化/README.md`, `01_工作流扁平化/api_to_ui.py`, `01_工作流扁平化/build_prompt.py` |
| `02_调度器sigma分析` | `02_调度器sigma分析/` | 5 | `02_调度器sigma分析/README.md`, `02_调度器sigma分析/sigma_matrix.py`, `02_调度器sigma分析/sigma_model_matrix.json` |
| `09_Web面板` | `09_Web面板/` | 4 | `09_Web面板/README.md`, `09_Web面板/index.html`, `09_Web面板/panel.py` |
| `tests` | `tests/` | 4 | `tests/test_flatten.py`, `tests/test_logutil.py`, `tests/test_panel_api.py` |

依赖方向：入口层（应用 / 页面）调用领域层（业务模块），领域层依赖基础设施层（脚本、配置、模型资产）；反向引用不允许。

## 3. 数据流

ComfyUI 加载工作流 JSON → 按编号目录运行实验脚本 → 输出图像与指标表格。

## 4. 外部依赖

| 依赖 | 用途 | 不可用时 |
|---|---|---|
| ComfyUI | 工作流执行宿主 | 实验脚本无运行环境 |

## 5. 边界与非目标

- 不做长期在线服务；离线即可完成主要工作。
- 不引入与工具体积不匹配的重型运行时。
- 不入库：密钥 / token / 口令 / 连接串、本机绝对路径、`local/` 与 `AGENTS.md`、构建产物。
- 治理正文只在 `ReSerendipity/.github/governance`，本仓不复制规则正文。

## 6. 变更影响面

| 改什么 | 必须同步 | 由谁校验 |
|---|---|---|
| 目录结构 / 入口 | 本文「组件与依赖方向」与「数据流」 | 维护者 |
| CI 与门禁 | 本仓 `README.md` 的测试命令；治理仓 §20 远端载体口径 | `audit-drift.py` |
| 依赖清单 | 锁文件与 `.github/dependabot.yml` 的生态段 | Dependabot / `lock-consistency` |
| README 展示图 | §8.1 真实性红线（图必须来自真实运行） | 治理仓 `readme-image-provenance` |
