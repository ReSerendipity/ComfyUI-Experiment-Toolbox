# 08 官方模板对齐

> 本目录来自 2026-09-24 合并前的 `ComfyUI-工作流改造经验/03_官方模板对齐`；当时仅预留未填充，
> 已于 **2026-10-11** 用 `diff_edit.py --export-dir` 批量填充（评估报告 P2-5）。

## 内容

`<工作流名>.diff.md` × 11（Image 8 份 + Edit 3 份）：「当前工作流 vs 官方模板」对照快照，每份含：

- **概览**：顶层节点类型 删/加 清单；
- **子图差异**：逐子图逐节点 id 的 新增 / 删除 / widgets 变化（官方值 vs 当前值）。

示例（`Qwen_image_2_1_t2i.json.diff.md`）：顶层类型无删加；子图内可见 KSampler 种子模式
`'fixed'→'randomize'`、新增 LoraLoaderModelOnly / TextGenerate / SeedVR2 等融合节点——与
`../05_结构改造脚本/README.md` 的改造清单互相印证。

## 再生成

```bat
python ..\05_结构改造脚本\diff_edit.py --export-dir . ^
  --templates "%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\Lib\site-packages\comfyui_workflow_templates_json\templates" ^
  --edit "%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Edit" ^
  --image "%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image"
```

> 不传 `--edit/--image/--templates` 时按 README 约定路径（ComfyUI-aki-v3）；本机实际为 aki-v3.2。
> 模板随 ComfyUI 升级会变，快照已带生成时间戳，模板更新后重新生成即可对照。

## 相关工具

- 对齐检查 / 再生成：`../05_结构改造脚本/diff_edit.py`（v2 覆盖 Image + Edit 双轨）
- 参数权威值：`../06_文档与结论/采样器和调度器的组合推荐.md` 第一节（官方模板原值表）
