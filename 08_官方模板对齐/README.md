# 08 官方模板对齐（预留位）

> 本目录来自 2026-09-24 合并前的 `ComfyUI-工作流改造经验/03_官方模板对齐`，当时仅预留未填充。

## 预定用途

存放**本机官方模板的关键节点快照/对照清单**，作为结构轨改造时的比对基准：

- 官方模板源：`%USERPROFILE%\APP\ComfyUI-aki-v3\python\Lib\site-packages\comfyui_workflow_templates_json\templates\`
- 本机工作流：`%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\{Image,Edit}\`

## 建议的填充方式（二选一）

1. **脚本生成**（推荐）：扩展 `../05_结构改造脚本/diff_edit.py`，把「工作流 vs 官方模板」的 diff 结果批量导出到本目录（每份工作流一个 `.md` 或 `.json`）；
2. **手动快照**：把本机实际用到的 8 份官方模板 JSON 原样拷贝进来（注意：模板随 ComfyUI 升级会变，快照需注明来源版本号）。

## 相关工具

- 对齐检查：`../05_结构改造脚本/diff_edit.py`
- 参数权威值：`../06_文档与结论/采样器和调度器的组合推荐.md` 第一节（官方模板原值表）
