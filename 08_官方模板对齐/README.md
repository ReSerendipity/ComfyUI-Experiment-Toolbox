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

> 不传 `--edit/--image/--templates` 时按 README 约定路径（ComfyUI-aki-v3.2）；本机实际为 aki-v3.2。
> 模板随 ComfyUI 升级会变，快照已带生成时间戳，模板更新后重新生成即可对照。
>
> **模板总数是会漂移的数字，文档里不要写死**：实测 2026-10-20 为 651 份，2026-10-31 已到 674 份（11 天 +23）。
> 需要引用时写「当前实测」并带日期，或只描述量级（数百份）。

## 选对模板：同一模型有十几份官方模板，怎么判

官方模板目录 `python/Lib/site-packages/comfyui_workflow_templates_json/templates/` 里，**同一个模型往往有多份变体**——
实测 Qwen 系 27 份（其中 t2i 只有 3 份）、Z-Image 6 份（t2i 4 份，含 int8）、Krea 4 份、FLUX 23 份。
挑错模板的代价是「缺模型 → `value_not_in_list` → 静默无输出」或「跑通但链路不是你想测的那条」。

三条判据，按顺序用：

1. **文件名后缀对齐量化与蒸馏**：`_sd_`（如 `image_flux3_klein_distilled_t2i.json`）对应 **distilled** 权重，
   `_base_` 对应非蒸馏版。拿 `_sd_` 的权重去套 `_base_` 模板，模型名对不上。
2. **用 CLIP / VAE 名反查**：模板引用的 text encoder 名与本地权重是同一份，才算同一条链。
   实测 Z_image_turbo 的 `qwen_3_4b_fp8_mixed` 恰好等于官方 `image_z_image_turbo_int8` 链的 TE，据此确认。
3. **模板引用的每个模型本地都要有**：模板常带增益件（prompt upsampler / SLG / 特定量化档），缺一个就加载失败。

> **开关设 `false` 挡不住静态校验**：`ComfySwitchNode` 的 `lazy=True` + `check_lazy_status` 只让**执行层**跳过未选分支，
> 而 `execution.py` 的 `validate_inputs` 会递归校验所有连线输入、无惰性豁免——模板原样 + `switch=false` 仍会被
> `value_not_in_list` 拒绝。必须**物理裁剪**分支：`../01_工作流扁平化/derive_api.py` 的 `resolve_switches`。

## 相关工具

- 对齐检查 / 再生成：`../05_结构改造脚本/diff_edit.py`（v2 覆盖 Image + Edit 双轨）
- 参数权威值：`../06_文档与结论/采样器和调度器的组合推荐.md` 第一节（官方模板原值表）
